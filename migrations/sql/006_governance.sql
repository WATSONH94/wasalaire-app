-- =====================================================================
-- 006 — Gouvernance & complétude P1 (03/10/2026)
--   (A) ORTB en table versionnée (EC-02) : plus aucune règle en dur.
--   (B) Dédup import de variables (MQ-05) : clé de source, import rejouable.
--   (C) 4-eyes calcul != validation (INV-10) : traçabilité du calculateur du run.
--   (D) Matrice de droits CONFIGURABLE par l'abonné (workspace) + politique 4-eyes,
--       au choix de l'administrateur désigné par l'abonné. Le code ne porte que le
--       DÉFAUT (deny-by-default) ; l'abonné peut surcharger action x rôle.
-- Migration rejouable (IF NOT EXISTS / ON CONFLICT). Jamais de réécriture destructive.
-- =====================================================================

-- (A) ORTB (redevance audiovisuelle, CGI Art.125 §2) : mars = 1000, juin = 3000.
INSERT INTO rate_table (code, valeur, date_effet, source) VALUES
 ('ortb_mois_3', 1000, '2025-01-01', 'CGI Art.125 §2 (redevance ORTB, échéance de mars)'),
 ('ortb_mois_6', 3000, '2025-01-01', 'CGI Art.125 §2 (redevance ORTB, échéance de juin)')
ON CONFLICT (code, date_effet) DO NOTHING;

-- (B) Dédup import de variables : une même ligne source (source_ref) n'est insérée
--     qu'une fois par (société, période, salarié, type). source_ref NULL = saisie
--     manuelle unitaire (pas de contrainte, comportement historique inchangé).
ALTER TABLE variable ADD COLUMN IF NOT EXISTS source_ref text;
CREATE UNIQUE INDEX IF NOT EXISTS uq_variable_source
  ON variable (company_id, period_id, employee_id, type, source_ref)
  WHERE source_ref IS NOT NULL;

-- (C) 4-eyes calcul != validation : qui a calculé le run (peut rester NULL en mode
--     opérateur unique / appels sans acteur).
ALTER TABLE payroll_run ADD COLUMN IF NOT EXISTS calcule_par uuid REFERENCES app_user(id);

-- (D1) Surcharges de la matrice de droits, par abonné (workspace).
--      Une ligne (workspace, action, role_code) force allowed = true/false ;
--      en l'absence de ligne, le défaut du code (PERMISSIONS) s'applique.
CREATE TABLE IF NOT EXISTS permission_override (
    id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id  uuid NOT NULL REFERENCES workspace(id),
    action        text NOT NULL,
    role_code     text NOT NULL,
    allowed       boolean NOT NULL,
    updated_by    uuid REFERENCES app_user(id),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, action, role_code)
);
CREATE INDEX IF NOT EXISTS idx_perm_override_ws_action
  ON permission_override (workspace_id, action);

-- (D2) Politique de séparation des tâches (4-eyes), par abonné, réglée par l'admin.
--      Défaut = 4-eyes DÉSACTIVÉ : la cible est le TPE mono-opérateur (une personne
--      calcule et valide). L'administrateur de l'abonné l'ACTIVE quand la structure le
--      requiert (séparation calcul/validation et validation/décaissement).
CREATE TABLE IF NOT EXISTS governance_policy (
    workspace_id                 uuid PRIMARY KEY REFERENCES workspace(id),
    four_eyes_calcul_validation  boolean NOT NULL DEFAULT false,
    four_eyes_validation_paiement boolean NOT NULL DEFAULT false,
    updated_by                   uuid REFERENCES app_user(id),
    updated_at                   timestamptz NOT NULL DEFAULT now()
);
