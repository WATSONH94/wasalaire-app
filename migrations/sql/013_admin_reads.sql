-- 013 — Fonctions de LECTURE du back-office ADMIN (interne WaSalaire).
-- Elles traversent toutes les organisations (vue éditeur), donc SECURITY DEFINER pour
-- s'affranchir de la RLS tenant. L'AUTORISATION reste contrôlée côté API (require_internal),
-- et l'EXECUTE n'est accordé qu'au rôle applicatif. Lecture seule, aucun secret exposé.

-- Vue d'ensemble plateforme (compteurs réels).
CREATE OR REPLACE FUNCTION admin_overview()
RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path = public STABLE
AS $$
  SELECT jsonb_build_object(
    'organizations',        (SELECT count(*) FROM workspace),
    'companies',            (SELECT count(*) FROM company WHERE deleted_at IS NULL),
    'establishments',       (SELECT count(*) FROM establishment),
    'users_active',         (SELECT count(*) FROM app_user WHERE statut = 'actif'),
    'internal_users',       (SELECT count(*) FROM app_user WHERE platform_role <> 'none'),
    'employees',            (SELECT count(*) FROM employee),
    'payslips',             (SELECT count(*) FROM payslip),
    'runs_total',           (SELECT count(*) FROM payroll_run),
    'subscriptions_active', (SELECT count(*) FROM subscription WHERE statut IN ('active','beta')),
    'subscriptions_total',  (SELECT count(*) FROM subscription)
  );
$$;
REVOKE ALL ON FUNCTION admin_overview() FROM PUBLIC;

-- Organisations clientes (abonnés) + plan + statut + nb sociétés.
CREATE OR REPLACE FUNCTION admin_organizations()
RETURNS TABLE (
  workspace_id uuid, nom text, type text, nb_companies bigint,
  plan text, statut text, is_beta boolean, created_at timestamptz
)
LANGUAGE sql SECURITY DEFINER SET search_path = public STABLE
AS $$
  SELECT w.id, w.nom, w.type,
         (SELECT count(*) FROM company c WHERE c.workspace_id = w.id AND c.deleted_at IS NULL),
         p.code, s.statut, s.is_beta, w.created_at
  FROM workspace w
  LEFT JOIN subscription s ON s.workspace_id = w.id
  LEFT JOIN plan p ON p.id = s.plan_id
  ORDER BY w.nom;
$$;
REVOKE ALL ON FUNCTION admin_organizations() FROM PUBLIC;

-- Utilisateurs INTERNES WaSalaire (profil éditeur) — pour l'écran « Utilisateurs internes ».
CREATE OR REPLACE FUNCTION admin_internal_users()
RETURNS TABLE (
  id uuid, email text, platform_role text, statut text,
  totp_enrolled boolean, must_change_password boolean, created_at timestamptz
)
LANGUAGE sql SECURITY DEFINER SET search_path = public STABLE
AS $$
  SELECT id, email, platform_role, statut, totp_enrolled, must_change_password, created_at
  FROM app_user
  WHERE platform_role <> 'none'
  ORDER BY email;
$$;
REVOKE ALL ON FUNCTION admin_internal_users() FROM PUBLIC;

-- Attribue / modifie le rôle interne d'un utilisateur (back-office). Contrôle d'autorisation
-- côté API (super_admin). Empêche de retirer le DERNIER super_admin (anti-lockout).
CREATE OR REPLACE FUNCTION admin_set_platform_role(p_actor uuid, p_user uuid, p_role text)
RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE v_old text; v_nb_super int;
BEGIN
  IF p_role NOT IN ('none','super_admin','admin_plateforme','support','conformite','commercial') THEN
    RAISE EXCEPTION 'Rôle interne inconnu : %', p_role;
  END IF;
  SELECT platform_role INTO v_old FROM app_user WHERE id = p_user;
  IF v_old IS NULL THEN RAISE EXCEPTION 'Utilisateur introuvable'; END IF;
  IF v_old = 'super_admin' AND p_role <> 'super_admin' THEN
    SELECT count(*) INTO v_nb_super FROM app_user WHERE platform_role = 'super_admin';
    IF v_nb_super <= 1 THEN
      RAISE EXCEPTION 'Impossible de retirer le dernier super-administrateur.';
    END IF;
  END IF;
  UPDATE app_user SET platform_role = p_role WHERE id = p_user;
  INSERT INTO security_event (user_id, type, detail)
  VALUES (p_actor, 'platform_role_changed',
          jsonb_build_object('cible', p_user, 'ancien', v_old, 'nouveau', p_role));
  RETURN p_role;
END;
$$;
REVOKE ALL ON FUNCTION admin_set_platform_role(uuid, uuid, text) FROM PUBLIC;

-- Journal d'audit interne (événements de sécurité récents).
CREATE OR REPLACE FUNCTION admin_audit(p_limit int DEFAULT 100)
RETURNS TABLE (id uuid, user_id uuid, email text, type text, ip text, detail jsonb, created_at timestamptz)
LANGUAGE sql SECURITY DEFINER SET search_path = public STABLE
AS $$
  SELECT id, user_id, email, type, host(ip)::text, detail, created_at
  FROM security_event
  ORDER BY created_at DESC
  LIMIT greatest(1, least(p_limit, 500));
$$;
REVOKE ALL ON FUNCTION admin_audit(int) FROM PUBLIC;
