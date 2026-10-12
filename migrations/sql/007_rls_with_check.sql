-- =====================================================================
-- 007 — Défense en profondeur RLS : ajout de WITH CHECK (correctif A-03)
--
-- Les policies `tenant_scope` ne définissaient qu'un `USING`. En PostgreSQL, la
-- clause USING filtre les LECTURES et les lignes candidates d'un UPDATE/DELETE,
-- mais NE contraint PAS les INSERT ni la nouvelle valeur d'un UPDATE. Sans
-- `WITH CHECK`, le rôle applicatif pouvait donc ÉCRIRE (INSERT/UPDATE) une ligne
-- portant un `company_id` HORS de son périmètre (fuite/corruption inter-tenant
-- en cas de bug ou de compromission applicative).
--
-- Ce correctif pose `WITH CHECK = USING` sur toutes les tables tenant : on ne peut
-- écrire que dans le périmètre courant (current_scope()). Les FK composites (004)
-- garantissent déjà la cohérence de société entre parent et enfant ; WITH CHECK
-- ajoute la garantie au niveau de CHAQUE écriture.
--
-- Migration incrémentale et immuable (ne jamais réécrire une migration jouée).
-- =====================================================================

-- Tables isolées sur `company_id` : WITH CHECK identique au USING.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'establishment','department','position','employee','dependent',
    'contract','pay_element','payroll_period','payroll_run','payslip',
    'payslip_line','calc_snapshot','variable','declaration','accounting_entry',
    'payout_batch','payout_item','leave_request','document','notification']
  LOOP
    EXECUTE format(
      'ALTER POLICY tenant_scope ON %I '
      'USING (company_id = ANY (current_scope())) '
      'WITH CHECK (company_id = ANY (current_scope()));', t);
  END LOOP;
END $$;

-- `company` : isolée sur sa propre clé `id`. Le rôle applicatif ne crée pas de
-- société (provisionnement = hors runtime) ; WITH CHECK l'empêche explicitement.
ALTER POLICY tenant_scope ON company
  USING (id = ANY (current_scope()))
  WITH CHECK (id = ANY (current_scope()));

-- `document_template` : LECTURE = modèle global (company_id NULL) OU dans le scope ;
-- ÉCRITURE = scope uniquement (le runtime ne crée pas de modèle global : réservé au
-- provisionnement via un rôle propriétaire/superuser).
ALTER POLICY tenant_scope ON document_template
  USING (company_id IS NULL OR company_id = ANY (current_scope()))
  WITH CHECK (company_id = ANY (current_scope()));
