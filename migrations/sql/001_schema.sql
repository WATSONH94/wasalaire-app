-- =====================================================================
-- Schéma PostgreSQL — SaaS Paie Bénin (traduction de modele-de-donnees.md)
-- Multi-tenant par Row-Level Security (company_id) · réglementaire versionné
-- · immuabilité après clôture · audit append-only · soft delete.
-- ⚠️ Schéma de conception (prototype). Migrations réelles à outiller (Alembic/Prisma…).
--
-- ✅ VALIDÉ sur PostgreSQL 17.6 (20/09/2026) : chargement complet sans erreur ;
--    RLS testé (contexte tenant A → seules les lignes de A visibles) ;
--    trigger d'immuabilité testé (UPDATE d'un bulletin verrouillé → exception).
-- Note RLS : les policies s'appliquent aux rôles NON-superuser ; l'app se connecte
--    avec un rôle applicatif et exécute `SET app.current_company = '<uuid>'` par requête.
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------- Organisation & accès (cabinets multi-entreprises) ----------
CREATE TABLE workspace (
    id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    nom           text NOT NULL,
    type          text NOT NULL CHECK (type IN ('entreprise_directe','cabinet_comptable')),
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE company (               -- tenant
    id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id        uuid REFERENCES workspace(id),
    raison_sociale      text NOT NULL,
    ifu                 text,
    num_employeur_cnss  text,
    secteur             text,
    taux_atmp           numeric(4,3) NOT NULL DEFAULT 0.020 CHECK (taux_atmp BETWEEN 0.01 AND 0.04),
    regime_vps          text NOT NULL DEFAULT 'normal' CHECK (regime_vps IN ('normal','enseignement')),
    convention_id       uuid,
    created_at          timestamptz NOT NULL DEFAULT now(),
    deleted_at          timestamptz
);

CREATE TABLE app_user (              -- PAS de company_id : accès via membership
    id      uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    email   text NOT NULL UNIQUE,
    mfa_enabled boolean NOT NULL DEFAULT true,
    statut  text NOT NULL DEFAULT 'actif'
);

CREATE TABLE role (
    id    uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    code  text NOT NULL UNIQUE      -- admin, paie, rh, comptable, auditeur, employe
);

CREATE TABLE membership (            -- user ─* (workspace | company)
    id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      uuid NOT NULL REFERENCES app_user(id),
    workspace_id uuid REFERENCES workspace(id),
    company_id   uuid REFERENCES company(id),
    role_id      uuid NOT NULL REFERENCES role(id),
    date_debut   date NOT NULL DEFAULT current_date,
    date_fin     date,
    CHECK (workspace_id IS NOT NULL OR company_id IS NOT NULL)   -- au moins un scope
);

-- ---------- Structure entreprise ----------
CREATE TABLE establishment (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    nom text NOT NULL, adresse text, num_cnss_etab text
);
CREATE TABLE department (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    nom text NOT NULL, centre_de_cout text
);
CREATE TABLE position (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    intitule text NOT NULL,
    categorie text CHECK (categorie IN ('cadre','employe','ouvrier_horaire')),
    classification_conv text
);

-- ---------- Salarié & contrat ----------
CREATE TABLE employee (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    matricule text NOT NULL,
    nom text NOT NULL, num_cnss text, ifu text,
    date_naissance date, genre text CHECK (genre IN ('H','F')),
    situation_familiale text, iban_mobile_money text,
    created_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (company_id, matricule)
);
CREATE TABLE dependent (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    employee_id uuid NOT NULL REFERENCES employee(id),
    type text CHECK (type IN ('conjoint','enfant')),
    date_naissance date, a_charge boolean DEFAULT true,
    assure_perso boolean DEFAULT false, scolarise boolean, invalide boolean
);
CREATE TABLE contract (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    employee_id uuid NOT NULL REFERENCES employee(id),
    type text CHECK (type IN ('CDI','CDD','apprentissage')),
    date_debut date NOT NULL, date_fin date, periode_essai_fin date,
    position_id uuid REFERENCES position(id),
    department_id uuid REFERENCES department(id),
    establishment_id uuid REFERENCES establishment(id),
    convention_id uuid,
    salaire_base numeric(14,2) NOT NULL CHECK (salaire_base >= 0),
    mode text CHECK (mode IN ('mensuel','horaire')),
    statut text NOT NULL DEFAULT 'actif'
);

-- ---------- Rubriques & paie ----------
CREATE TABLE pay_element (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    code text NOT NULL, libelle text NOT NULL,
    type text CHECK (type IN ('gain','retenue','charge_pat','info')),
    soumis_cnss boolean NOT NULL DEFAULT true,   -- \
    soumis_its  boolean NOT NULL DEFAULT true,   --  > 3 assiettes indépendantes
    soumis_vps  boolean NOT NULL DEFAULT true,   -- /
    formule text, ordre int,
    UNIQUE (company_id, code)
);
CREATE TABLE payroll_period (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    mois int NOT NULL CHECK (mois BETWEEN 1 AND 12),
    annee int NOT NULL,
    statut text NOT NULL DEFAULT 'ouverte'
        CHECK (statut IN ('ouverte','calculee','validee','cloturee','comptabilisee','declaree','payee')),
    UNIQUE (company_id, annee, mois)
);
CREATE TABLE payroll_run (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    period_id uuid NOT NULL REFERENCES payroll_period(id),
    date_execution timestamptz NOT NULL DEFAULT now(),
    version_regles text
);
CREATE TABLE payslip (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    run_id uuid NOT NULL REFERENCES payroll_run(id),
    employee_id uuid NOT NULL REFERENCES employee(id),
    brut numeric(14,2), base_cnss numeric(14,2), base_its numeric(14,2),
    total_retenues numeric(14,2), net_a_payer numeric(14,2), cout_employeur numeric(14,2),
    pdf_url text, calc_snapshot_id uuid,
    version int NOT NULL DEFAULT 1,          -- bulletin rectificatif = nouvelle version
    verrouille boolean NOT NULL DEFAULT false
);
CREATE TABLE payslip_line (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    payslip_id uuid NOT NULL REFERENCES payslip(id),
    element_id uuid REFERENCES pay_element(id),
    base numeric(14,2), taux numeric(8,5), montant numeric(14,2),
    sens text CHECK (sens IN ('gain','retenue','charge'))
);
-- Reproductibilité légale : intrants + versions de règles figés
CREATE TABLE calc_snapshot (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    payslip_id uuid NOT NULL REFERENCES payslip(id),
    entrees_figees jsonb NOT NULL,
    bundle_regles jsonb NOT NULL,
    version_moteur text NOT NULL,
    regle_arrondi text NOT NULL,
    hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE variable (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    employee_id uuid NOT NULL REFERENCES employee(id),
    period_id uuid NOT NULL REFERENCES payroll_period(id),
    type text, quantite numeric(12,2), montant numeric(14,2)
);

-- ---------- Réglementaire (GLOBAL, versionné — pas de company_id) ----------
CREATE TABLE rate_table (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    code text NOT NULL, valeur numeric(12,5) NOT NULL,
    date_effet date NOT NULL, source text NOT NULL,
    UNIQUE (code, date_effet)               -- jamais d'UPDATE destructif : nouvelle version datée
);
CREATE TABLE tax_bracket (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_code text NOT NULL CHECK (table_code IN ('ITS','saisie')),
    tranche_min numeric(14,2) NOT NULL, tranche_max numeric(14,2),
    taux numeric(8,5) NOT NULL, date_effet date NOT NULL, source text NOT NULL
);
CREATE TABLE regulatory_rule (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    code text NOT NULL, description text, conditions text, formule text,
    date_debut date NOT NULL, date_fin date, source text, niveau_confiance text
);

-- ---------- Déclaratif, comptable, audit ----------
CREATE TABLE declaration (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    run_id uuid NOT NULL REFERENCES payroll_run(id),
    type text CHECK (type IN ('ITS','VPS','CNSS','AMO')),
    periode date, echeance date, montant numeric(14,2),
    statut text, fichier_export text, accuse text
);
CREATE TABLE accounting_entry (
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid NOT NULL REFERENCES company(id),
    run_id uuid NOT NULL REFERENCES payroll_run(id),
    journal text, compte text, libelle text,
    debit numeric(14,2) DEFAULT 0, credit numeric(14,2) DEFAULT 0,
    date_ecriture date
);
CREATE TABLE audit_log (             -- append-only
    id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id uuid,
    user_id uuid REFERENCES app_user(id),
    action text NOT NULL, entite text, avant jsonb, apres jsonb,
    ip inet, horodatage timestamptz NOT NULL DEFAULT now()
);

-- ---------- Index de performance ----------
CREATE INDEX idx_payslip_company_run   ON payslip(company_id, run_id);
CREATE INDEX idx_variable_emp_period   ON variable(employee_id, period_id);
CREATE INDEX idx_period_company        ON payroll_period(company_id, annee, mois);
CREATE INDEX idx_ratetable_code_date   ON rate_table(code, date_effet);

-- =====================================================================
-- ROW-LEVEL SECURITY (isolation multi-tenant)
-- Le middleware applicatif exécute :  SET app.current_company = '<uuid>';
-- =====================================================================
-- La table `company` est isolée sur sa propre clé `id` ; les autres sur `company_id`.
ALTER TABLE company ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON company
  USING (id = current_setting('app.current_company', true)::uuid);

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'establishment','department','position','employee','dependent',
    'contract','pay_element','payroll_period','payroll_run','payslip',
    'payslip_line','calc_snapshot','variable','declaration','accounting_entry']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format($p$
      CREATE POLICY tenant_isolation ON %I
        USING (company_id = current_setting('app.current_company', true)::uuid);
    $p$, t);
  END LOOP;
END $$;

-- Immuabilité : interdit UPDATE/DELETE d'un bulletin verrouillé (après clôture)
CREATE OR REPLACE FUNCTION forbid_locked_payslip() RETURNS trigger AS $$
BEGIN
  IF OLD.verrouille THEN
    RAISE EXCEPTION 'Bulletin verrouillé (clôturé) : correction = bulletin rectificatif (nouvelle version).';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_payslip_immutable BEFORE UPDATE OR DELETE ON payslip
  FOR EACH ROW EXECUTE FUNCTION forbid_locked_payslip();

-- Audit append-only : interdit UPDATE/DELETE
CREATE OR REPLACE FUNCTION forbid_audit_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_log est append-only.'; END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_audit_append_only BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION forbid_audit_mutation();

-- =====================================================================
-- Amorce des paramètres réglementaires versionnés (miroir de moteur_paie.PARAMS)
-- =====================================================================
INSERT INTO rate_table (code, valeur, date_effet, source) VALUES
 ('taux_pension_sal', 0.036, '2024-01-01', 'CNSS off. / Loi 98-019 Art.24-25'),
 ('taux_pension_emp', 0.064, '2024-01-01', 'CNSS off.'),
 ('taux_pf',          0.090, '2024-01-01', 'CNSS off.'),
 ('taux_vps',         0.040, '2024-01-01', 'CGI Art.194'),
 ('smig',         52000.000, '2023-01-01', 'Décret 2022-692'),
 ('part_souscripteur_amo', 0.800, '2026-10-29', 'Décret 2025-672 Art.10');

INSERT INTO tax_bracket (table_code, tranche_min, tranche_max, taux, date_effet, source) VALUES
 ('ITS',      0,  60000, 0.00, '2025-01-01', 'CGI Art.125'),
 ('ITS',  60000, 150000, 0.10, '2025-01-01', 'CGI Art.125'),
 ('ITS', 150000, 250000, 0.15, '2025-01-01', 'CGI Art.125'),
 ('ITS', 250000, 500000, 0.19, '2025-01-01', 'CGI Art.125'),
 ('ITS', 500000,   NULL, 0.30, '2025-01-01', 'CGI Art.125');
