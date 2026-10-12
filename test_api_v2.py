"""
Preuve bout-en-bout de l'API v2 PERSISTANTE : téléphone+OTP → jeton scope →
cycle de paie persisté → contrôle de périmètre. Exécute la vraie app FastAPI
(TestClient) contre PostgreSQL réel. Prérequis : cluster + schema.sql +
schema-v2-deltas.sql + rôle wasalaire_app (voir script d'orchestration) ;
PG* en environnement.
"""
from __future__ import annotations
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import psycopg
from fastapi.testclient import TestClient
from api_v2 import app

W  = "dddddddd-0000-0000-0000-000000000001"
C1 = "dddddddd-0000-0000-0000-0000000000c1"
C2 = "dddddddd-0000-0000-0000-0000000000c2"
NODE = "dddddddd-0000-0000-0000-0000000000a1"
ROLE = "dddddddd-0000-0000-0000-0000000000b1"
USER = "dddddddd-0000-0000-0000-0000000000e1"
TEL = "+22961000009"

results = []
def check(label, cond):
    results.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

def seed():
    su = psycopg.connect("", autocommit=True)
    su.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'Cab','cabinet_comptable')", (W,))
    su.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Alpha SARL',0.02)", (C1, W))
    su.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Beta SARL',0.02)", (C2, W))
    su.execute("INSERT INTO org_node(id,tenant_id,type,nom,company_id) VALUES (%s,%s,'societe','Alpha',%s)", (NODE, W, C1))
    su.execute("INSERT INTO role(id,code) VALUES (%s,'admin')", (ROLE,))
    su.execute("INSERT INTO app_user(id,telephone,telephone_verifie) VALUES (%s,%s,false)", (USER, TEL))
    su.execute("INSERT INTO access_grant(user_id,org_node_id,role_id) VALUES (%s,%s,%s)", (USER, NODE, ROLE))
    e1 = su.execute("INSERT INTO employee(company_id,matricule,nom,methode_paiement,momo_operateur,momo_numero) "
                    "VALUES (%s,'M001','KOFFI Alain','mobile_money','MTN','+22990000001') RETURNING id", (C1,)).fetchone()[0]
    su.execute("INSERT INTO contract(company_id,employee_id,type,date_debut,salaire_base,mode,statut) VALUES (%s,%s,'CDI','2025-01-01',200000,'mensuel','actif')", (C1, e1))
    su.close()
    return str(e1)

def main():
    e1 = seed()
    c = TestClient(app)

    # 1) OTP : demande → code (DEV) → vérification → jeton portant le périmètre
    r = c.post("/v1/auth/request-otp", json={"telephone": TEL, "canal": "whatsapp"})
    code = r.json().get("dev_code")
    check("request-otp renvoie un code (DEV)", r.status_code == 200 and code)

    r = c.post("/v1/auth/verify-otp", json={"telephone": TEL, "code": "000000"})
    check("OTP incorrect → 401", r.status_code == 401)

    r = c.post("/v1/auth/verify-otp", json={"telephone": TEL, "code": code})
    tok = r.json().get("token")
    companies = r.json().get("companies", [])
    check("verify-otp → jeton + périmètre = [Alpha]", r.status_code == 200 and tok and companies == [C1])
    H = {"Authorization": f"Bearer {tok}"}

    # 2) Sans jeton → 401
    check("endpoint protégé sans jeton → 401", c.get("/v1/me").status_code == 401)

    # 3) Cycle : période → variable (prime) → calcul
    r = c.post("/v1/periods", headers=H, json={"company_id": C1, "mois": 1, "annee": 2026})
    pid = r.json().get("period_id"); check("ouverture période", r.status_code == 200 and pid)

    r = c.post("/v1/periods/variables", headers=H, json={
        "company_id": C1, "period_id": pid, "employee_id": e1, "type": "Prime", "montant": 30000})
    check("ajout variable (prime)", r.status_code == 200)

    r = c.post("/v1/periods/calculate", headers=H,
               json={"company_id": C1, "period_id": pid, "periode": "2026-01-01"})
    run_id = r.json().get("run_id"); check("calcul run (1 bulletin)", r.json().get("bulletins") == 1)

    # 4) Contrôles : aucun bloquant (base ≥ SMIG, net > 0)
    r = c.get(f"/v1/runs/{run_id}/controls", headers=H)
    check("contrôles : 0 bloquant", r.json().get("bloquants") == 0)

    # 5) Déclaration : ITS agrégé (base 200k + prime 30k → ITS 21 000)
    r = c.get(f"/v1/runs/{run_id}/declaration", headers=H)
    check("déclaration ITS total = 21 000", r.json()["its_vps"]["its_total"] == 21000)

    # 6) Décaissement AVANT clôture → refusé (P0-04, garde)
    r = c.post(f"/v1/runs/{run_id}/payout", headers=H, params={"company_id": C1})
    check("décaissement avant clôture refusé (409)", r.status_code == 409)

    # 7) Clôture + bulletin verrouillé
    r = c.post(f"/v1/runs/{run_id}/close", headers=H, params={"period_id": pid})
    check("clôture", r.status_code == 200)
    b = c.get(f"/v1/runs/{run_id}/payslips", headers=H).json()["bulletins"][0]
    check("bulletin : net = 200 720, verrouillé", b["net"] == 200720 and b["verrouille"] is True)

    # 8) Décaissement APRÈS clôture : mobile money (net 200 720)
    r = c.post(f"/v1/runs/{run_id}/payout", headers=H, params={"company_id": C1})
    pm = r.json()["par_methode"]
    check("décaissement mobile money = 200 720 (après clôture)",
          pm.get("mobile_money", {}).get("montant") == 200720)

    # 9) Contrôle de périmètre → 403
    r = c.post("/v1/periods", headers=H, json={"company_id": C2, "mois": 1, "annee": 2026})
    check("société hors périmètre → 403", r.status_code == 403)

    ok = sum(results)
    print(f"\nAPI v2 (OTP + persistance + scope) : {ok}/{len(results)} PASS")
    if ok != len(results):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
