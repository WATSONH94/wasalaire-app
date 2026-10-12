-- =====================================================================
-- WaSalaire - Lot 4 : durcissement sécurité (P1-08, P1-09).
-- FORCE RLS sur les tables tenant, contraintes org/grants, support 4-yeux.
-- Migration incrémentale et immuable.
-- =====================================================================

-- ---------- FORCE ROW LEVEL SECURITY (P1-08) ----------
-- Même le propriétaire de table est soumis aux policies (défense en profondeur ;
-- le runtime passe déjà par wasalaire_app non-propriétaire, mais FORCE couvre
-- tout accès par un rôle propriétaire qui poserait un scope).
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'company','establishment','department','position','employee','dependent',
    'contract','pay_element','payroll_period','payroll_run','payslip','payslip_line',
    'calc_snapshot','variable','declaration','accounting_entry','payout_batch',
    'payout_item','leave_request','document','notification','document_template']
  LOOP
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', t);
  END LOOP;
END $$;

-- ---------- P1-09 : contraintes organisation & grants ----------
-- 1 nœud 'societe' <-> 1 company (unicité).
CREATE UNIQUE INDEX uq_orgnode_company_societe ON org_node(company_id) WHERE type='societe';
-- Pas de nœud son propre parent (garde-fou anti-cycle minimal ; le reparentage
-- n'est pas supporté, donc aucun cycle ne peut se former autrement).
ALTER TABLE org_node ADD CONSTRAINT chk_orgnode_no_self_parent
    CHECK (parent_id IS NULL OR parent_id <> id);
-- Un grant (user, nœud, rôle) est unique.
ALTER TABLE access_grant ADD CONSTRAINT uq_access_grant UNIQUE (user_id, org_node_id, role_id);

-- ---------- Séparation des tâches : qui a clôturé (4 yeux sans lire l'audit) ----------
ALTER TABLE payroll_period ADD COLUMN cloture_par uuid REFERENCES app_user(id);
