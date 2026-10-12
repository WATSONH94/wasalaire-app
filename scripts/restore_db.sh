#!/usr/bin/env bash
# Restauration WaSalaire (P1-16) : recharge un dump dans une base CIBLE.
# Usage : ./restore_db.sh <fichier.dump[.gpg]> [base_cible]
#   PG* en environnement. La base cible est créée si absente.
# ⚠️ Exécuter un exercice de restauration régulièrement (preuve de reprise, RTO/RPO).
set -euo pipefail

SRC="${1:?Usage: restore_db.sh <fichier.dump[.gpg]> [base_cible]}"
TARGET="${2:-wasalaire_restore_test}"

TMP="$SRC"
if [[ "$SRC" == *.gpg ]]; then
  TMP="${SRC%.gpg}"
  echo ">> déchiffrement GPG"
  gpg --yes --decrypt --output "$TMP" "$SRC"
fi

echo ">> (re)création de la base cible $TARGET"
psql -d postgres -c "DROP DATABASE IF EXISTS \"$TARGET\";"
psql -d postgres -c "CREATE DATABASE \"$TARGET\";"

echo ">> restauration dans $TARGET"
pg_restore --no-owner --dbname="$TARGET" "$TMP"

echo ">> vérification rapide (quelques tables clés)"
psql -d "$TARGET" -c "SELECT 'company' t, count(*) FROM company UNION ALL \
SELECT 'payslip', count(*) FROM payslip UNION ALL SELECT 'audit_log', count(*) FROM audit_log;"

echo ">> OK : restauré dans $TARGET"
