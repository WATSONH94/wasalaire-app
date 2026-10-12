"""
Tests de garde — gouvernance & complétude P1 (migration 006).
Prouve : (A) ORTB versionné en table, (B) dédup import de variables (MQ-05),
(C) 4-eyes calcul != validation configurable (INV-10), (D) matrice de droits
CONFIGURABLE par l'abonné + garde anti-lockout.
Prérequis : cluster PG lancé, migrations appliquées, rôle wasalaire_app.
Connexion libpq par env (PGUSER superuser pour le seed ; SET ROLE pour l'app).
"""
from __future__ import annotations
import sys
from datetime import date
import psycopg

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from moteur_paie import ReglementDB, Salarie, Rubrique, calcul_bulletin
from payroll_service import (
    set_scope, open_period, calculate_run, validate_and_close, add_variable,
    import_variables, effective_allowed_roles, set_permission_override,
    get_governance_policy, set_governance_policy, four_eyes_policy, WorkflowError,
)

W  = "11111111-0000-0000-0000-0000000000aa"
C1 = "11111111-0000-0000-0000-0000000000b1"
U1 = "11111111-0000-0000-0000-0000000000c1"
U2 = "11111111-0000-0000-0000-0000000000c2"

results = []
def check(label, cond):
    results.append((label, bool(cond))); print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

def raises_workflow(fn) -> bool:
    try:
        fn(); return False
    except WorkflowError:
        return True


def seed(su):
    su.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'WS Gov','entreprise_directe')", (W,))
    su.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Gamma SARL',0.02)", (C1, W))
    su.execute("INSERT INTO app_user(id,email) VALUES (%s,'u1@gamma.bj')", (U1,))
    su.execute("INSERT INTO app_user(id,email) VALUES (%s,'u2@gamma.bj')", (U2,))
    e1 = su.execute("INSERT INTO employee(company_id,matricule,nom) VALUES (%s,'G001','KOFFI Alain') RETURNING id", (C1,)).fetchone()[0]
    su.execute("INSERT INTO contract(company_id,employee_id,type,date_debut,salaire_base,mode,statut) VALUES (%s,%s,'CDI','2025-01-01',200000,'mensuel','actif')", (C1, e1))
    return str(e1)


def main():
    su = psycopg.connect("", autocommit=True)
    emp = seed(su)

    app = psycopg.connect("", autocommit=True)
    app.execute("SET ROLE wasalaire_app")
    set_scope(app, [C1])
    rg = ReglementDB(app)

    # (A) ORTB versionné en table (EC-02)
    print("A) ORTB en table :")
    o = rg.ortb(date(2026, 1, 1))
    check("ortb lu en base = {3:1000, 6:6->3000}", o.get(3) == 1000 and o.get(6) == 3000)
    b_juin = calcul_bulletin(Salarie("x"), [Rubrique("Base", 200000)], date(2026, 6, 1), reglement=rg)
    b_mai = calcul_bulletin(Salarie("x"), [Rubrique("Base", 200000)], date(2026, 5, 1), reglement=rg)
    check("ITS juin = ITS mai + 3000 (ORTB de table appliqué)", b_juin["its"] == b_mai["its"] + 3000)

    # (B) Dédup import de variables (MQ-05)
    print("B) Dédup import variables :")
    p = open_period(app, C1, 3, 2026)
    lignes = [{"employee_id": emp, "type": "Prime", "montant": 30000, "source_ref": "fic#1"},
              {"employee_id": emp, "type": "HS",    "montant": 12000, "source_ref": "fic#2"}]
    r1 = import_variables(app, C1, p, lignes, actor=U1)
    r2 = import_variables(app, C1, p, lignes, actor=U1)   # rejoue le même fichier
    n = app.execute("SELECT count(*) FROM variable WHERE period_id=%s", (p,)).fetchone()[0]
    check("1er import insère 2", r1["inserees"] == 2 and r1["ignorees"] == 0)
    check("2e import ignore 2 (idempotent)", r2["inserees"] == 0 and r2["ignorees"] == 2)
    check("pas de doublon en base (2 lignes)", n == 2)

    # (C) 4-eyes calcul != validation (INV-10), configurable
    print("C) 4-eyes calcul != validation :")
    check("défaut OFF (cible TPE mono-opérateur)",
          four_eyes_policy(app, C1, "four_eyes_calcul_validation") is False)
    # l'admin de l'abonné ACTIVE le 4-eyes
    set_governance_policy(app, W, "four_eyes_calcul_validation", True, actor=U1)
    run1, _ = calculate_run(app, C1, p, date(2026, 3, 1), actor=U1)
    check("activé : U1 calcule -> U1 ne peut pas valider",
          raises_workflow(lambda: validate_and_close(app, p, run1, actor=U1)))
    validate_and_close(app, p, run1, actor=U2)   # un second acteur : autorisé
    statut = app.execute("SELECT statut FROM payroll_period WHERE id=%s", (p,)).fetchone()[0]
    check("U2 (différent) valide et clôture", statut == "cloturee")
    # l'admin redésactive -> opérateur unique autorisé
    set_governance_policy(app, W, "four_eyes_calcul_validation", False, actor=U1)
    check("politique off : four_eyes_calcul_validation = False",
          four_eyes_policy(app, C1, "four_eyes_calcul_validation") is False)
    p2 = open_period(app, C1, 4, 2026)
    run2, _ = calculate_run(app, C1, p2, date(2026, 4, 1), actor=U1)
    validate_and_close(app, p2, run2, actor=U1)   # même acteur toléré car politique off
    check("politique off : U1 calcule ET valide (toléré)",
          app.execute("SELECT statut FROM payroll_period WHERE id=%s", (p2,)).fetchone()[0] == "cloturee")

    # (D) Matrice de droits configurable par l'abonné
    print("D) Matrice de droits configurable :")
    DEF = {"admin", "rh"}   # défaut (ex. employee.create)
    base = effective_allowed_roles(app, "employee.create", [W], DEF)
    check("défaut inchangé sans surcharge", base == {"admin", "rh"})
    set_permission_override(app, W, "employee.create", "paie", True, actor=U1)
    withpaie = effective_allowed_roles(app, "employee.create", [W], DEF)
    check("surcharge ALLOW : 'paie' ajouté", "paie" in withpaie)
    set_permission_override(app, W, "employee.create", "rh", False, actor=U1)
    without_rh = effective_allowed_roles(app, "employee.create", [W], DEF)
    check("surcharge DENY : 'rh' retiré", "rh" not in without_rh)
    check("anti-lockout : retirer admin de permissions.manage refusé",
          raises_workflow(lambda: set_permission_override(app, W, "permissions.manage", "admin", False, actor=U1)))
    floor = effective_allowed_roles(app, "permissions.manage", [W], {"admin"})
    check("anti-lockout : admin garde toujours permissions.manage", "admin" in floor)

    ok = sum(1 for _, c in results if c)
    print(f"\nGouvernance & P1 (006) : {ok}/{len(results)} PASS")
    if ok != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
