-- =====================================================================
-- 010 — Accès transverse super-admin plateforme.
-- `all_company_ids()` : liste TOUTES les sociétés hors RLS, via SECURITY DEFINER
-- (exécutée avec les droits du propriétaire = superuser de migration). Sert UNIQUEMENT
-- à poser le périmètre d'un super-admin (break-glass tracé) ; ne renvoie que des UUID.
-- L'isolation RLS reste la règle pour tous les autres accès.
-- =====================================================================
CREATE OR REPLACE FUNCTION all_company_ids() RETURNS uuid[]
LANGUAGE sql SECURITY DEFINER SET search_path = public STABLE AS $$
  SELECT coalesce(array_agg(id), '{}'::uuid[]) FROM company WHERE deleted_at IS NULL;
$$;
REVOKE ALL ON FUNCTION all_company_ids() FROM PUBLIC;
-- EXECUTE est accordé à wasalaire_app par run_migrations.sh (section rôle, après création du rôle).
