#!/usr/bin/env bash
# =====================================================================
# Runner de recette WaSalaire (P08 / R14) : ISOLATION STRICTE et rejouable.
#
#  - Tests de calcul purs : executes sans base.
#  - Tests DB : chaque test s'execute sur SA PROPRE base, clonee a partir d'une
#    base template migree une seule fois (CREATE DATABASE ... TEMPLATE, rapide).
#    La base du test est supprimee apres. Chaque test part donc d'un etat propre :
#    plus aucune collision de fixtures entre tests (ni au rejeu), y compris sur
#    role.code='admin' (ecart workspace_pkey / role_code_key definitivement leve).
#  - Code de sortie != 0 des qu'un test echoue -> CI rouge.
#  - Retry unique sur erreur d'infrastructure (coupure/arret serveur), pour
#    tolerer un moteur Docker instable sans masquer un vrai echec de test.
#
# Connexion superuser : variables PG* (PGHOST/PGPORT/PGUSER/PGPASSWORD).
# psql de provisioning : binaire local s'il existe, sinon `docker exec` dans
#   le conteneur $WASALAIRE_TEST_DB_CONTAINER (defaut: wasalaire-test-db).
# =====================================================================
set -uo pipefail
cd "$(dirname "$0")"

export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
PGHOST="${PGHOST:-127.0.0.1}"; PGPORT="${PGPORT:-5546}"
PGUSER="${PGUSER:-postgres}"; PGPASSWORD="${PGPASSWORD:-wasa_test_pwd}"
export PGHOST PGPORT PGUSER PGPASSWORD
CONTAINER="${WASALAIRE_TEST_DB_CONTAINER:-wasalaire-test-db}"
TMPL="${WASALAIRE_TMPL_DB:-wasalaire_tmpl}"
APP_PWD="${WASALAIRE_DB_PASSWORD:-wasa_app_pwd}"

PURE=(test_scenarios test_modules test_rupture_rg test_controles test_rubriques
      test_ortb test_13m_avance test_r11_r12 test_r07_hardening test_r15_r16_amo)
DBT=(test_p0_guards test_r09_immutable test_withcheck test_rh_temporal
     test_governance test_ruleset test_storage test_payout_amount test_v3
     test_security test_redteam test_declaratif test_onboarding test_accounts
     test_platform)

filter(){ grep -viE "wsl: Failed to translate"; }
have_local_psql(){ command -v psql >/dev/null 2>&1; }
psql_on(){ local db="$1"
  if have_local_psql; then psql -v ON_ERROR_STOP=1 -q -d "$db"
  else docker exec -i "$CONTAINER" psql -U "$PGUSER" -d "$db" -v ON_ERROR_STOP=1 -q; fi; }
db_ready(){
  if have_local_psql; then pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" >/dev/null 2>&1
  else docker exec "$CONTAINER" pg_isready -U "$PGUSER" >/dev/null 2>&1; fi; }
ensure_up(){ db_ready && return 0; docker start "$CONTAINER" >/dev/null 2>&1 || true
  for _ in $(seq 1 20); do db_ready && return 0; sleep 1; done
  echo "ERREUR : PostgreSQL indisponible"; return 1; }

