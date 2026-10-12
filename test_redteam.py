"""
Red Team finale (contre-audit, section 35) : tentatives de contournement
APRÈS corrections. Un PASS = l'attaque échoue (le système résiste).
Complète test_p0_guards / test_security / test_declaratif (angles non déjà couverts).

Prérequis : cluster + migrations (001..005) + wasalaire_app ; PG* en env ; WASALAIRE_DEV=1.
"""
from __future__ import annotations
import sys, json, base64, hmac, hashlib, time
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from datetime import date
import psycopg
import payroll_service as ps
from payroll_service import WorkflowError
from fastapi.testclient import TestClient
from api_v2 import app, make_token, SECRET

W="66666666-0000-0000-0000-000000000001"; C1="66666666-0000-0000-0000-0000000000c1"
NODE="66666666-0000-0000-0000-0000000000a1"; RADM="66666666-0000-0000-0000-0000000000b1"
UADM="66666666-0000-0000-0000-0000000000e1"

res=[]
def check(l,c,d=""):
    res.append(bool(c)); print(f"  [{'PASS' if c else 'FAIL'}] {l}" + (f"  -> {d}" if d else ""))
def raises(fn, *exc):
    try: fn(); return False
    except exc or (Exception,): return True

def seed():
    s=psycopg.connect("",autocommit=True)
    s.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'WS','cabinet_comptable')",(W,))
    s.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Alpha',0.02)",(C1,W))
    s.execute("INSERT INTO org_node(id,tenant_id,type,nom,company_id) VALUES (%s,%s,'societe','Alpha',%s)",(NODE,W,C1))
    s.execute("INSERT INTO role(id,code) VALUES (%s,'admin')",(RADM,))
    s.execute("INSERT INTO app_user(id,telephone,telephone_verifie) VALUES (%s,'+22961000040',true)",(UADM,))
    s.execute("INSERT INTO access_grant(user_id,org_node_id,role_id) VALUES (%s,%s,%s)",(UADM,NODE,RADM))
    e=s.execute("INSERT INTO employee(company_id,matricule,nom,methode_paiement) "
                "VALUES (%s,'M001','KOFFI','especes') RETURNING id",(C1,)).fetchone()[0]
    s.execute("INSERT INTO contract(company_id,employee_id,type,date_debut,salaire_base,mode,statut) "
              "VALUES (%s,%s,'CDI','2025-01-01',200000,'mensuel','actif')",(C1,e))
    s.close()

def appc():
    c=psycopg.connect("",autocommit=True); c.execute("SET ROLE wasalaire_app"); ps.set_scope(c,[C1]); return c

def forge_expired_token(user_id):
    payload={"sub":user_id,"companies":[C1],"roles":["admin"],"exp":int(time.time())-10}
    body=base64.urlsafe_b64encode(json.dumps(payload,separators=(",",":")).encode()).decode().rstrip("=")
    sig=base64.urlsafe_b64encode(hmac.new(SECRET,body.encode(),hashlib.sha256).digest()).decode().rstrip("=")
    return f"{body}.{sig}"

def main():
    seed()
    tc=TestClient(app)

    # 1) Jeton expiré -> 401
    He={"Authorization":f"Bearer {forge_expired_token(UADM)}"}
    check("jeton expiré rejeté (401)", tc.get("/v1/me",headers=He).status_code==401)

    # 2) Jeton falsifié (signature invalide) -> 401
    good=make_token(UADM,[C1],["admin"]); tampered=good[:-2]+("aa" if good[-2:]!="aa" else "bb")
    check("jeton falsifié rejeté (401)",
          tc.get("/v1/me",headers={"Authorization":f"Bearer {tampered}"}).status_code==401)

    c=appc()
    # 3) Calcul sur période inexistante -> WorkflowError
    check("calcul sur période inexistante refusé",
          raises(lambda: ps.calculate_run(c,C1,"66666666-0000-0000-0000-0000000000ff",date(2026,1,1)), WorkflowError))

    # 4) Double run ACTIF sur une même période (invariant BD) -> violation unique
    p=ps.open_period(c,C1,1,2026)
    r1,_=ps.calculate_run(c,C1,p,date(2026,1,1))
    def _force_second_active():
        try:
            c.execute("INSERT INTO payroll_run(company_id,period_id,version_regles,actif) "
                      "VALUES (%s,%s,'x',true)",(C1,p))
        except psycopg.errors.UniqueViolation:
            raise WorkflowError("unique")
    check("deux runs actifs sur une période refusés (index unique)",
          raises(_force_second_active, WorkflowError))

    # 5) Montant extrême : brut très élevé -> calcul sans crash, ITS tranche 30%
    pe=ps.open_period(c,C1,2,2026)
    e1=c.execute("SELECT id FROM employee WHERE company_id=%s LIMIT 1",(C1,)).fetchone()[0]
    ps.add_variable(c,C1,e1,pe,"Prime exceptionnelle",50_000_000)
    rbig,_=ps.calculate_run(c,C1,pe,date(2026,2,1))
    rb=c.execute("SELECT resultat FROM payslip WHERE run_id=%s LIMIT 1",(rbig,)).fetchone()[0]
    check("montant extrême calculé sans crash (net>0, ITS>0)", rb["net"]>0 and rb["its"]>0,
          f"net={rb['net']}")

    # 6) Immuabilité après clôture via SQL direct (trigger) -> refus
    pc=ps.open_period(c,C1,3,2026)
    rc,_=ps.calculate_run(c,C1,pc,date(2026,3,1))
    ps.validate_and_close(c,pc,rc)
    def _mod_locked():
        try:
            c.execute("UPDATE payslip SET net_a_payer=1 WHERE run_id=%s",(rc,))
        except psycopg.errors.RaiseException:
            raise WorkflowError("locked")
    check("modification d'un bulletin clôturé refusée (trigger immuabilité)",
          raises(_mod_locked, WorkflowError))

    # 7) Recalcul après clôture via le service -> refusé (période clôturée)
    check("recalcul après clôture refusé",
          raises(lambda: ps.calculate_run(c,C1,pc,date(2026,3,1)), WorkflowError, psycopg.errors.RaiseException))
    c.close()

    ok=sum(res); print(f"\nRed Team finale : {ok}/{len(res)} attaques repoussées")
    if ok!=len(res): raise SystemExit(1)

if __name__=="__main__":
    main()
