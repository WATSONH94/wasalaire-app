"""
Tests Lot 5 : déclarations et comptabilité câblées au run CLÔTURÉ (P1-07).
Persistance, équilibre comptable, idempotence, refus avant clôture, RBAC.
Prérequis : cluster + migrations (001..005) + wasalaire_app ; PG* en env ; WASALAIRE_DEV=1.
"""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from datetime import date
import psycopg
import payroll_service as ps
from payroll_service import WorkflowError

W="77777777-0000-0000-0000-000000000001"; C1="77777777-0000-0000-0000-0000000000c1"
NODE="77777777-0000-0000-0000-0000000000a1"; RADM="77777777-0000-0000-0000-0000000000b1"
RAUD="77777777-0000-0000-0000-0000000000b2"; UADM="77777777-0000-0000-0000-0000000000e1"
UAUD="77777777-0000-0000-0000-0000000000e2"

res=[]
def check(l,c,d=""):
    res.append(bool(c)); print(f"  [{'PASS' if c else 'FAIL'}] {l}" + (f"  -> {d}" if d else ""))
def raises_wf(fn):
    try: fn(); return False
    except WorkflowError: return True

def seed():
    s=psycopg.connect("",autocommit=True)
    s.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'WS','cabinet_comptable')",(W,))
    s.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Alpha',0.02)",(C1,W))
    s.execute("INSERT INTO org_node(id,tenant_id,type,nom,company_id) VALUES (%s,%s,'societe','Alpha',%s)",(NODE,W,C1))
    s.execute("INSERT INTO role(id,code) VALUES (%s,'admin'),(%s,'auditeur')",(RADM,RAUD))
    s.execute("INSERT INTO app_user(id,telephone,telephone_verifie) VALUES (%s,'+22961000030',true)",(UADM,))
    s.execute("INSERT INTO app_user(id,telephone,telephone_verifie) VALUES (%s,'+22961000031',true)",(UAUD,))
    s.execute("INSERT INTO access_grant(user_id,org_node_id,role_id) VALUES (%s,%s,%s)",(UADM,NODE,RADM))
    s.execute("INSERT INTO access_grant(user_id,org_node_id,role_id) VALUES (%s,%s,%s)",(UAUD,NODE,RAUD))
    e=s.execute("INSERT INTO employee(company_id,matricule,nom,methode_paiement) "
                "VALUES (%s,'M001','KOFFI',  'virement') RETURNING id",(C1,)).fetchone()[0]
    s.execute("INSERT INTO contract(company_id,employee_id,type,date_debut,salaire_base,mode,statut) "
              "VALUES (%s,%s,'CDI','2025-01-01',200000,'mensuel','actif')",(C1,e))
    s.close()

def app():
    c=psycopg.connect("",autocommit=True); c.execute("SET ROLE wasalaire_app"); ps.set_scope(c,[C1]); return c

def main():
    seed()
    c=app()
    p=ps.open_period(c,C1,1,2026)
    run,_=ps.calculate_run(c,C1,p,date(2026,1,1))

    # refus AVANT clôture
    check("déclaration refusée avant clôture", raises_wf(lambda: ps.persist_declaration(c,run)))
    check("comptabilité refusée avant clôture", raises_wf(lambda: ps.persist_accounting(c,run)))

    ps.validate_and_close(c,p,run,actor=UADM)

    # déclarations
    d1=ps.persist_declaration(c,run,actor=UADM)
    types={x["type"] for x in d1}
    check("déclarations persistées (ITS,VPS,CNSS,AMO)", types=={"ITS","VPS","CNSS","AMO"}, str(sorted(types)))
    d2=ps.persist_declaration(c,run,actor=UADM)
    n=c.execute("SELECT count(*) FROM declaration WHERE run_id=%s",(run,)).fetchone()[0]
    check("déclarations idempotentes (pas de doublon)", len(d2)==4 and n==4, f"{n} lignes")

    # comptabilité
    a1=ps.persist_accounting(c,run,actor=UADM)
    check("écriture comptable équilibrée (débit=crédit)", a1["total_debit"]==a1["total_credit"] and a1["total_debit"]>0,
          f"D={a1['total_debit']} C={a1['total_credit']}")
    ps.persist_accounting(c,run,actor=UADM)
    ne=c.execute("SELECT count(*) FROM accounting_entry WHERE run_id=%s",(run,)).fetchone()[0]
    check("comptabilité idempotente (une seule écriture)", ne==len(a1["lignes"]), f"{ne} lignes")
    c.close()

    # RBAC : auditeur ne peut pas persister la compta ; comptable/admin oui (via API)
    from fastapi.testclient import TestClient
    from api_v2 import app as fastapp, make_token
    tc=TestClient(fastapp)
    H_aud={"Authorization":f"Bearer {make_token(UAUD,[C1],['auditeur'])}"}
    r=tc.post(f"/v1/runs/{run}/accounting",headers=H_aud)
    check("RBAC : auditeur NE PEUT PAS persister la comptabilité (403)", r.status_code==403, f"{r.status_code}")

    ok=sum(res); print(f"\nDéclaratif/comptable (Lot 5) : {ok}/{len(res)} PASS")
    if ok!=len(res): raise SystemExit(1)

if __name__=="__main__":
    main()
