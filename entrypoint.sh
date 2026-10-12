#!/usr/bin/env bash
# Démarrage production WaSalaire (Coolify, derrière Traefik).
# 1) Migrations appliquées avec le rôle SUPERUSER (création du rôle applicatif, schéma, RLS).
# 2) API démarrée avec le rôle APPLICATIF non-privilégié (RLS réellement appliquée).
set -euo pipefail

echo "[entrypoint] Application des migrations (superuser)…"
PGUSER="${POSTGRES_SUPERUSER:-postgres}" \
PGPASSWORD="${POSTGRES_SUPERPASSWORD:?POSTGRES_SUPERPASSWORD requis}" \
PGHOST="${PGHOST:?PGHOST requis}" PGPORT="${PGPORT:-5432}" PGDATABASE="${PGDATABASE:?PGDATABASE requis}" \
WASALAIRE_DB_PASSWORD="${WASALAIRE_DB_PASSWORD:?WASALAIRE_DB_PASSWORD requis}" \
  bash migrations/run_migrations.sh

echo "[entrypoint] Démarrage de l'API (uvicorn) en rôle applicatif…"
exec uvicorn api_v2:app --host 0.0.0.0 --port 8000
