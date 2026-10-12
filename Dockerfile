# WaSalaire API v2 — image de production (déploiement Coolify derrière Traefik).
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8

# psql pour exécuter les migrations au démarrage (entrypoint).
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh migrations/run_migrations.sh

EXPOSE 8000
# Migrations (superuser) puis API (rôle applicatif non-privilégié) — cf. entrypoint.sh.
ENTRYPOINT ["./entrypoint.sh"]
