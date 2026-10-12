#!/usr/bin/env bash
# Sauvegarde WaSalaire (P1-16) : dump PostgreSQL compressé, horodaté, avec rétention.
# Usage : variables PG* (ou PGHOST/PGUSER/PGDATABASE) en environnement.
#   BACKUP_DIR (défaut ./backups), RETENTION_DAYS (défaut 14).
# Chiffrement : si BACKUP_GPG_RECIPIENT est défini, le dump est chiffré GPG.
# ⚠️ À planifier (cron/systemd timer) ET à stocker HORS SITE. Tester la restauration.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DB="${PGDATABASE:-wasalaire}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
OUT="$BACKUP_DIR/wasalaire-${DB}-${STAMP}.dump"

echo ">> dump $DB -> $OUT (format custom, compressé)"
pg_dump --format=custom --compress=9 --file="$OUT" "$DB"

if [ -n "${BACKUP_GPG_RECIPIENT:-}" ]; then
  echo ">> chiffrement GPG ($BACKUP_GPG_RECIPIENT)"
  gpg --yes --encrypt --recipient "$BACKUP_GPG_RECIPIENT" "$OUT"
  rm -f "$OUT"
  OUT="$OUT.gpg"
fi

echo ">> empreinte"
sha256sum "$OUT" > "$OUT.sha256"

echo ">> purge des sauvegardes de plus de $RETENTION_DAYS jours"
find "$BACKUP_DIR" -name "wasalaire-*.dump*" -type f -mtime +"$RETENTION_DAYS" -delete || true

echo ">> OK : $OUT"
