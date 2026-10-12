"""
Tests de sécurité (Lot 4) : OTP durci, moindre privilège, révocation immédiate.
Prérequis : cluster + migrations (001..005) + rôle wasalaire_app ; PG* en env ;
WASALAIRE_DEV=1. Base fraîche recommandée.
"""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import psycopg
from fastapi.testclient import TestClient
from api_v2 import app

W="88888888-0000-0000-0000-000000000001"; C1="88888888-0000-0000-0000-0000000000c1"
NODE="88888888-0000-0000-0000-0000000000a1"; ROLE="88888888-0000-0000-0000-0000000000b1"
USER="88888888-0000-0000-0000-0000000000e1"; TEL="+22961000020"

res=[]
def check(l,c,d=""):
    res.append(bool(c)); print(f"  [{'PASS' if c else 'FAIL'}] {l}" + (f"  -> {d}" if d else ""))

def seed():
    s=psycopg.connect("",autocommit=True)
    s.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'WS','cabinet_comptable')",(W,))
    s.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Alpha',0.02)",(C1,W))
    s.execute("INSERT INTO org_node(id,tenant_id,type,nom,company_id) VALUES (%s,%s,'societe','Alpha',%s)",(NODE,W,C1))
    s.execute("INSERT INTO role(id,code) VALUES (%s,'admin')",(ROLE,))
    s.execute("INSERT INTO app_user(id,telephone,telephone_verifie) VALUES (%s,%s,true)",(USER,TEL))
    s.execute("INSERT INTO access_grant(user_id,org_node_id,role_id) VALUES (%s,%s,%s)",(USER,NODE,ROLE))
    s.close()

def main():
    seed()
    c=TestClient(app)

    # 1) Anti-énumération : numéro inconnu -> réponse générique, aucun compte créé, aucun défi.
    before = psycopg.connect("",autocommit=True).execute("SELECT count(*) FROM app_user").fetchone()[0]
    r=c.post("/v1/auth/request-otp",json={"telephone":"+22999999999","canal":"sms"})
    after = psycopg.connect("",autocommit=True).execute("SELECT count(*) FROM app_user").fetchone()[0]
    ch = psycopg.connect("",autocommit=True).execute("SELECT count(*) FROM otp_challenge WHERE telephone='+22999999999'").fetchone()[0]
    check("OTP numéro inconnu → réponse générique sent=true", r.status_code==200 and r.json().get("sent") is True)
    check("OTP numéro inconnu → aucun compte créé", after==before, f"{before}->{after}")
    check("OTP numéro inconnu → aucun défi créé", ch==0)
    check("OTP numéro inconnu → pas de dev_code divulgué", "dev_code" not in r.json())

    # 2) Anti-abus : 3 demandes OK puis 429.
    codes_ok = all(c.post("/v1/auth/request-otp",json={"telephone":TEL,"canal":"sms"}).status_code==200
                   for _ in range(3))
    r4 = c.post("/v1/auth/request-otp",json={"telephone":TEL,"canal":"sms"})
    check("OTP anti-abus : 3 OK puis 429", codes_ok and r4.status_code==429, f"4e={r4.status_code}")

    # 3) Moindre privilège : le rôle applicatif ne peut pas écrire le référentiel ni lire l'audit.
    ap=psycopg.connect("",autocommit=True); ap.execute("SET ROLE wasalaire_app")
    def denied(sql):
        try:
            ap.execute(sql); return False
        except psycopg.errors.InsufficientPrivilege:
            return True
        except Exception:
            return True
    check("moindre privilège : INSERT rate_table refusé (référentiel lecture seule)",
          denied("INSERT INTO rate_table(code,valeur,date_effet,source) VALUES ('x',1,'2026-01-01','t')"))
    check("moindre privilège : SELECT audit_log refusé (audit écriture seule)",
          denied("SELECT * FROM audit_log LIMIT 1"))
    ap.close()

    # 4) Révocation immédiate : suppression du grant -> périmètre vide à la requête suivante.
    #    (le périmètre/rôles sont re-dérivés de la BD, pas lus du jeton)
    from api_v2 import make_token
    H={"Authorization": f"Bearer {make_token(USER,[C1],['admin'])}"}
    me1=c.get("/v1/me",headers=H)
    su=psycopg.connect("",autocommit=True)
    su.execute("DELETE FROM access_grant WHERE user_id=%s",(USER,))
    me2=c.get("/v1/me",headers=H)
    su.close()
    # Après retrait du grant : plus de périmètre ni de rôle -> accès refusé immédiatement.
    check("révocation immédiate : accès (200,[C1]) avant, refusé (403) après suppression du grant",
          me1.status_code==200 and me1.json().get("companies")==[C1] and me2.status_code==403,
          f"me1={me1.status_code} me2={me2.status_code}")

    ok=sum(res); print(f"\nSécurité (Lot 4) : {ok}/{len(res)} PASS")
    if ok!=len(res): raise SystemExit(1)

if __name__=="__main__":
    main()
