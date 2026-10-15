#!/usr/bin/env bash
# Applique les migrations WaSalaire de façon REJOUABLE (idempotente au niveau fichier).
#
# Chaque fichier de migrations/sql/*.sql est appliqué UNE SEULE FOIS, dans une transaction,
# puis enregistré dans la table de suivi `schema_migrations` (nom + empreinte sha256).
# Un second passage saute les fichiers déjà appliqués. Un fichier historique modifié après
# application est refusé (empreinte différente), pour préserver la traçabilité (jamais de
# réécriture destructive d'une migration déjà jouée : ajouter un nouveau fichier numéroté).
#
# Usage : variables PG* en environnement (superuser pour la migration), puis ./run_migrations.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")/sql" && pwd)"

# 0) Table de suivi des migrations (créée une fois, idempotent).
psql -v ON_ERROR_STOP=1 -q <<'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    text PRIMARY KEY,
    checksum    text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
);
SQL

# 1) Application ordonnée, une fois par fichier.
for f in "$DIR"/*.sql; do
  base="$(basename "$f")"
  sum="$(sha256sum "$f" | awk '{print $1}')"
  applied="$(psql -tAqc "SELECT checksum FROM schema_migrations WHERE filename='${base}'")"
  if [ -z "$applied" ]; then
    echo ">> migration ${base} (application)"
    # Fichier + enregistrement dans la MÊME transaction : si le fichier échoue, rien n'est marqué.
    psql -v ON_ERROR_STOP=1 --single-transaction -f "$f" \
      -c "INSERT INTO schema_migrations(filename, checksum) VALUES ('${base}', '${sum}')"
  elif [ "$applied" != "$sum" ]; then
    echo "!! ERREUR : ${base} a été modifié après application (empreinte différente)." >&2
    echo "!! Une migration jouée est immuable : créez un nouveau fichier numéroté." >&2
    exit 1
  else
    echo ">> migration ${base} (déjà appliquée, ignorée)"
  fi
done

# 2) Rôle applicatif + privilèges (idempotent, rejoué à chaque fois pour couvrir les tables neuves).
echo ">> rôle applicatif (scope-RLS)"
APP_PWD="${WASALAIRE_DB_PASSWORD:-change-me-in-prod}"
psql -v ON_ERROR_STOP=1 -q <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='wasalaire_app') THEN
    CREATE ROLE wasalaire_app LOGIN PASSWORD '${APP_PWD}';
  ELSE
    ALTER ROLE wasalaire_app LOGIN PASSWORD '${APP_PWD}';
  END IF;
END \$\$;
GRANT USAGE ON SCHEMA public TO wasalaire_app;
-- Moindre privilège (P1-08) : SELECT/INSERT/UPDATE par défaut (jamais DELETE : soft-delete),
-- puis restrictions ciblées. Couvre aussi les tables neuves (défaut sûr), le référentiel
-- restant en lecture seule et l'audit en écriture seule.
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO wasalaire_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO wasalaire_app;
-- Référentiel réglementaire : lecture seule (aucune écriture par le runtime).
REVOKE INSERT, UPDATE ON rate_table, tax_bracket, regulatory_rule, role FROM wasalaire_app;
-- Journal d'audit : écriture seule (le runtime n'a pas à relire ni modifier l'audit).
REVOKE SELECT, UPDATE ON audit_log FROM wasalaire_app;
-- Table de suivi des migrations : hors de portée du runtime.
REVOKE ALL ON schema_migrations FROM wasalaire_app;
-- Accès transverse super-admin (migration 010) : exécuter la fonction SECURITY DEFINER.
DO \$do\$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='all_company_ids') THEN
    GRANT EXECUTE ON FUNCTION all_company_ids() TO wasalaire_app;
  END IF;
  -- Onboarding in-app (migration 011) : création de société + liste des nœuds admin.
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='create_company_under_node') THEN
    GRANT EXECUTE ON FUNCTION create_company_under_node(uuid, uuid, text, text) TO wasalaire_app;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='admin_nodes') THEN
    GRANT EXECUTE ON FUNCTION admin_nodes(uuid) TO wasalaire_app;
  END IF;
  -- Back-office ADMIN interne (migration 013) : lectures transverses + set rôle + audit.
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='admin_overview') THEN
    GRANT EXECUTE ON FUNCTION admin_overview() TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION admin_organizations() TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION admin_internal_users() TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION admin_set_platform_role(uuid, uuid, text) TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION admin_audit(int) TO wasalaire_app;
  END IF;
  -- Workflow référentiels réglementaires (migration 014).
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='reg_change_publish') THEN
    GRANT EXECUTE ON FUNCTION reg_referentials_read() TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION reg_changes_list() TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION reg_change_propose(uuid,text,text,jsonb,date,text,text) TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION reg_change_validate(uuid,uuid) TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION reg_change_reject(uuid,uuid,text) TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION reg_change_publish(uuid,uuid) TO wasalaire_app;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='regulatory_change') THEN
    GRANT SELECT, INSERT, UPDATE ON regulatory_change TO wasalaire_app;
  END IF;
END \$do\$;
SQL

echo ">> Migrations appliquées. L'application se connecte avec le rôle wasalaire_app (RLS active)."
