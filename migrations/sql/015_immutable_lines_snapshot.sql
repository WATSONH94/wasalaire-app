-- =====================================================================
-- 015 : Immuabilité étendue aux lignes de bulletin et au snapshot de calcul (R09)
-- Migration incrémentale et immuable (ne jamais réécrire une migration jouée).
-- ---------------------------------------------------------------------
-- AVANT : seul `payslip` était protégé (trg_payslip_immutable sur la colonne
--         `verrouille`). Les lignes `payslip_line` et le snapshot figé
--         `calc_snapshot` d'un bulletin VERROUILLÉ restaient modifiables,
--         permettant d'altérer une paie clôturée en contournant l'immuabilité
--         du bulletin (anomalie R09 du contre-audit).
-- APRES  : toute INSERT / UPDATE / DELETE sur `payslip_line` ou `calc_snapshot`
--         dont le bulletin parent est verrouillé lève une exception.
--         Correction d'une paie clôturée = bulletin rectificatif
--         (nouveau bulletin, version + 1, non verrouillé).
-- Note RLS : fonction SECURITY INVOKER ; le SELECT sur payslip reste soumis à
--         la policy tenant_isolation (même company_id que la ligne), donc visible.
-- =====================================================================

CREATE OR REPLACE FUNCTION forbid_mutation_on_locked_payslip() RETURNS trigger AS $$
DECLARE
  pid    uuid;
  locked boolean;
BEGIN
  pid := COALESCE(NEW.payslip_id, OLD.payslip_id);
  SELECT verrouille INTO locked FROM payslip WHERE id = pid;
  IF COALESCE(locked, false) THEN
    RAISE EXCEPTION 'Bulletin verrouillé (clôturé) : lignes et snapshot figés. Correction = bulletin rectificatif (nouvelle version).';
  END IF;
  RETURN COALESCE(NEW, OLD);
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_payslip_line_immutable ON payslip_line;
CREATE TRIGGER trg_payslip_line_immutable
  BEFORE INSERT OR UPDATE OR DELETE ON payslip_line
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation_on_locked_payslip();

DROP TRIGGER IF EXISTS trg_calc_snapshot_immutable ON calc_snapshot;
CREATE TRIGGER trg_calc_snapshot_immutable
  BEFORE INSERT OR UPDATE OR DELETE ON calc_snapshot
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation_on_locked_payslip();

-- ---------------------------------------------------------------------
-- ROLLBACK manuel (réversibilité documentée ; ne pas exécuter en routine) :
--   DROP TRIGGER IF EXISTS trg_payslip_line_immutable ON payslip_line;
--   DROP TRIGGER IF EXISTS trg_calc_snapshot_immutable ON calc_snapshot;
--   DROP FUNCTION IF EXISTS forbid_mutation_on_locked_payslip();
-- ---------------------------------------------------------------------
