"""
Preuve bout-en-bout : MOTEUR → PostgreSQL (persistance réelle) sous scope-RLS.
Prérequis : cluster lancé, schema.sql + schema-v2-deltas.sql chargés, rôle
applicatif `wasalaire_app` créé et privilégié (voir le script d'orchestration).
Connexion via variables d'environnement libpq (PGHOST/PGPORT/PGUSER/PGDATABASE).

Vérifie : calcul persisté = valeur du moteur testé ; snapshot présent (hash) ;
immuabilité après clôture ; isolation scope-RLS (une société ne voit pas l'autre).
"""
from __future__ import annotations
import sys
from datetime import date
import psycopg

try:  # console Windows (cp1252) → forcer UTF-8 pour l'affichage
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from payroll_service import (
    set_scope, open_period, calculate_run, validate_and_close, list_payslips,
)

C1 = "aaaaaaaa-0000-0000-0000-000000000001"
C2 = "bbbbbbbb-0000-0000-0000-000000000002"
W  = "cccccccc-0000-0000-0000-000000000003"

results = []
def check(label, cond):
    results.append((label, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")


def seed(su):
    su.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'WS','entreprise_directe')", (W,))
    su.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Alpha SARL',0.02)", (C1, W))
    su.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Beta SARL',0.02)", (C2, W))
    # Société 1 : 2 salariés
    e1 = su.execute("INSERT INTO employee(company_id,matricule,nom) VALUES (%s,'M001','KOFFI Alain') RETURNING id", (C1,)).fetchone()[0]
    e2 = su.execute("INSERT INTO employee(company_id,matricule,nom) VALUES (%s,'M002','ADJOVI Mireille') RETURNING id", (C1,)).fetchone()[0]
    su.execute("INSERT INTO contract(company_id,employee_id,type,date_debut,salaire_base,mode,statut) VALUES (%s,%s,'CDI','2025-01-01',200000,'mensuel','actif')", (C1, e1))
    su.execute("INSERT INTO contract(company_id,employee_id,type,date_debut,salaire_base,mode,statut) VALUES (%s,%s,'CDI','2025-01-01',100000,'mensuel','actif')", (C1, e2))
    # une prime (soumise aux 3 assiettes par défaut) pour e2, période jan-2026
    per1 = su.execute("INSERT INTO payroll_period(company_id,mois,annee) VALUES (%s,1,2026) RETURNING id", (C1,)).fetchone()[0]
    su.execute("INSERT INTO variable(company_id,employee_id,period_id,type,montant) VALUES (%s,%s,%s,'Prime',30000)", (C1, e2, per1))
    su.execute("UPDATE payroll_period SET statut='ouverte' WHERE id=%s", (per1,))
    # Société 2 : 1 salarié + un bulletin direct (pour tester l'isolation)
    e3 = su.execute("INSERT INTO employee(company_id,matricule,nom) VALUES (%s,'B001','Autre Société') RETURNING id", (C2,)).fetchone()[0]
    p2 = su.execute("INSERT INTO payroll_period(company_id,mois,annee) VALUES (%s,1,2026) RETURNING id", (C2,)).fetchone()[0]
    r2 = su.execute("INSERT INTO payroll_run(company_id,period_id,version_regles) VALUES (%s,%s,'2026') RETURNING id", (C2, p2)).fetchone()[0]
    su.execute("INSERT INTO payslip(company_id,run_id,employee_id,brut,net_a_payer) VALUES (%s,%s,%s,999,999)", (C2, r2, e3))


def main():
    su = psycopg.connect("", autocommit=True)   # superuser (bypass RLS) : bootstrap
    seed(su)

    app = psycopg.connect("", autocommit=True)   # rôle applicatif : RLS active
    app.execute("SET ROLE wasalaire_app")
    set_scope(app, [C1])

    print("Cycle de paie (société Alpha, scope=Alpha) :")
    period_id = open_period(app, C1, 1, 2026)
    run_id, n = calculate_run(app, C1, period_id, date(2026, 1, 1))
    validate_and_close(app, period_id, run_id)
    bulletins = {b["nom"]: b for b in list_payslips(app, run_id)}

    # 1) calcul persisté = valeur du moteur (KOFFI base 200000 → net 176 300)
    k = bulletins.get("KOFFI Alain", {})
    check("2 bulletins calculés & persistés", n == 2 and len(bulletins) == 2)
    check("net KOFFI = 176 300 (moteur)", k.get("net") == 176300)
    check("base_its KOFFI = 200 000", k.get("base_its") == 200000)
    check("coût employeur KOFFI = 242 800", k.get("cout_employeur") == 242800)
    check("bulletins verrouillés après clôture", all(b["verrouille"] for b in bulletins.values()))

    # 2) snapshot de reproductibilité présent (hash) pour chaque bulletin
    snaps = app.execute(
        "SELECT count(*) FROM calc_snapshot s JOIN payslip p ON p.id=s.payslip_id "
        "WHERE p.run_id=%s AND s.hash IS NOT NULL", (run_id,)).fetchone()[0]
    check("snapshot+hash pour chaque bulletin", snaps == n)

    # 3) immuabilité : UPDATE d'un bulletin verrouillé → refusé par la BD
    blocked = False
    try:
        app.execute("UPDATE payslip SET net_a_payer=1 WHERE run_id=%s", (run_id,))
    except psycopg.errors.RaiseException:
        blocked = True
    check("UPDATE bulletin verrouillé rejeté (trigger)", blocked)

    # 4) isolation scope-RLS
    set_scope(app, [C1])
    vue_c1 = app.execute("SELECT count(*) FROM payslip").fetchone()[0]
    check("scope Alpha → ne voit QUE ses 2 bulletins", vue_c1 == 2)
    set_scope(app, [C2])
    vue_c2 = app.execute("SELECT count(*) FROM payslip").fetchone()[0]
    voit_run_c1 = app.execute("SELECT count(*) FROM payslip WHERE run_id=%s", (run_id,)).fetchone()[0]
    check("scope Beta → voit son bulletin, pas ceux d'Alpha", vue_c2 == 1 and voit_run_c1 == 0)

    ok = sum(1 for _, c in results if c)
    print(f"\nPersistance API↔BD : {ok}/{len(results)} PASS "
          f"(moteur→PostgreSQL, scope-RLS, immuabilité, snapshot)")
    if ok != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
