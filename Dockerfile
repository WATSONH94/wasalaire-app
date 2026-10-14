# WaSalaire — image de production (Coolify/Traefik). Multi-stage : build du front React,
# puis runtime API Python qui sert aussi le SPA (même origine, aucune URL codée en dur).

# ── Stage 1 : build du front React/Vite ──
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2 : runtime API (FastAPI) + SPA ──
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8

# psql pour exécuter les migrations au démarrage (entrypoint).
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Le build React est servi par l'API depuis ./webdist (cf. api_v2 : _WEBDIST).
COPY --from=web /web/dist ./webdist
RUN chmod +x entrypoint.sh migrations/run_migrations.sh

EXPOSE 8000
# Migrations (superuser) puis API (rôle applicatif non-privilégié) — cf. entrypoint.sh.
ENTRYPOINT ["./entrypoint.sh"]
