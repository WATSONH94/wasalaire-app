-- =====================================================================
-- WaSalaire - Lot 1 : intégrité inter-sociétés (P0-06), machine d'états (P0-01),
-- unicité de run actif (N3) et de lot de décaissement (P0-04).
-- Migration incrémentale et immuable (ne jamais réécrire une migration jouée).
-- =====================================================================

-- ---------- Clés composites (parents) : (id, company_id) ----------
-- Nécessaires pour que les FK composites des enfants garantissent la cohérence de société.
ALTER TABLE employee       ADD CONSTRAINT uq_employee_id_company  UNIQUE (id, company_id);
ALTER TABLE payroll_period ADD CONSTRAINT uq_period_id_company    UNIQUE (id, company_id);
ALTER TABLE payroll_run    ADD CONSTRAINT uq_run_id_company       UNIQUE (id, company_id);
ALTER TABLE payslip        ADD CONSTRAINT uq_payslip_id_company   UNIQUE (id, company_id);
ALTER TABLE payout_batch   ADD CONSTRAINT uq_batch_id_company     UNIQUE (id, company_id);

-- ---------- FK composites (enfants) : la société doit correspondre ----------
ALTER TABLE contract        ADD CONSTRAINT fk_contract_emp_company
    FOREIGN KEY (employee_id, company_id) REFERENCES employee(id, company_id);
ALTER TABLE variable        ADD CONSTRAINT fk_variable_emp_company
    FOREIGN KEY (employee_id, company_id) REFERENCES employee(id, company_id);
ALTER TABLE variable        ADD CONSTRAINT fk_variable_period_company
    FOREIGN KEY (period_id, company_id)   REFERENCES payroll_period(id, company_id);
ALTER TABLE payroll_run     ADD CONSTRAINT fk_run_period_company
    FOREIGN KEY (period_id, company_id)   REFERENCES payroll_period(id, company_id);
ALTER TABLE payslip         ADD CONSTRAINT fk_payslip_run_company
    FOREIGN KEY (run_id, company_id)      REFERENCES payroll_run(id, company_id);
ALTER TABLE payslip         ADD CONSTRAINT fk_payslip_emp_company
    FOREIGN KEY (employee_id, company_id) REFERENCES employee(id, company_id);
ALTER TABLE payslip_line    ADD CONSTRAINT fk_line_payslip_company
    FOREIGN KEY (payslip_id, company_id)  REFERENCES payslip(id, company_id);
ALTER TABLE calc_snapshot   ADD CONSTRAINT fk_snap_payslip_company
    FOREIGN KEY (payslip_id, company_id)  REFERENCES payslip(id, company_id);
ALTER TABLE declaration     ADD CONSTRAINT fk_decl_run_company
    FOREIGN KEY (run_id, company_id)      REFERENCES payroll_run(id, company_id);
ALTER TABLE accounting_entry ADD CONSTRAINT fk_acc_run_company
    FOREIGN KEY (run_id, company_id)      REFERENCES payroll_run(id, company_id);
ALTER TABLE payout_batch    ADD CONSTRAINT fk_batch_run_company
    FOREIGN KEY (run_id, company_id)      REFERENCES payroll_run(id, company_id);
ALTER TABLE payout_item     ADD CONSTRAINT fk_item_batch_company
    FOREIGN KEY (batch_id, company_id)    REFERENCES payout_batch(id, company_id);
ALTER TABLE payout_item     ADD CONSTRAINT fk_item_emp_company
    FOREIGN KEY (employee_id, company_id) REFERENCES employee(id, company_id);
ALTER TABLE leave_request   ADD CONSTRAINT fk_leave_emp_company
    FOREIGN KEY (employee_id, company_id) REFERENCES employee(id, company_id);
-- document.employee_id est NULLABLE (documents globaux) : MATCH SIMPLE n'exige la
-- cohérence que si employee_id est renseigné.
ALTER TABLE document        ADD CONSTRAINT fk_document_emp_company
    FOREIGN KEY (employee_id, company_id) REFERENCES employee(id, company_id);

-- ---------- Machine d'états : période ----------
-- Interdit la réouverture d'une période clôturée et toute sortie de l'état 'cloturee'.
CREATE OR REPLACE FUNCTION guard_period_transition() RETURNS trigger AS $$
BEGIN
  IF OLD.statut = 'cloturee' AND NEW.statut <> 'cloturee' THEN
    RAISE EXCEPTION 'Période clôturée non modifiable (% -> %). Correction = rectificatif.',
      OLD.statut, NEW.statut;
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_period_transition BEFORE UPDATE ON payroll_period
  FOR EACH ROW EXECUTE FUNCTION guard_period_transition();

-- Interdit la création d'un run sur une période clôturée (aucun run libre après clôture).
CREATE OR REPLACE FUNCTION guard_run_on_open_period() RETURNS trigger AS $$
DECLARE st text;
BEGIN
  SELECT statut INTO st FROM payroll_period WHERE id = NEW.period_id;
  IF st = 'cloturee' THEN
    RAISE EXCEPTION 'Période clôturée : aucun nouveau run (rectificatif requis).';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_run_open_period BEFORE INSERT ON payroll_run
  FOR EACH ROW EXECUTE FUNCTION guard_run_on_open_period();

-- ---------- Un seul run ACTIF par période (N3) ----------
ALTER TABLE payroll_run ADD COLUMN actif boolean NOT NULL DEFAULT true;
CREATE UNIQUE INDEX uq_run_actif_period ON payroll_run(period_id) WHERE actif;

-- ---------- Un seul lot de décaissement par run (P0-04) ----------
ALTER TABLE payout_batch ADD CONSTRAINT uq_batch_run UNIQUE (run_id);