provision_template(){
  echo ">> base template '$TMPL' (migrations + role, une seule fois)"
  echo "DROP DATABASE IF EXISTS $TMPL;" | psql_on postgres 2>&1 | filter
  echo "CREATE DATABASE $TMPL;"         | psql_on postgres 2>&1 | filter
  for f in $(ls migrations/sql/*.sql | sort); do
    psql_on "$TMPL" < "$f" >/dev/null 2>&1 || { echo "   [ERR migration] $(basename "$f")"; return 1; }
  done
  psql_on "$TMPL" >/dev/null 2>&1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='wasalaire_app') THEN
    CREATE ROLE wasalaire_app LOGIN PASSWORD '${APP_PWD}';
  ELSE ALTER ROLE wasalaire_app LOGIN PASSWORD '${APP_PWD}'; END IF;
END \$\$;
GRANT wasalaire_app TO ${PGUSER};
GRANT USAGE ON SCHEMA public TO wasalaire_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO wasalaire_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO wasalaire_app;
REVOKE INSERT, UPDATE ON rate_table, tax_bracket, regulatory_rule, role FROM wasalaire_app;
REVOKE SELECT, UPDATE ON audit_log FROM wasalaire_app;
DO \$do\$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='all_company_ids') THEN GRANT EXECUTE ON FUNCTION all_company_ids() TO wasalaire_app; END IF;
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='create_company_under_node') THEN GRANT EXECUTE ON FUNCTION create_company_under_node(uuid,uuid,text,text) TO wasalaire_app; END IF;
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='admin_nodes') THEN GRANT EXECUTE ON FUNCTION admin_nodes(uuid) TO wasalaire_app; END IF;
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='admin_overview') THEN
    GRANT EXECUTE ON FUNCTION admin_overview() TO wasalaire_app; GRANT EXECUTE ON FUNCTION admin_organizations() TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION admin_internal_users() TO wasalaire_app; GRANT EXECUTE ON FUNCTION admin_set_platform_role(uuid,uuid,text) TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION admin_audit(int) TO wasalaire_app; END IF;
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='reg_change_publish') THEN
    GRANT EXECUTE ON FUNCTION reg_referentials_read() TO wasalaire_app; GRANT EXECUTE ON FUNCTION reg_changes_list() TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION reg_change_propose(uuid,text,text,jsonb,date,text,text) TO wasalaire_app; GRANT EXECUTE ON FUNCTION reg_change_validate(uuid,uuid) TO wasalaire_app;
    GRANT EXECUTE ON FUNCTION reg_change_reject(uuid,uuid,text) TO wasalaire_app; GRANT EXECUTE ON FUNCTION reg_change_publish(uuid,uuid) TO wasalaire_app; END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='regulatory_change') THEN GRANT SELECT, INSERT, UPDATE ON regulatory_change TO wasalaire_app; END IF;
END \$do\$;
SQL
  echo "   template pret"
}

is_infra_err(){ echo "$1" | grep -qiE "shutting down|starting up|connection to server|server closed|could not connect|the database system is"; }

PASS=0; FAIL=0; declare -a FAILED=()
run_pure(){ local t="$1"; [ -f "$t.py" ] || { echo "   [SKIP] $t"; return; }
  local out code; out=$(python "$t.py" 2>&1 | filter); code=${PIPESTATUS[0]}
  local s; s=$(echo "$out" | grep -iE "PASS|RÉSULTAT|RESULT|OK|écart|erreur" | tail -1)
  if [ "$code" -eq 0 ]; then echo "   [PASS] $t :: $s"; PASS=$((PASS+1))
  else echo "   [FAIL] $t (exit $code)"; FAILED+=("$t"); FAIL=$((FAIL+1)); fi; }

run_db(){ local t="$1"; [ -f "$t.py" ] || { echo "   [SKIP] $t"; return; }
  local db="wct_$t" out code attempt=0
  while :; do attempt=$((attempt+1))
    ensure_up || { out="DB indisponible"; code=1; }
    if [ "${code:-0}" -ne 1 ] || [ -z "${out:-}" ]; then
      echo "DROP DATABASE IF EXISTS $db;" | psql_on postgres >/dev/null 2>&1
      echo "CREATE DATABASE $db TEMPLATE $TMPL;" | psql_on postgres >/dev/null 2>&1
      out=$(PGDATABASE="$db" python "$t.py" 2>&1 | filter); code=${PIPESTATUS[0]}
      echo "DROP DATABASE IF EXISTS $db;" | psql_on postgres >/dev/null 2>&1
    fi
    if [ "$code" -ne 0 ] && is_infra_err "$out" && [ "$attempt" -lt 2 ]; then
      echo "   [retry] $t (coupure infra, nouvelle tentative)"; sleep 3; continue; fi
    break
  done
  local s; s=$(echo "$out" | grep -iE "PASS|RÉSULTAT|RESULT|OK|écart|erreur" | tail -1)
  if [ "$code" -eq 0 ]; then echo "   [PASS] $t :: $s"; PASS=$((PASS+1))
  else echo "   [FAIL] $t (exit $code) :: $(echo "$out" | tail -1)"; FAILED+=("$t"); FAIL=$((FAIL+1)); fi; }

echo "=== TESTS DE CALCUL PURS ==="
for t in "${PURE[@]}"; do run_pure "$t"; done
echo "=== TESTS BASE (une base clonee par test, isolee) ==="
ensure_up || exit 2
provision_template || exit 2
for t in "${DBT[@]}"; do run_db "$t"; done
echo "DROP DATABASE IF EXISTS $TMPL;" | psql_on postgres 2>&1 | filter
echo ""
echo "===================================================================="
echo "RESULTAT GLOBAL : $PASS reussi(s), $FAIL echec(s)"
[ "$FAIL" -ne 0 ] && { echo "ECHECS : ${FAILED[*]}"; exit 1; }
echo "SUITE VERTE."
exit 0
