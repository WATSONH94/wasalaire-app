"""
Test RLS WITH CHECK (A-03) : l'isolation multi-tenant en ÉCRITURE.
Un rôle applicatif dont le périmètre est [C1] ne doit PAS pouvoir INSÉRER ni
déplacer une ligne vers une société hors périmètre (C2), même en forgeant le
company_id directement (contournement du contrôle applicatif).

Prérequis : cluster + migrations (001..008) + rôle wasalaire_app ; PG* en env.
Base fraîche recommandée. Lancé en CI après run_migrations.sh.
"""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import psycopg
import payroll_service as ps

W  = "77777777-0000-0000-0000-000000000001"
C1 = "77777777-0000-0000-0000-0000000000c1"
C2 = "77777777-0000-0000-0000-0000000000c2"

res = []
def check(label, cond, detail=""):
    res.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))
def raises(fn, *exc):
    try: fn(); return False
    except exc or (Exception,): return True


def seed():
    s = psycopg.connect("", autocommit=True)   # superuser (bypass RLS) pour amorcer
    s.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'WS','cabinet_comptable')", (W,))
    s.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Alpha',0.02)", (C1, W))
    s.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Beta',0.02)", (C2, W))
    s.close()


def appc(scope):
    c = psycopg.connect("", autocommit=True)
    c.execute("SET ROLE wasalaire_app")   # rôle non-privilégié → RLS + WITH CHECK actifs
    ps.set_scope(c, scope)
    return c


def main():
    seed()
    c = appc([C1])   # périmètre = C1 uniquement

    # 1) INSERT dans le périmètre (C1) : autorisé.
    ok_insert = False
    try:
        c.execute("INSERT INTO employee(company_id,matricule,nom,methode_paiement) "
                  "VALUES (%s,'M1','KOFFI','especes')", (C1,))
        ok_insert = True
    except Exception as e:
        ok_insert = False
    check("INSERT employee dans le périmètre (C1) autorisé", ok_insert)

    # 2) INSERT hors périmètre (C2) en forçant company_id : REFUSÉ par WITH CHECK.
    def _insert_c2():
        try:
            c.execute("INSERT INTO employee(company_id,matricule,nom,methode_paiement) "
                      "VALUES (%s,'M2','MALICE','especes')", (C2,))
        except psycopg.errors.InsufficientPrivilege:
            raise psycopg.errors.InsufficientPrivilege("RLS WITH CHECK")
    check("INSERT employee hors périmètre (C2) refusé (WITH CHECK)",
          raises(_insert_c2, psycopg.errors.InsufficientPrivilege))

    # 3) UPDATE déplaçant une ligne de C1 vers C2 : REFUSÉ par WITH CHECK.
    def _move_to_c2():
        try:
            c.execute("UPDATE employee SET company_id=%s WHERE company_id=%s AND matricule='M1'",
                      (C2, C1))
        except psycopg.errors.InsufficientPrivilege:
            raise psycopg.errors.InsufficientPrivilege("RLS WITH CHECK")
    check("UPDATE déplaçant C1 -> C2 refusé (WITH CHECK)",
          raises(_move_to_c2, psycopg.errors.InsufficientPrivilege))

    # 4) Contrôle de non-régression : C2 reste invisible en lecture (USING).
    n = c.execute("SELECT count(*) FROM employee WHERE company_id=%s", (C2,)).fetchone()[0]
    check("aucune ligne C2 visible/insérée depuis le périmètre C1", n == 0, f"count={n}")
    c.close()

    ok = sum(res); print(f"\nRLS WITH CHECK (A-03) : {ok}/{len(res)} PASS")
    if ok != len(res): raise SystemExit(1)


if __name__ == "__main__":
    main()
