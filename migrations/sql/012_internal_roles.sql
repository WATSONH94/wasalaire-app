-- 012 — Rôles INTERNES WaSalaire (éditeur du SaaS), distincts des rôles d'organisation cliente.
-- platform_role décrit le profil INTERNE d'un collaborateur WaSalaire (back-office Admin).
-- Les rôles CLIENTS (admin, paie, rh, comptable, auditeur, employe) restent dans `role`
-- + `access_grant` (scopés par organisation). Aucune fusion des deux univers.

-- Étend l'énumération des rôles internes sans toucher aux comptes existants.
ALTER TABLE app_user DROP CONSTRAINT IF EXISTS app_user_platform_role_check;
ALTER TABLE app_user
  ADD CONSTRAINT app_user_platform_role_check
  CHECK (platform_role IN (
    'none',            -- utilisateur CLIENT (aucun rôle interne WaSalaire)
    'super_admin',     -- administration générale + gouvernance plateforme
    'admin_plateforme',-- gestion opérationnelle (comptes, organisations, config autorisée)
    'support',         -- assistance clients / incidents (accès lecture limité + tracé)
    'conformite',      -- référentiels réglementaires (barèmes, versions) via workflow validé
    'commercial'       -- offres, abonnements, facturation SaaS
  ));
-- (security_event (009) couvre déjà la journalisation « break-glass » + index type/date.)
