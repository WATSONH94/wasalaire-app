"""
Tests complétude P2-02 : intégrité temporelle RH.
- Au plus un contrat actif par salarié (index unique partiel).
- Pas de chevauchement de congés validés (trigger).
Prérequis : cluster + migrations (001..007) ; PG* en env ; WASALAIRE_DEV=1. Base fraîche.
"""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import psycopg

W="55555555-0000-0000-0000-000000000001"; C1="55555555-0000-0000-0000-0000000000c1"
res=[]
def check(l,c,d=""):
    res.append(bool(c)); print(f"  [{'PASS' if c else 'FAIL'}] {l}" + (f"  -> {d}" if d else ""))
def denied(conn, sql, params=None, *exc):
    try:
        conn.execute(sql, params or ()); return False
    except exc or (Exception,):
        return True

def main():
    s=psycopg.connect("",autocommit=True)
    s.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'WS','cabinet_comptable')",(W,))
    s.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Alpha',0.02)",(C1,W))
    e=s.execute("INSERT INTO employee(company_id,matricule,nom) VALUES (%s,'M001','KOFFI') RETURNING id",(C1,)).fetchone()[0]
    s.execute("INSERT INTO contract(company_id,employee_id,type,date_debut,salaire_base,mode,statut) "
              "VALUES (%s,%s,'CDI','2025-01-01',200000,'mensuel','actif')",(C1,e))

    # 1) Second contrat ACTIF pour le même salarié -> refusé (index unique partiel)
    check("2e contrat actif pour un même salarié refusé",
          denied(s, "INSERT INTO contract(company_id,employee_id,type,date_debut,salaire_base,mode,statut) "
                    "VALUES (%s,%s,'CDD','2025-06-01',150000,'mensuel','actif')", (C1,e),
                 psycopg.errors.UniqueViolation))
    # mais un contrat clos en plus est permis
    check("contrat supplémentaire 'clos' permis",
          not denied(s, "INSERT INTO contract(company_id,employee_id,type,date_debut,salaire_base,mode,statut) "
                        "VALUES (%s,%s,'CDD','2024-01-01',150000,'mensuel','clos')", (C1,e)))

    # 2) Congés : deux demandes qui se chevauchent, validées -> 2e validation refusée
    l1=s.execute("INSERT INTO leave_request(company_id,employee_id,type,date_debut,date_fin,jours,statut) "
                 "VALUES (%s,%s,'conge_annuel','2026-07-01','2026-07-10',8,'valide') RETURNING id",(C1,e)).fetchone()[0]
    l2=s.execute("INSERT INTO leave_request(company_id,employee_id,type,date_debut,date_fin,jours,statut) "
                 "VALUES (%s,%s,'conge_annuel','2026-07-08','2026-07-15',6,'en_attente') RETURNING id",(C1,e)).fetchone()[0]
    check("validation d'un congé chevauchant un congé validé refusée",
          denied(s, "UPDATE leave_request SET statut='valide' WHERE id=%s", (l2,),
                 psycopg.errors.RaiseException))
    # un congé non chevauchant se valide
    l3=s.execute("INSERT INTO leave_request(company_id,employee_id,type,date_debut,date_fin,jours,statut) "
                 "VALUES (%s,%s,'conge_annuel','2026-09-01','2026-09-05',4,'en_attente') RETURNING id",(C1,e)).fetchone()[0]
    check("validation d'un congé non chevauchant acceptée",
          not denied(s, "UPDATE leave_request SET statut='valide' WHERE id=%s", (l3,)))
    s.close()

    ok=sum(res); print(f"\nIntégrité temporelle RH (P2-02) : {ok}/{len(res)} PASS")
    if ok!=len(res): raise SystemExit(1)

if __name__=="__main__":
    main()
