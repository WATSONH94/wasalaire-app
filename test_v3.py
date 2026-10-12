"""Tests v3 : RH (entrée/sortie/congés), campagne, reporting, notifications, WaDocs.
Prérequis : cluster + schema.sql + v2 + v3 + rôle wasalaire_app ; PG* en env."""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import psycopg
from fastapi.testclient import TestClient
from api_v2 import app
from wadocs import merge
from notifications import notify, list_notifications
from payroll_service import set_scope

W="ffffffff-0000-0000-0000-000000000001"; C1="ffffffff-0000-0000-0000-0000000000c1"
GRP="ffffffff-0000-0000-0000-0000000000a2"; SOC="ffffffff-0000-0000-0000-0000000000a1"
ROLE="ffffffff-0000-0000-0000-0000000000b1"; USER="ffffffff-0000-0000-0000-0000000000e1"
TEL="+22961000010"
results=[]
def check(l,c): results.append(bool(c)); print(f"  [{'PASS' if c else 'FAIL'}] {l}")

def seed():
    su=psycopg.connect("",autocommit=True)
    su.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'WS','cabinet_comptable')",(W,))
    su.execute("INSERT INTO company(id,workspace_id,raison_sociale,ifu) VALUES (%s,%s,'Alpha SARL','1234567890123')",(C1,W))
    su.execute("INSERT INTO org_node(id,tenant_id,type,nom) VALUES (%s,%s,'groupe','Groupe ADJOVI')",(GRP,W))
    su.execute("INSERT INTO org_node(id,tenant_id,type,parent_id,nom,company_id) VALUES (%s,%s,'societe',%s,'Alpha',%s)",(SOC,W,GRP,C1))
    su.execute("INSERT INTO role(id,code) VALUES (%s,'admin')",(ROLE,))
    su.execute("INSERT INTO app_user(id,telephone,telephone_verifie) VALUES (%s,%s,true)",(USER,TEL))
    su.execute("INSERT INTO access_grant(user_id,org_node_id,role_id) VALUES (%s,%s,%s)",(USER,GRP,ROLE))
    su.close()

def main():
    # 0) merge WaDocs (unitaire, sans BD)
    r = merge("Bonjour {{Salarié.nom}}, salaire {{Contrat.salaire | money}}.",
              {"Salarié":{"nom":"KOFFI Alain"},"Contrat":{"salaire":200000}})
    check("WaDocs merge (champs + money)", r=="Bonjour KOFFI Alain, salaire 200 000 F.")
    check("WaDocs champ manquant visible", "[X ?]" in merge("{{X}}", {}))

    seed()
    c=TestClient(app)
    tok=c.post("/v1/auth/verify-otp",json={"telephone":TEL,"code":
        c.post("/v1/auth/request-otp",json={"telephone":TEL,"canal":"sms"}).json()["dev_code"]}).json()["token"]
    H={"Authorization":f"Bearer {tok}"}

    # 1) Entrée salarié + contrôle SMIG
    r=c.post("/v1/employees",headers=H,json={"company_id":C1,"matricule":"M001","nom":"KOFFI Alain","salaire_base":200000,"num_cnss":"CNSS1"})
    emp=r.json().get("employee_id"); check("création salarié",r.status_code==200 and emp)
    r=c.post("/v1/employees",headers=H,json={"company_id":C1,"matricule":"M002","nom":"Trop bas","salaire_base":40000})
    check("SMIG < 52000 → refus 422",r.status_code==422)

    # 2) Congés : demande → validation → solde
    lid=c.post("/v1/leaves",headers=H,json={"company_id":C1,"employee_id":emp,"type":"conge_annuel","date_debut":"2026-10-12","date_fin":"2026-10-20","jours":7}).json()["leave_id"]
    check("demande de congé créée",bool(lid))
    check("validation congé",c.post(f"/v1/leaves/{lid}/validate?accord=true",headers=H).status_code==200)
    bal=c.get(f"/v1/employees/{emp}/leave-balance?mois_service=12&anciennete_ans=0",headers=H).json()
    check("solde congé = acquis 24 − pris 7 = 17",bal["solde"]==17.0)

    # 3) Campagne multi-société
    camp=c.post("/v1/campaigns",headers=H,json={"org_node_id":GRP,"mois":9,"annee":2026}).json()["campaign_id"]
    check("campagne créée",bool(camp))
    check("statut campagne (structure)","societes" in c.get(f"/v1/campaigns/{camp}/status",headers=H).json())

    # 4) Reporting réel
    rep=c.get(f"/v1/reporting?company_id={C1}",headers=H).json()
    check("reporting effectif ≥ 1",rep["effectif"]>=1 and "cout_employeur" in rep)

    # 5) WaDocs génération document
    doc=c.post("/v1/documents/generate",headers=H,json={"company_id":C1,"employee_id":emp,"titre":"Contrat KOFFI"}).json()
    check("document généré (fusion nom+salaire)","KOFFI Alain" in doc["contenu"] and "200 000 F" in doc["contenu"])
    check("liste documents",len(c.get(f"/v1/documents?company_id={C1}",headers=H).json()["documents"])>=1)

    # 6) Notifications (service + API)
    app_conn=psycopg.connect("",autocommit=True); app_conn.execute("SET ROLE wasalaire_app"); set_scope(app_conn,[C1])
    notify(app_conn,C1,"salaire_envoye","Salaires envoyés (3 salariés)",canal="log")
    check("notification listée via API",len(c.get(f"/v1/notifications?company_id={C1}",headers=H).json()["notifications"])>=1)

    # 7) Sortie (solde de tout compte)
    rup=c.post(f"/v1/employees/{emp}/rupture",headers=H,json={"company_id":C1,"type_rupture":"licenciement","anciennete_ans":8}).json()
    check("rupture → net estimé calculé",rup.get("net_estime",0)>0)

    ok=sum(results); print(f"\nv3 (RH/congés/campagne/reporting/notif/WaDocs) : {ok}/{len(results)} PASS")
    if ok!=len(results): raise SystemExit(1)

if __name__=="__main__": main()
