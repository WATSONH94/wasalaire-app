"""
Tests de GARDE des P0 (issus du contre-audit d'octobre 2026).
Chaque test rejoue l'ancien comportement dangereux et vérifie qu'il est DÉSORMAIS
bloqué. Un PASS = la faille est fermée. Non-régression obligatoire.

Prérequis : cluster + migrations (001..004) + rôle wasalaire_app ; PG* en env.
Base dédiée recommandée (fixtures avec identifiants fixes).
"""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from datetime import date
import psycopg
import payroll_service as ps
from payroll_service import WorkflowError
from fastapi.testclient import TestClient
from api_v2 import app, make_token

W   = "99999999-0000-0000-0000-000000000001"
C1  = "99999999-0000-0000-0000-0000000000c1"
C2  = "99999999-0000-0000-0000-0000000000c2"
CAB = "99999999-0000-0000-0000-0000000000a0"
NA  = "99999999-0000-0000-0000-0000000000a1"
NB  = "99999999-0000-0000-0000-0000000000a2"
RADM= "99999999-0000-0000-0000-0000000000b1"
RAUD= "99999999-0000-0000-0000-0000000000b2"
UADM= "99999999-0000-0000-0000-0000000000e1"
UAUD= "99999999-0000-0000-0000-0000000000e2"
UNONE="99999999-0000-0000-0000-0000000000e3"   # utilisateur sans aucun grant

res = []
def check(label, cond, detail=""):
    res.append(bool(cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))

def raises_workflow(fn) -> bool:
    try:
        fn(); return False
    except WorkflowError:
        return True

def su():
    return psycopg.connect("", autocommit=True)

def appconn(scope):
    c = psycopg.connect("", autocommit=True)
    c.execute("SET ROLE wasalaire_app")
    ps.set_scope(c, scope)
    return c

def seed():
    s = su()
    s.execute("INSERT INTO workspace(id,nom,type) VALUES (%s,'Cabinet','cabinet_comptable')",(W,))
    s.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Alpha SARL',0.02)",(C1,W))
    s.execute("INSERT INTO company(id,workspace_id,raison_sociale,taux_atmp) VALUES (%s,%s,'Beta SARL',0.02)",(C2,W))
    s.execute("INSERT INTO org_node(id,tenant_id,type,nom) VALUES (%s,%s,'cabinet','Cabinet')",(CAB,W))
    s.execute("INSERT INTO org_node(id,tenant_id,type,parent_id,nom,company_id) VALUES (%s,%s,'societe',%s,'Alpha',%s)",(NA,W,CAB,C1))
    s.execute("INSERT INTO org_node(id,tenant_id,type,parent_id,nom,company_id) VALUES (%s,%s,'societe',%s,'Beta',%s)",(NB,W,CAB,C2))
    s.execute("INSERT INTO role(id,code) VALUES (%s,'admin'),(%s,'auditeur')",(RADM,RAUD))
    s.execute("INSERT INTO app_user(id,telephone,telephone_verifie) VALUES (%s,'+22961000011',true)",(UADM,))
    s.execute("INSERT INTO app_user(id,telephone,telephone_verifie) VALUES (%s,'+22961000012',true)",(UAUD,))
    s.execute("INSERT INTO access_grant(user_id,org_node_id,role_id) VALUES (%s,%s,%s)",(UADM,CAB,RADM))
    s.execute("INSERT INTO access_grant(user_id,org_node_id,role_id) VALUES (%s,%s,%s)",(UAUD,CAB,RAUD))
    s.execute("INSERT INTO app_user(id,telephone,telephone_verifie) VALUES (%s,'+22961000013',true)",(UNONE,))
    for (c, mat, nom) in [(C1,'A001','ALPHA Salarié'),(C2,'B001','BETA Salarié')]:
        e = s.execute("INSERT INTO employee(company_id,matricule,nom,methode_paiement,momo_operateur,momo_numero) "
                      "VALUES (%s,%s,%s,'mobile_money','MTN','+22990000001') RETURNING id",(c,mat,nom)).fetchone()[0]
        s.execute("INSERT INTO contract(company_id,employee_id,type,date_debut,salaire_base,mode,statut) "
                  "VALUES (%s,%s,'CDI','2025-01-01',200000,'mensuel','actif')",(c,e))
    s.close()

