-- =====================================================================
-- 009 — Comptes : authentification email+mot de passe, MFA TOTP,
--       rôles plateforme (SaaS), abonnements/plans/entitlements, journal sécurité.
--
-- COMPLÈTE l'identité téléphone+OTP existante (ne la remplace pas) : un même
-- app_user peut se connecter par téléphone+OTP (mobile) ET par email+mdp+TOTP (web).
-- Aucun mot de passe ni secret TOTP en clair : seuls des hashs / secrets chiffrés
-- applicativement sont stockés (le chiffrement/hachage est fait par le service).
-- Idempotent (ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS / ON CONFLICT).
-- =====================================================================

-- ---------- Identité : credentials email + mot de passe ----------
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS password_hash        text;        -- hash argon2/bcrypt ; jamais le clair
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS must_change_password boolean NOT NULL DEFAULT false;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS email_verifie        boolean NOT NULL DEFAULT false;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS provisioned_by       text;        -- 'admin' = provisionné manuellement (non vérifié par email)
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS created_at           timestamptz NOT NULL DEFAULT now();

-- ---------- MFA TOTP (obligatoire) ----------
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS totp_secret_enc      text;        -- secret TOTP CHIFFRÉ (jamais en clair)
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS totp_enrolled        boolean NOT NULL DEFAULT false;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS mfa_enforced         boolean NOT NULL DEFAULT true;  -- MFA imposé

-- Codes de récupération MFA (hashés, usage unique)
CREATE TABLE IF NOT EXISTS mfa_recovery_code (
    id         uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    uuid NOT NULL REFERENCES app_user(id),
    code_hash  text NOT NULL,
    used_at    timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mfa_recovery_user ON mfa_recovery_code(user_id);

-- ---------- Rôle plateforme (SaaS), distinct des rôles tenant ----------
-- 'none' par défaut. 'admin_plateforme' = gestion comptes/plans/support SANS données paie.
-- 'super_admin' = accès transverse complet (décision explicite ; usage tracé = break-glass, cf. security_event).
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS platform_role text NOT NULL DEFAULT 'none'
    CHECK (platform_role IN ('none','admin_plateforme','super_admin'));

-- ---------- Journal de sécurité (connexions, MFA, brute-force, break-glass) ----------
CREATE TABLE IF NOT EXISTS security_event (
    id         uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    uuid REFERENCES app_user(id),
    email      text,
    type       text NOT NULL,     -- login_ok|login_fail|mfa_ok|mfa_fail|totp_enrolled|password_changed|lockout|mfa_reset|breakglass_access
    ip         inet,
    detail     jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_secevent_user  ON security_event(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_secevent_email ON security_event(email, created_at);
CREATE INDEX IF NOT EXISTS idx_secevent_type  ON security_event(type, created_at);

-- ---------- Abonnements / plans / entitlements ----------
CREATE TABLE IF NOT EXISTS plan (
    id         uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    code       text NOT NULL UNIQUE,                 -- freemium|standard|pro|entreprise|cabinet|beta
    libelle    text NOT NULL,
    is_public  boolean NOT NULL DEFAULT true,         -- plan commercial (true) vs interne/bêta (false)
    limites    jsonb NOT NULL DEFAULT '{}'::jsonb,    -- quotas & features : max_societes, max_salaries, exports...
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS subscription (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id uuid NOT NULL REFERENCES workspace(id),
    plan_id     uuid NOT NULL REFERENCES plan(id),
    statut      text NOT NULL DEFAULT 'active'
                CHECK (statut IN ('active','trialing','beta','suspended','cancelled')),
    is_beta     boolean NOT NULL DEFAULT false,       -- licence bêta : accès sans facturation réelle
    date_debut  date NOT NULL DEFAULT current_date,
    date_fin    date,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id)                             -- 1 abonnement courant par abonné (workspace)
);
CREATE INDEX IF NOT EXISTS idx_subscription_ws ON subscription(workspace_id);

-- Amorce des plans (idempotent). Quotas indicatifs — à affiner avec le produit.
INSERT INTO plan (code, libelle, is_public, limites) VALUES
 ('freemium',  'Freemium',               true,  '{"max_societes":1,"max_salaries":5,"exports":false,"declarations":false,"multi_client":false}'),
 ('standard',  'Standard',               true,  '{"max_societes":1,"max_salaries":50,"exports":true,"declarations":true,"multi_client":false}'),
 ('pro',       'Pro',                    true,  '{"max_societes":5,"max_salaries":500,"exports":true,"declarations":true,"multi_client":false}'),
 ('entreprise','Entreprise multi-sites', true,  '{"max_societes":1,"max_etablissements":100,"max_salaries":100000,"exports":true,"declarations":true,"analytique":true,"multi_client":false}'),
 ('cabinet',   'Cabinet multi-clients',  true,  '{"max_clients":1000,"max_salaries":100000,"exports":true,"declarations":true,"multi_client":true}'),
 ('beta',      'Accès bêta complet',     false, '{"max_societes":1000,"max_salaries":1000000,"exports":true,"declarations":true,"multi_client":true,"all_features":true}')
ON CONFLICT (code) DO NOTHING;

-- Index d'unicité email insensible à la casse (les emails sont comparés en minuscule par le service)
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_email_lower ON app_user (lower(email)) WHERE email IS NOT NULL;
