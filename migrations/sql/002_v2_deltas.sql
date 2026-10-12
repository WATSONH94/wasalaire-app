-- =====================================================================
-- WaSalaire — Deltas v2 « mobile-first / multi-surface »
-- À appliquer APRÈS 16/schema.sql. Traduit les décisions de
-- 15/architecture-cible-mobile-first.md :
--   D4 hiérarchie complète (arbre + closure)   D5 scope-RLS (ensemble autorisé)
--   D6 identité téléphone + OTP                 D7 décaissement multi-méthode
--   + payroll_campaign (pilotage multi-sociétés)
--
-- ✅ VALIDÉ sur PostgreSQL 17.6 (20/09/2026) : chargement OK ; scope-RLS testé
--    (cabinet voit N sociétés, DRH groupe voit son sous-arbre, RH voit 1 société,
--     mono-société n'a accès à aucune autre) ; immuabilité/audit hérités du base.
-- =====================================================================

-- ---------- D4 : arbre organisationnel typé + closure table ----------
CREATE TABLE org_node (
    id         uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id  uuid NOT NULL REFERENCES workspace(id),
    type       text NOT NULL CHECK (type IN
               ('cabinet','client','groupe','societe','etablissement','service')),
    parent_id  uuid REFERENCES org_node(id),
    nom        text NOT NULL,
    company_id uuid REFERENCES company(id),      -- renseigné ssi type='societe'
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((type = 'societe') = (company_id IS NOT NULL))   -- 1 nœud société <-> 1 company
);
CREATE INDEX idx_orgnode_parent  ON org_node(parent_id);
CREATE INDEX idx_orgnode_company ON org_node(company_id);

-- Closure : (ancêtre, descendant, profondeur) — chaque nœud est son propre ancêtre (depth 0)
CREATE TABLE org_closure (
    ancestor_id   uuid NOT NULL REFERENCES org_node(id),
    descendant_id uuid NOT NULL REFERENCES org_node(id),
    depth         int  NOT NULL,
    PRIMARY KEY (ancestor_id, descendant_id)
);

-- Maintien automatique de la closure à l'insertion d'un nœud
CREATE OR REPLACE FUNCTION org_node_maintain_closure() RETURNS trigger AS $$
BEGIN
    -- self-link
    INSERT INTO org_closure(ancestor_id, descendant_id, depth)
    VALUES (NEW.id, NEW.id, 0);
    -- liens depuis tous les ancêtres du parent
    IF NEW.parent_id IS NOT NULL THEN
        INSERT INTO org_closure(ancestor_id, descendant_id, depth)
        SELECT c.ancestor_id, NEW.id, c.depth + 1
        FROM org_closure c
        WHERE c.descendant_id = NEW.parent_id;
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_orgnode_closure AFTER INSERT ON org_node
    FOR EACH ROW EXECUTE FUNCTION org_node_maintain_closure();

-- ---------- D5 : droits d'accès par nœud + scope-RLS ----------
-- (access_grant remplace le besoin d'un membership mono-société pour le multi-dossiers)
CREATE TABLE access_grant (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     uuid NOT NULL REFERENCES app_user(id),
    org_node_id uuid NOT NULL REFERENCES org_node(id),
    role_id     uuid NOT NULL REFERENCES role(id),
    date_debut  date NOT NULL DEFAULT current_date,
    date_fin    date
);
CREATE INDEX idx_grant_user ON access_grant(user_id);

-- Ensemble des sociétés autorisées pour un utilisateur (via sous-arbre de ses grants)
CREATE OR REPLACE FUNCTION authorized_companies(p_user uuid) RETURNS uuid[] AS $$
    SELECT coalesce(array_agg(DISTINCT n.company_id), '{}'::uuid[])
    FROM access_grant g
    JOIN org_closure c ON c.ancestor_id = g.org_node_id
    JOIN org_node   n ON n.id = c.descendant_id AND n.type = 'societe'
    WHERE g.user_id = p_user
      AND (g.date_fin IS NULL OR g.date_fin >= current_date);
$$ LANGUAGE sql STABLE;

-- Lecture du périmètre courant (posé par l'app : SET app.authorized_companies = '{...}')
CREATE OR REPLACE FUNCTION current_scope() RETURNS uuid[] AS $$
    SELECT coalesce(nullif(current_setting('app.authorized_companies', true), '')::uuid[],
                    '{}'::uuid[]);
$$ LANGUAGE sql STABLE;

-- Remplace la RLS mono-société (app.current_company) par la scope-RLS (ensemble autorisé)
DROP POLICY IF EXISTS tenant_isolation ON company;
CREATE POLICY tenant_scope ON company
    USING (id = ANY (current_scope()));

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'establishment','department','position','employee','dependent',
    'contract','pay_element','payroll_period','payroll_run','payslip',
    'payslip_line','calc_snapshot','variable','declaration','accounting_entry']
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I;', t);
    EXECUTE format($p$
      CREATE POLICY tenant_scope ON %I
        USING (company_id = ANY (current_scope()));
    $p$, t);
  END LOOP;
END $$;

-- ---------- D6 : identité mobile-first (téléphone + OTP) ----------
ALTER TABLE app_user ADD COLUMN telephone          text;   -- E.164, ex +229xxxxxxxx
ALTER TABLE app_user ADD COLUMN telephone_verifie  boolean NOT NULL DEFAULT false;
ALTER TABLE app_user ALTER COLUMN email DROP NOT NULL;      -- email désormais optionnel
CREATE UNIQUE INDEX uq_user_tel ON app_user(telephone) WHERE telephone IS NOT NULL;

CREATE TABLE otp_challenge (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     uuid REFERENCES app_user(id),
    telephone   text NOT NULL,
    canal       text NOT NULL CHECK (canal IN ('sms','whatsapp')),
    code_hash   text NOT NULL,                    -- jamais le code en clair
    tentatives  int  NOT NULL DEFAULT 0,
    expire_at   timestamptz NOT NULL,
    consomme_at timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------- Résultat de calcul figé sur le bulletin (déclarations / décaissement / contrôles) ----------
ALTER TABLE payslip ADD COLUMN resultat jsonb;   -- dict complet du moteur (its, cnss_sal/pat, vps, amo, net…)

-- ---------- payroll_campaign : pilotage multi-sociétés (client / groupe) ----------
CREATE TABLE payroll_campaign (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_node_id uuid NOT NULL REFERENCES org_node(id),   -- client ou groupe
    mois        int  NOT NULL CHECK (mois BETWEEN 1 AND 12),
    annee       int  NOT NULL,
    statut      text NOT NULL DEFAULT 'en_cours'
                CHECK (statut IN ('en_cours','cloturee')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_node_id, annee, mois)
);
ALTER TABLE payroll_run ADD COLUMN campaign_id uuid REFERENCES payroll_campaign(id);

-- ---------- D7 : décaissement multi-méthode ----------
CREATE TYPE payout_method AS ENUM ('especes','virement','mobile_money','cheque');

ALTER TABLE employee ADD COLUMN methode_paiement payout_method NOT NULL DEFAULT 'especes';
ALTER TABLE employee ADD COLUMN momo_operateur   text CHECK (momo_operateur IN ('MTN','MOOV'));
ALTER TABLE employee ADD COLUMN momo_numero      text;   -- E.164
ALTER TABLE employee ADD COLUMN iban             text;   -- virement (distinct du mobile money)

CREATE TABLE payout_batch (
    id         uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    run_id     uuid NOT NULL REFERENCES payroll_run(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE payout_item (
    id             uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id     uuid NOT NULL REFERENCES company(id),
    batch_id       uuid NOT NULL REFERENCES payout_batch(id),
    employee_id    uuid NOT NULL REFERENCES employee(id),
    methode        payout_method NOT NULL,
    montant        numeric(14,2) NOT NULL CHECK (montant >= 0),
    cle_idempotence text NOT NULL UNIQUE,          -- mouvement d'argent = idempotent
    statut         text NOT NULL DEFAULT 'a_envoyer'
                   CHECK (statut IN ('a_envoyer','envoye','confirme','echoue')),
    reference_operateur text,
    accuse         jsonb
);
CREATE INDEX idx_payout_item_batch ON payout_item(batch_id);

-- Scope-RLS sur les nouvelles tables porteuses de company_id
ALTER TABLE payout_batch ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON payout_batch USING (company_id = ANY (current_scope()));
ALTER TABLE payout_item  ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON payout_item  USING (company_id = ANY (current_scope()));
