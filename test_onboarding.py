"""
Recette des endpoints d'onboarding (structure société) : établissement, département,
poste, contrat — avec preuve d'ISOLATION (société hors périmètre refusée) et garde SMIG.
Exécute la vraie app FastAPI (TestClient) contre PostgreSQL réel. Prérequis : cluster +
migrations + rôle wasalaire_app ; PG* en environnement (voir CI).
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

W    = "cccccccc-0000-0000-0000-000000000001"
C1   = "cccccccc-0000-0000-0000-0000000000c1"
C2   = "cccccccc-0000-0000-0000-0000000000c2"
NODE = "cccccccc-0000-0000-0000-0000000000a1"
ROLE = "cccccccc-0000-0000-0000-0000000000b1"
USER = "cccccccc-0000-0000-0000-0000000000e1"
TEL  = "+22961000021"

results = []
def check(label, cond):
    results.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

def seed():
    su = psycopg.connect("", autocommit=True)
    su.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'Cab','cabinet_comptable')", (W,))
    su.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Alpha SARL',0.02)", (C1, W))
    su.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Beta SARL',0.02)", (C2, W))
    # Seul C1 est rattaché à un nœud sous le grant → seul C1 est dans le périmètre de USER.
    su.execute("INSERT INTO org_node(id,tenant_id,type,nom,company_id) VALUES (%s,%s,'societe','Alpha',%s)", (NODE, W, C1))
    su.execute("INSERT INTO role(id,code) VALUES (%s,'admin')", (ROLE,))
    su.execute("INSERT INTO app_user(id,telephone,telephone_verifie) VALUES (%s,%s,false)", (USER, TEL))
    su.execute("INSERT INTO access_grant(user_id,org_node_id,role_id) VALUES (%s,%s,%s)", (USER, NODE, ROLE))
    e1 = su.execute("INSERT INTO employee(company_id,matricule,nom) VALUES (%s,'M100','AGBO Rita') RETURNING id", (C1,)).fetchone()[0]
    su.close()
    return str(e1)

def _token(c):
    r = c.post("/v1/auth/request-otp", json={"telephone": TEL, "canal": "sms"})
    code = r.json().get("dev_code")
    r = c.post("/v1/auth/verify-otp", json={"telephone": TEL, "code": code})
    return r.json()["token"]

def main():
    e1 = seed()
    c = TestClient(app)
    H = {"Authorization": f"Bearer {_token(c)}"}

    # 1) Établissement
    r = c.post("/v1/establishments", headers=H, json={"company_id": C1, "nom": "Siège Cotonou", "adresse": "Cotonou"})
    est_id = r.json().get("establishment_id"); check("création établissement", r.status_code == 200 and est_id)
    check("liste établissements = 1", len(c.get("/v1/establishments", headers=H, params={"company_id": C1}).json()["etablissements"]) == 1)

    # 2) Département
    r = c.post("/v1/departments", headers=H, json={"company_id": C1, "nom": "Comptabilité", "centre_de_cout": "CC01"})
    dep_id = r.json().get("department_id"); check("création département", r.status_code == 200 and dep_id)

    # 3) Poste (catégorie valide / invalide)
    r = c.post("/v1/positions", headers=H, json={"company_id": C1, "intitule": "Comptable", "categorie": "cadre"})
    pos_id = r.json().get("position_id"); check("création poste (cadre)", r.status_code == 200 and pos_id)
    check("poste catégorie invalide → 422",
          c.post("/v1/positions", headers=H, json={"company_id": C1, "intitule": "X", "categorie": "roi"}).status_code == 422)

    # 4) Contrat (relie salarié + poste + département + établissement)
    r = c.post("/v1/contracts", headers=H, json={
        "company_id": C1, "employee_id": e1, "type_contrat": "CDI", "date_debut": "2026-01-01",
        "salaire_base": 150000, "position_id": pos_id, "department_id": dep_id, "establishment_id": est_id})
    check("création contrat", r.status_code == 200 and r.json().get("contract_id"))
    check("liste contrats du salarié = 1",
          len(c.get("/v1/contracts", headers=H, params={"company_id": C1, "employee_id": e1}).json()["contrats"]) == 1)

    # 5) Garde SMIG : salaire sous le SMIG → 422
    check("contrat sous SMIG refusé (422)",
          c.post("/v1/contracts", headers=H, json={
              "company_id": C1, "employee_id": e1, "type_contrat": "CDI",
              "date_debut": "2026-01-01", "salaire_base": 10000}).status_code == 422)

    # 6) ISOLATION : société hors périmètre (C2) → 403 sur chaque création
    check("établissement sur société hors périmètre → 403",
          c.post("/v1/establishments", headers=H, json={"company_id": C2, "nom": "X"}).status_code == 403)
    check("liste établissements hors périmètre → 403",
          c.get("/v1/establishments", headers=H, params={"company_id": C2}).status_code == 403)

    ok = sum(results)
    print(f"\nOnboarding (structure + isolation + SMIG) : {ok}/{len(results)} PASS")
    if ok != len(results):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
