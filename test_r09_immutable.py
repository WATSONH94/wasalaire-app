"""
Test de garde R09 : immuabilité des lignes de bulletin et du snapshot de calcul
après verrouillage (clôture).

Reproduit d'abord l'ancien comportement dangereux (mutation d'une ligne / d'un
snapshot d'un bulletin verrouillé) et vérifie qu'il est DÉSORMAIS bloqué par les
triggers de la migration 015. Un PASS = la faille R09 est fermée.

Entièrement transactionnel (ROLLBACK final) : aucun résidu en base, rejouable.

Prérequis : cluster + migrations 001..015 ; PG* en environnement (superuser).
"""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import uuid
import psycopg

res = []
def check(label, cond, detail=""):
    res.append(bool(cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))

def raises(cur, sql, params=()):
    """Exécute dans un SAVEPOINT ; True si une exception est levée (puis rollback du savepoint)."""
    cur.execute("SAVEPOINT sp")
    try:
        cur.execute(sql, params)
        cur.execute("RELEASE SAVEPOINT sp")
        return False
    except psycopg.Error:
        cur.execute("ROLLBACK TO SAVEPOINT sp")
        return True

def main():
    conn = psycopg.connect("", autocommit=False)   # superuser : RLS bypassée, triggers actifs
    cur = conn.cursor()

    W   = uuid.uuid4(); C = uuid.uuid4()
    PER = uuid.uuid4(); RUN = uuid.uuid4(); EMP = uuid.uuid4()
    PS_LOCK = uuid.uuid4(); PS_OPEN = uuid.uuid4()
    LINE_LOCK = uuid.uuid4(); SNAP_LOCK = uuid.uuid4(); LINE_OPEN = uuid.uuid4()

    try:
        cur.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'R09','cabinet_comptable')", (W,))
        cur.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'R09 SARL',0.02)", (C, W))
        cur.execute("INSERT INTO payroll_period(id,company_id,mois,annee) VALUES (%s,%s,1,2026)", (PER, C))
        cur.execute("INSERT INTO payroll_run(id,company_id,period_id) VALUES (%s,%s,%s)", (RUN, C, PER))
        cur.execute("INSERT INTO employee(id,company_id,matricule,nom) VALUES (%s,%s,'M001','Test')", (EMP, C))

        # Bulletin NON verrouillé : lignes + snapshot insérés normalement (comportement de calcul).
        cur.execute("INSERT INTO payslip(id,company_id,run_id,employee_id,verrouille) VALUES (%s,%s,%s,%s,false)",
                    (PS_LOCK, C, RUN, EMP))
        cur.execute("INSERT INTO payslip_line(id,company_id,payslip_id,montant,sens) VALUES (%s,%s,%s,100000,'gain')",
                    (LINE_LOCK, C, PS_LOCK))
        cur.execute("""INSERT INTO calc_snapshot(id,company_id,payslip_id,entrees_figees,bundle_regles,version_moteur,regle_arrondi,hash)
                       VALUES (%s,%s,%s,'{}'::jsonb,'{}'::jsonb,'v1','FCFA_entier','h0')""",
                    (SNAP_LOCK, C, PS_LOCK))

        # Clôture = verrouillage du bulletin (autorisé : OLD.verrouille=false).
        cur.execute("UPDATE payslip SET verrouille=true WHERE id=%s", (PS_LOCK,))
        cur.execute("SELECT verrouille FROM payslip WHERE id=%s", (PS_LOCK,))
        check("bulletin verrouillé (clôturé)", cur.fetchone()[0] is True)

        # R09 : toute mutation des lignes / du snapshot d'un bulletin verrouillé doit être refusée.
        check("UPDATE payslip_line d'un bulletin verrouillé refusé",
              raises(cur, "UPDATE payslip_line SET montant=1 WHERE id=%s", (LINE_LOCK,)))
        check("DELETE payslip_line d'un bulletin verrouillé refusé",
              raises(cur, "DELETE FROM payslip_line WHERE id=%s", (LINE_LOCK,)))
        check("INSERT payslip_line sur bulletin verrouillé refusé",
              raises(cur, "INSERT INTO payslip_line(id,company_id,payslip_id,montant,sens) VALUES (%s,%s,%s,5,'gain')",
                     (uuid.uuid4(), C, PS_LOCK)))
        check("UPDATE calc_snapshot d'un bulletin verrouillé refusé",
              raises(cur, "UPDATE calc_snapshot SET hash='x' WHERE id=%s", (SNAP_LOCK,)))
        check("DELETE calc_snapshot d'un bulletin verrouillé refusé",
              raises(cur, "DELETE FROM calc_snapshot WHERE id=%s", (SNAP_LOCK,)))

        # Contrôle de non-régression : bulletin NON verrouillé → lignes modifiables.
        cur.execute("INSERT INTO payslip(id,company_id,run_id,employee_id,verrouille) VALUES (%s,%s,%s,%s,false)",
                    (PS_OPEN, C, RUN, EMP))
        cur.execute("INSERT INTO payslip_line(id,company_id,payslip_id,montant,sens) VALUES (%s,%s,%s,200000,'gain')",
                    (LINE_OPEN, C, PS_OPEN))
        ok_update = not raises(cur, "UPDATE payslip_line SET montant=250000 WHERE id=%s", (LINE_OPEN,))
        check("UPDATE payslip_line d'un bulletin NON verrouillé autorisé (non-régression)", ok_update)

    finally:
        conn.rollback()   # idempotent : aucun résidu
        conn.close()

    n_ok = sum(res); n = len(res)
    print(f"\nGARDE R09 (immuabilité lignes + snapshot) : {n_ok}/{n} PASS")
    sys.exit(0 if n_ok == n else 1)

if __name__ == "__main__":
    main()
