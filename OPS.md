# Runbook d'exploitation - WaSalaire

Ce document couvre la partie exploitation (gate J de l'audit) : déploiement durci,
sauvegarde, restauration, supervision. Il fournit le code et les procédures ; la mise
en oeuvre effective (hébergeur, domaine, secrets réels, sauvegardes hors site qui
tournent) reste à provisionner par l'exploitant.

## 1. Déploiement durci (TLS)

Local / test (API exposée en clair sur 8000) :

    WASALAIRE_SECRET=<32+ car.> docker compose up -d

Production (reverse-proxy Caddy, HTTPS automatique Let's Encrypt) :

    export WASALAIRE_SECRET=<secret fort en coffre, >=16 car.>
    export WASALAIRE_DOMAIN=paie.exemple.bj   # doit pointer (DNS A/AAAA) sur l'hôte
    export WASALAIRE_ORIGINS=https://paie.exemple.bj
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

Garde-fous actifs : l'API refuse de démarrer en prod avec un secret faible (fail-closed) ;
elle tourne en rôle DB non-superuser (RLS appliquée) ; CORS nominatif ; healthcheck sur
`/health` (API et conteneur).

## 2. Secrets

- `WASALAIRE_SECRET` : signature des jetons. Fort (>=16 car.), en coffre, jamais committé.
- `WASALAIRE_DB_PASSWORD` : mot de passe du rôle applicatif `wasalaire_app`.
- `POSTGRES_PASSWORD` : superuser DB (migrations uniquement).
- Intégrations : `FEDAPAY_SECRET_KEY`, `WHATSAPP_TOKEN` + `WHATSAPP_PHONE_ID`, `SMS_API_KEY`.
- Fournir via `.env` (exclu par `.gitignore` et `.dockerignore`) ou le coffre de l'hébergeur.

## 3. Sauvegarde

    BACKUP_DIR=/var/backups/wasalaire RETENTION_DAYS=14 \
    BACKUP_GPG_RECIPIENT=<clé> bash scripts/backup_db.sh

- Dump `pg_dump` format custom compressé + empreinte sha256, chiffrement GPG optionnel.
- À planifier (cron/systemd timer), par exemple quotidien, et à répliquer HORS SITE.
- Le volume Docker `pgdata` n'est PAS une sauvegarde.

Exemple cron (02h00) :

    0 2 * * * cd /opt/wasalaire/23-PROTOTYPE-MOTEUR && BACKUP_DIR=/var/backups/wasalaire \
      BACKUP_GPG_RECIPIENT=ops@exemple.bj bash scripts/backup_db.sh >> /var/log/wasalaire-backup.log 2>&1

## 4. Restauration (à tester régulièrement)

    bash scripts/restore_db.sh /var/backups/wasalaire/wasalaire-...dump.gpg wasalaire_restore_test

Un exercice de restauration doit être exécuté périodiquement (preuve de reprise). Vérifier
le nombre de lignes des tables clés affiché en fin de script.

## 5. Objectifs de continuité (à arbitrer)

- RPO cible proposé : <= 24 h (sauvegarde quotidienne) ; <= 15 min avec archivage WAL / PITR managé.
- RTO cible proposé : <= 2 h (restauration + redéploiement).
- Pour un RPO court : activer l'archivage WAL ou une base managée avec PITR.

## 6. Supervision

- Sonde `/health` (200 = OK, 503 = base indisponible) : brancher sur le monitoring de l'hébergeur.
- Alerting proposé : indisponibilité `/health`, échec du job de sauvegarde, erreurs 5xx,
  anomalies bloquantes de paie, échecs de décaissement.
- Journaux : éviter toute donnée personnelle dans les logs applicatifs.

## 7. Reste à faire (hors code)

Sauvegardes qui tournent réellement + stockage hors site chiffré ; PITR/WAL si RPO court ;
exercices de restauration planifiés ; alerting branché ; rotation des secrets ; scan
d'images et de dépendances en CI (SBOM/CVE). Ces points relèvent de l'infrastructure de
l'exploitant, pas du dépôt applicatif.
