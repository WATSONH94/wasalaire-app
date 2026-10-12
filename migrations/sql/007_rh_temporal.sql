-- =====================================================================
-- WaSalaire - Complétude P2-02 : intégrité temporelle RH.
-- Au plus un contrat actif par salarié ; pas de chevauchement de congés validés.
-- Migration incrémentale et immuable.
-- =====================================================================

-- Un seul contrat ACTIF par salarié (anti multi-contrats actifs, N6).
CREATE UNIQUE INDEX uq_contract_actif_emp ON contract(employee_id) WHERE statut='actif';

-- Pas de chevauchement de congés VALIDÉS pour un même salarié (sans dépendance btree_gist :
-- contrôle à l'écriture via trigger, en utilisant l'opérateur de recouvrement de daterange).
CREATE OR REPLACE FUNCTION guard_leave_overlap() RETURNS trigger AS $$
BEGIN
  IF NEW.statut = 'valide' THEN
    IF EXISTS (
      SELECT 1 FROM leave_request l
      WHERE l.employee_id = NEW.employee_id
        AND l.id <> NEW.id
        AND l.statut = 'valide'
        AND daterange(l.date_debut, l.date_fin, '[]')
            && daterange(NEW.date_debut, NEW.date_fin, '[]')
    ) THEN
      RAISE EXCEPTION 'Chevauchement de congés validés pour ce salarié (% au %).',
        NEW.date_debut, NEW.date_fin;
    END IF;
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_leave_overlap BEFORE INSERT OR UPDATE ON leave_request
  FOR EACH ROW EXECUTE FUNCTION guard_leave_overlap();
