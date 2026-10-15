-- 014 — Workflow de modification des RÉFÉRENTIELS RÉGLEMENTAIRES (back-office interne).
-- Les barèmes (rate_table, tax_bracket) sont DATÉS D'EFFET : une modification = une NOUVELLE
-- version (insert), jamais un écrasement. Le rôle applicatif n'a PAS le droit d'écrire ces
-- tables (REVOKE) ; les modifications passent par ce workflow contrôlé (4-yeux) via des
-- fonctions SECURITY DEFINER. AUCUNE valeur n'est inventée : le proposeur fournit la valeur
-- ET sa source juridique ; la validation est humaine et tracée.

CREATE TABLE IF NOT EXISTS regulatory_change (
    id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    type          text NOT NULL CHECK (type IN ('rate','bracket')),
    cible_code    text NOT NULL,                 -- rate_table.code ou tax_bracket.table_code
    payload       jsonb NOT NULL,                -- {valeur} | {tranche_min,tranche_max,taux}
    date_effet    date NOT NULL,
    source        text NOT NULL,                 -- référence juridique (obligatoire)
    note          text,
    statut        text NOT NULL DEFAULT 'proposee'
                  CHECK (statut IN ('proposee','validee','publiee','rejetee')),
    propose_par   uuid NOT NULL REFERENCES app_user(id),
    valide_par    uuid REFERENCES app_user(id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    validated_at  timestamptz,
    published_at  timestamptz
);
CREATE INDEX IF NOT EXISTS idx_regchange_statut ON regulatory_change(statut, created_at DESC);

-- Lecture des barèmes courants (dernière version effective par code).
CREATE OR REPLACE FUNCTION reg_referentials_read()
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path = public STABLE AS $$
  SELECT jsonb_build_object(
    'rates', (SELECT coalesce(jsonb_agg(jsonb_build_object(
                'code', code, 'valeur', valeur, 'date_effet', date_effet, 'source', source) ORDER BY code, date_effet DESC), '[]'::jsonb) FROM rate_table),
    'brackets', (SELECT coalesce(jsonb_agg(jsonb_build_object(
                'table_code', table_code, 'tranche_min', tranche_min, 'tranche_max', tranche_max,
                'taux', taux, 'date_effet', date_effet, 'source', source) ORDER BY table_code, tranche_min), '[]'::jsonb) FROM tax_bracket)
  );
$$;
REVOKE ALL ON FUNCTION reg_referentials_read() FROM PUBLIC;

CREATE OR REPLACE FUNCTION reg_changes_list()
RETURNS TABLE (id uuid, type text, cible_code text, payload jsonb, date_effet date, source text,
               note text, statut text, propose_par text, valide_par text,
               created_at timestamptz, published_at timestamptz)
LANGUAGE sql SECURITY DEFINER SET search_path = public STABLE AS $$
  SELECT c.id, c.type, c.cible_code, c.payload, c.date_effet, c.source, c.note, c.statut,
         pu.email, vu.email, c.created_at, c.published_at
  FROM regulatory_change c
  LEFT JOIN app_user pu ON pu.id = c.propose_par
  LEFT JOIN app_user vu ON vu.id = c.valide_par
  ORDER BY c.created_at DESC;
$$;
REVOKE ALL ON FUNCTION reg_changes_list() FROM PUBLIC;

-- Proposition d'une modification (statut 'proposee').
CREATE OR REPLACE FUNCTION reg_change_propose(
    p_actor uuid, p_type text, p_cible text, p_payload jsonb, p_date_effet date, p_source text, p_note text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_id uuid;
BEGIN
  IF p_type NOT IN ('rate','bracket') THEN RAISE EXCEPTION 'Type invalide'; END IF;
  IF coalesce(btrim(p_source),'') = '' THEN RAISE EXCEPTION 'Source juridique obligatoire'; END IF;
  IF p_type='rate' AND NOT (p_payload ? 'valeur') THEN RAISE EXCEPTION 'payload.valeur requis'; END IF;
  IF p_type='bracket' AND NOT (p_payload ? 'taux') THEN RAISE EXCEPTION 'payload.taux requis'; END IF;
  INSERT INTO regulatory_change(type, cible_code, payload, date_effet, source, note, propose_par)
  VALUES (p_type, p_cible, p_payload, p_date_effet, btrim(p_source), p_note, p_actor)
  RETURNING id INTO v_id;
  INSERT INTO security_event(user_id, type, detail)
  VALUES (p_actor, 'reg_change_proposed', jsonb_build_object('change', v_id, 'cible', p_cible));
  RETURN v_id;
END; $$;
REVOKE ALL ON FUNCTION reg_change_propose(uuid,text,text,jsonb,date,text,text) FROM PUBLIC;

-- Validation (4-yeux : le valideur ≠ le proposeur). Statut 'validee'.
CREATE OR REPLACE FUNCTION reg_change_validate(p_actor uuid, p_change uuid)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_prop uuid; v_statut text;
BEGIN
  SELECT propose_par, statut INTO v_prop, v_statut FROM regulatory_change WHERE id = p_change;
  IF v_prop IS NULL THEN RAISE EXCEPTION 'Proposition introuvable'; END IF;
  IF v_statut <> 'proposee' THEN RAISE EXCEPTION 'Seule une proposition en attente peut être validée'; END IF;
  IF v_prop = p_actor THEN RAISE EXCEPTION 'Séparation des tâches : le valideur doit être différent du proposeur.'; END IF;
  UPDATE regulatory_change SET statut='validee', valide_par=p_actor, validated_at=now() WHERE id=p_change;
  INSERT INTO security_event(user_id, type, detail) VALUES (p_actor, 'reg_change_validated', jsonb_build_object('change', p_change));
  RETURN 'validee';
END; $$;
REVOKE ALL ON FUNCTION reg_change_validate(uuid,uuid) FROM PUBLIC;

CREATE OR REPLACE FUNCTION reg_change_reject(p_actor uuid, p_change uuid, p_note text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  UPDATE regulatory_change SET statut='rejetee', valide_par=p_actor, validated_at=now(),
         note = coalesce(p_note, note) WHERE id=p_change AND statut IN ('proposee','validee');
  IF NOT FOUND THEN RAISE EXCEPTION 'Proposition non rejetable'; END IF;
  INSERT INTO security_event(user_id, type, detail) VALUES (p_actor, 'reg_change_rejected', jsonb_build_object('change', p_change));
  RETURN 'rejetee';
END; $$;
REVOKE ALL ON FUNCTION reg_change_reject(uuid,uuid,text) FROM PUBLIC;

-- Publication : applique la version datée au référentiel (insert, non destructif). Statut 'publiee'.
CREATE OR REPLACE FUNCTION reg_change_publish(p_actor uuid, p_change uuid)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE c regulatory_change%ROWTYPE;
BEGIN
  SELECT * INTO c FROM regulatory_change WHERE id = p_change;
  IF c.id IS NULL THEN RAISE EXCEPTION 'Proposition introuvable'; END IF;
  IF c.statut <> 'validee' THEN RAISE EXCEPTION 'Seule une proposition VALIDÉE peut être publiée.'; END IF;
  IF c.type = 'rate' THEN
    INSERT INTO rate_table(code, valeur, date_effet, source)
    VALUES (c.cible_code, (c.payload->>'valeur')::numeric, c.date_effet, c.source);
  ELSE
    INSERT INTO tax_bracket(table_code, tranche_min, tranche_max, taux, date_effet, source)
    VALUES (c.cible_code, (c.payload->>'tranche_min')::numeric, nullif(c.payload->>'tranche_max','')::numeric,
            (c.payload->>'taux')::numeric, c.date_effet, c.source);
  END IF;
  UPDATE regulatory_change SET statut='publiee', published_at=now() WHERE id=p_change;
  INSERT INTO security_event(user_id, type, detail)
  VALUES (p_actor, 'reg_change_published', jsonb_build_object('change', p_change, 'cible', c.cible_code, 'date_effet', c.date_effet));
  RETURN 'publiee';
END; $$;
REVOKE ALL ON FUNCTION reg_change_publish(uuid,uuid) FROM PUBLIC;
