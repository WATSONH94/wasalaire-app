-- =====================================================================
-- WaSalaire — Deltas v3 : RH avancé (congés), WaDocs, notifications.
-- À appliquer APRÈS 16/schema.sql + schema-v2-deltas.sql.
-- Complète la couche « autour du cœur » pour passer de conçu → opérationnel.
-- =====================================================================

-- ---------- Congés & absences ----------
CREATE TABLE leave_request (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id  uuid NOT NULL REFERENCES company(id),
    employee_id uuid NOT NULL REFERENCES employee(id),
    type        text NOT NULL CHECK (type IN ('conge_annuel','maladie','maternite','sans_solde','autre')),
    date_debut  date NOT NULL,
    date_fin    date NOT NULL,
    jours       numeric(5,1) NOT NULL DEFAULT 0,
    statut      text NOT NULL DEFAULT 'en_attente'
                CHECK (statut IN ('en_attente','valide','refuse')),
    motif       text,
    valide_par  uuid REFERENCES app_user(id),
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_leave_emp ON leave_request(employee_id);

-- ---------- WaDocs : modèles & documents ----------
CREATE TABLE document_template (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id  uuid REFERENCES company(id),   -- NULL = modèle global/cabinet
    name        text NOT NULL,
    category    text NOT NULL CHECK (category IN
                ('embauche','vie_salarie','paie','depart','declarations','courrier')),
    contenu     text NOT NULL,                 -- gabarit avec {{champs}}
    version     int  NOT NULL DEFAULT 1,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE document (
    id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id   uuid NOT NULL REFERENCES company(id),
    employee_id  uuid REFERENCES employee(id),
    template_id  uuid REFERENCES document_template(id),
    titre        text NOT NULL,
    contenu      text NOT NULL,                -- rendu (fusion faite)
    statut       text NOT NULL DEFAULT 'brouillon'
                 CHECK (statut IN ('brouillon','signe','publie')),
    hash         text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_document_emp ON document(employee_id);

-- ---------- Notifications (multi-canal) ----------
CREATE TABLE notification (
    id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id  uuid REFERENCES company(id),
    employee_id uuid REFERENCES employee(id),
    type        text NOT NULL,                 -- bulletin_pret, salaire_envoye, echeance...
    canal       text NOT NULL CHECK (canal IN ('push','sms','whatsapp','log')),
    destinataire text,                          -- téléphone / device
    message     text NOT NULL,
    statut      text NOT NULL DEFAULT 'envoye'  CHECK (statut IN ('a_envoyer','envoye','echoue')),
    reference   text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_notif_company ON notification(company_id);

-- ---------- RLS (scope-RLS, cohérent avec v2) ----------
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['leave_request','document','notification'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format($p$
      CREATE POLICY tenant_scope ON %I
        USING (company_id = ANY (current_scope()));
    $p$, t);
  END LOOP;
END $$;
-- document_template : lisible si global (company_id NULL) ou dans le scope
ALTER TABLE document_template ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON document_template
  USING (company_id IS NULL OR company_id = ANY (current_scope()));