def main():
    seed()
    c = appconn([C1, C2])

    # ---- P0-01 : réouverture d'une période clôturée INTERDITE ----
    p1 = ps.open_period(c, C1, 3, 2026)
    run1, _ = ps.calculate_run(c, C1, p1, date(2026,3,1))
    ps.validate_and_close(c, p1, run1)
    check("P0-01 open_period sur période clôturée refusé",
          raises_workflow(lambda: ps.open_period(c, C1, 3, 2026)))
    # Un nouveau run sur une période clôturée est refusé par la BD (trigger).
    def _calc_closed():
        try:
            ps.calculate_run(c, C1, p1, date(2026,3,1))
        except (WorkflowError, psycopg.errors.RaiseException):
            raise WorkflowError("bloqué")
    check("P0-01 nouveau run sur période clôturée refusé", raises_workflow(_calc_closed))

    # ---- P0-06 : clôture croisée run(C1)+période(C2) INTERDITE ----
    p1c = ps.open_period(c, C1, 6, 2026)
    run1c, _ = ps.calculate_run(c, C1, p1c, date(2026,6,1))
    p2 = ps.open_period(c, C2, 6, 2026)
    check("P0-06 clôture croisée run(C1)+période(C2) refusée",
          raises_workflow(lambda: ps.validate_and_close(c, p2, run1c)))

    # ---- P0-06 : FK composite empêche un bulletin inter-sociétés (niveau BD) ----
    s = su()  # superuser : contourne la RLS mais PAS les FK
    try:
        s.execute("INSERT INTO payslip(company_id,run_id,employee_id,brut,net_a_payer) "
                  "SELECT %s,%s,e.id,1,1 FROM employee e WHERE e.company_id=%s LIMIT 1",
                  (C2, run1c, C2))
        fk_ok = False
    except psycopg.errors.ForeignKeyViolation:
        fk_ok = True
    s.close()
    check("P0-06 FK composite rejette payslip(run C1 / société C2)", fk_ok)

    # ---- P0-02 : clôture bloquée par anomalie, déblocable par dérogation tracée ----
    p_neg = ps.open_period(c, C1, 4, 2026)
    e1 = c.execute("SELECT id FROM employee WHERE company_id=%s LIMIT 1",(C1,)).fetchone()[0]
    ps.add_variable(c, C1, e1, p_neg, "Retenue exceptionnelle", -500000)
    run_neg, _ = ps.calculate_run(c, C1, p_neg, date(2026,4,1))
    check("P0-02 clôture refusée tant qu'une anomalie bloquante subsiste",
          raises_workflow(lambda: ps.validate_and_close(c, p_neg, run_neg)))
    # dérogation motivée : autorisée mais tracée en audit
    ps.validate_and_close(c, p_neg, run_neg, actor=UADM, override_reason="test dérogation")
    st = c.execute("SELECT statut FROM payroll_period WHERE id=%s",(p_neg,)).fetchone()[0]
    # L'audit est en écriture seule pour le runtime (moindre privilège) : on le lit hors-bande.
    aud = su().execute("SELECT count(*) FROM audit_log WHERE action='period.close' "
                       "AND apres->>'override' IS NOT NULL").fetchone()[0]
    check("P0-02 dérogation motivée possible ET auditée", st=="cloturee" and aud>=1, f"audit={aud}")

    # ---- P0-04 : décaissement AVANT clôture interdit ; idempotent après clôture ----
    p_pay = ps.open_period(c, C1, 5, 2026)
    run_pay, _ = ps.calculate_run(c, C1, p_pay, date(2026,5,1))
    check("P0-04 décaissement avant clôture refusé",
          raises_workflow(lambda: ps.create_payout(c, C1, run_pay)))
    check("P0-04 décaissement avec company_id≠run refusé",
          raises_workflow(lambda: ps.create_payout(c, C2, run_pay)))
    ps.validate_and_close(c, p_pay, run_pay)
    ps.create_payout(c, C1, run_pay)
    ps.create_payout(c, C1, run_pay)   # 2e appel : idempotent
    nb = c.execute("SELECT count(*) FROM payout_batch WHERE run_id=%s",(run_pay,)).fetchone()[0]
    check("P0-04 un seul lot par run (idempotent)", nb==1, f"{nb} batch")

    # ---- P0-01 : run superseded (N3) ----
    p_sup = ps.open_period(c, C1, 7, 2026)
    r_old, _ = ps.calculate_run(c, C1, p_sup, date(2026,7,1))
    r_new, _ = ps.calculate_run(c, C1, p_sup, date(2026,7,1))  # supersede r_old
    actifs = c.execute("SELECT count(*) FROM payroll_run WHERE period_id=%s AND actif",(p_sup,)).fetchone()[0]
    check("N3 un seul run actif par période", actifs==1 and r_old!=r_new, f"{actifs} actif(s)")
    check("P0-01 clôture d'un run inactif refusée",
          raises_workflow(lambda: ps.validate_and_close(c, p_sup, r_old)))

    # ---- P0-05 : AMO inactive par défaut ; active UNIQUEMENT si date d'effet configurée ----
    import os as _os
    _os.environ.pop("WASALAIRE_AMO_DATE_EFFET", None)
    p_amo = ps.open_period(c, C1, 11, 2026)
    run_amo, _ = ps.calculate_run(c, C1, p_amo, date(2026, 11, 1))
    r_off = c.execute("SELECT resultat FROM payslip WHERE run_id=%s LIMIT 1", (run_amo,)).fetchone()[0]
    check("P0-05 AMO inactive par défaut (amo=0, date d'effet non établie)",
          r_off.get("amo_sal", 0) == 0 and r_off.get("amo_pat", 0) == 0)
    _os.environ["WASALAIRE_AMO_DATE_EFFET"] = "2026-10-29"   # simule l'instrument approuvé
    try:
        p_amo2 = ps.open_period(c, C1, 12, 2026)
        run_amo2, _ = ps.calculate_run(c, C1, p_amo2, date(2026, 12, 1))
        r_on = c.execute("SELECT resultat FROM payslip WHERE run_id=%s LIMIT 1", (run_amo2,)).fetchone()[0]
        check("P0-05 AMO alimentée en persistance si date d'effet configurée (amo>0)",
              r_on.get("amo_sal", 0) > 0 and r_on.get("amo_pat", 0) > 0,
              f"amo_sal={r_on.get('amo_sal')} amo_pat={r_on.get('amo_pat')}")
    finally:
        _os.environ.pop("WASALAIRE_AMO_DATE_EFFET", None)

    # ---- Lot 3 : séparation des tâches (4 yeux), activable ----
    p_4e = ps.open_period(c, C1, 9, 2026)
    r_4e, _ = ps.calculate_run(c, C1, p_4e, date(2026, 9, 1))
    ps.validate_and_close(c, p_4e, r_4e, actor=UADM)        # UADM valide la clôture
    _os.environ["WASALAIRE_FOUR_EYES"] = "1"
    try:
        check("Lot3 4-yeux : le valideur de la clôture ne peut pas décaisser",
              raises_workflow(lambda: ps.create_payout(c, C1, r_4e, actor=UADM)))
        ps.create_payout(c, C1, r_4e, actor=UAUD)           # un second acteur : autorisé
        nb4 = c.execute("SELECT count(*) FROM payout_batch WHERE run_id=%s", (r_4e,)).fetchone()[0]
        check("Lot3 4-yeux : un second acteur peut décaisser", nb4 == 1)
    finally:
        _os.environ.pop("WASALAIRE_FOUR_EYES", None)

    # ---- Lot 3 : outbox, pas de double émission externe en reprise ----
    class CountingGW:
        canal = "mock"; sends = 0
        def send(self, item):
            CountingGW.sends += 1
            return {"statut": "envoye", "reference_operateur": f"REF{CountingGW.sends}",
                    "accuse": {"ok": True}}
    p_ob = ps.open_period(c, C1, 10, 2026)
    r_ob, _ = ps.calculate_run(c, C1, p_ob, date(2026, 10, 1))
    ps.validate_and_close(c, p_ob, r_ob)
    gw = CountingGW()
    ps.create_payout(c, C1, r_ob, gateway=gw)
    ps.create_payout(c, C1, r_ob, gateway=gw)               # reprise : ne doit PAS ré-émettre
    check("Lot3 outbox : pas de double émission externe en reprise", CountingGW.sends == 1,
          f"{CountingGW.sends} envoi(s)")
    c.close()

    # ---- P0-03 : RBAC (API) - rôle 'auditeur' ne peut ni clôturer ni payer ----
    tc = TestClient(app)
    H_aud = {"Authorization": f"Bearer {make_token(UAUD, [C1, C2], ['auditeur'])}"}
    H_adm = {"Authorization": f"Bearer {make_token(UADM, [C1, C2], ['admin'])}"}
    # admin prépare un run propre
    pj = tc.post("/v1/periods", headers=H_adm, json={"company_id":C1,"mois":8,"annee":2026}).json()["period_id"]
    rj = tc.post("/v1/periods/calculate", headers=H_adm,
                 json={"company_id":C1,"period_id":pj,"periode":"2026-08-01"}).json()["run_id"]
    check("P0-03 auditeur NE PEUT PAS clôturer (403)",
          tc.post(f"/v1/runs/{rj}/close", headers=H_aud, params={"period_id":pj}).status_code==403)
    # admin clôture
    check("P0-03 admin PEUT clôturer (200)",
          tc.post(f"/v1/runs/{rj}/close", headers=H_adm, params={"period_id":pj}).status_code==200)
    check("P0-03 auditeur NE PEUT PAS décaisser (403)",
          tc.post(f"/v1/runs/{rj}/payout", headers=H_aud, params={"company_id":C1}).status_code==403)
    check("P0-03 auditeur PEUT lire les contrôles (200)",
          tc.get(f"/v1/runs/{rj}/controls", headers=H_aud).status_code==200)
    # utilisateur SANS grant → périmètre et rôles vides (re-dérivés de la BD) → tout refusé
    H_none = {"Authorization": f"Bearer {make_token(UNONE, [C1], ['admin'])}"}  # rôle du jeton ignoré
    check("P0-03 utilisateur sans grant → clôture refusée (deny-by-default, révocation immédiate)",
          tc.post(f"/v1/runs/{rj}/close", headers=H_none, params={"period_id":pj}).status_code==403)

    ok = sum(res)
    print(f"\nGARDES P0 : {ok}/{len(res)} PASS (chaque PASS = faille fermée)")
    if ok != len(res):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
