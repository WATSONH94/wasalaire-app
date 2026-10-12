"""
API v2 — PERSISTANTE et SCOPE-ISOLÉE (remplace le cœur in-memory d'api_demo.py).
Chaîne complète : identité téléphone + OTP → jeton portant le périmètre →
cycle de paie persisté en PostgreSQL via `payroll_service` (moteur testé) →
isolation multi-tenant assurée par la BD (scope-RLS validée).

⚠️ Prototype : OTP renvoyé en clair en mode DEV (pas de passerelle SMS/WhatsApp
branchée) ; jeton HMAC minimal (pas de dépendance JWT) ; à durcir en production
(OIDC/MFA, secret en coffre, envoi OTP réel, HTTPS, rate-limit).

Lancer :  uvicorn api_v2:app          (nécessite PG* en environnement)
Tester :  python test_api_v2.py       (cluster + schéma + deltas requis)
"""
from __future__ import annotations
import os, json, hmac, base64, hashlib, secrets, time
from datetime import date, datetime, timezone, timedelta

import psycopg
from psycopg_pool import ConnectionPool
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel

from moteur_paie import param
from payroll_service import (
    set_scope, open_period, calculate_run, validate_and_close, list_payslips,
    add_variable, run_controls, declaration_aggregate, create_payout, list_payout,
    persist_declaration, persist_accounting,
    list_employees, list_companies, WorkflowError,
    create_campaign, attach_run_to_campaign, campaign_status, reporting_summary,
    import_variables, effective_allowed_roles, set_permission_override,
    list_permission_overrides, get_governance_policy, set_governance_policy,
)
from rh_service import (create_employee as rh_create_employee, rupture as rh_rupture,
                        request_leave, validate_leave, leave_balance)
from notifications import notify, list_notifications, WhatsAppGateway, SmsGateway, LogGateway
from wadocs import CONTRAT_TEMPLATE, generate_document, list_documents

_DEFAULT_SECRET = "dev-secret-change-me"
SECRET = os.environ.get("WASALAIRE_SECRET", _DEFAULT_SECRET).encode()
DEV = os.environ.get("WASALAIRE_DEV", "1") == "1"      # renvoie l'OTP en clair (démo)
OTP_TTL_MIN = 5
TOKEN_TTL_S = 3600

# Fail-closed (P1-11) : en production (DEV=0), refuser de démarrer avec un secret
# vide, par défaut connu, ou trop court. Couvre aussi les valeurs par défaut de compose.
_SECRET_RAW = os.environ.get("WASALAIRE_SECRET", _DEFAULT_SECRET)
_WEAK_SECRETS = {"", _DEFAULT_SECRET, "change-me-in-prod", "changeme", "secret"}
if not DEV and (_SECRET_RAW in _WEAK_SECRETS or len(_SECRET_RAW) < 16):
    raise RuntimeError(
        "WASALAIRE_SECRET faible ou absent en production : démarrage refusé (fail-closed). "
        "Définir un secret fort (>= 16 caractères, en coffre) ou, pour une démo, WASALAIRE_DEV=1.")

app = FastAPI(title="WaSalaire API v2 (persistante)", version="2.0.0")

from fastapi.requests import Request
from fastapi.responses import JSONResponse

@app.exception_handler(WorkflowError)
async def _workflow_error_handler(request: Request, exc: WorkflowError):
    # Transition de cycle interdite (machine d'états) -> 409 Conflict.
    return JSONResponse(status_code=409, content={"detail": str(exc)})
# CORS (P1-11) : nominatif via WASALAIRE_ORIGINS. Par défaut, '*' seulement en DEV ;
# en production sans liste explicite, aucune origine croisée (même origine uniquement).
_origins = [o.strip() for o in os.environ.get("WASALAIRE_ORIGINS", "*" if DEV else "").split(",")
            if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])


# ─────────────── Connexion BD : POOL (A-08) + rôle applicatif + scope-RLS ───────────────
# Une connexion par requête (psycopg.connect à chaque appel) ne tient pas la charge.
# Un pool réutilise les connexions. Chaque connexion physique est configurée UNE fois
# en rôle applicatif non-privilégié (RLS active). Le périmètre (scope) est posé PAR
# requête, puis RÉINITIALISÉ au retour au pool (sinon fuite de périmètre d'une requête
# à l'autre, car `set_config(..., is_local=false)` persiste sur la session).
POOL_MIN = int(os.environ.get("WASALAIRE_POOL_MIN", "1"))
POOL_MAX = int(os.environ.get("WASALAIRE_POOL_MAX", "10"))

def _pool_configure(conn):
    conn.autocommit = True
    conn.execute("SET ROLE wasalaire_app")         # rôle non-privilégié → RLS active

def _pool_reset(conn):
    # Avant réutilisation : efface tout périmètre résiduel de la requête précédente.
    # set_config('', ...) plutôt que RESET : toujours valide même si le GUC custom
    # n'a jamais été posé sur cette connexion (ex. endpoints d'auth sans scope).
    # current_scope() interprète la chaîne vide comme un périmètre vide ('{}').
    conn.execute("SELECT set_config('app.authorized_companies', '', false)")

pool = ConnectionPool(conninfo="", min_size=POOL_MIN, max_size=POOL_MAX,
                      configure=_pool_configure, reset=_pool_reset, open=False)
pool.open()   # ouverture non bloquante (wait=False) : ne requiert pas la BD à l'import

def _conn(scope: list[str] | None = None):
    """Emprunte une connexion au pool (rôle applicatif déjà posé). À RENDRE via
    `_release(conn)` (et non `conn.close()`) pour la remettre dans le pool."""
    c = pool.getconn()
    if scope is not None:
        set_scope(c, scope)
    return c

def _release(conn):
    """Rend la connexion au pool (le reset efface le périmètre)."""
    pool.putconn(conn)


# ─────────────── Jeton HMAC minimal (base64url(payload).sig) ───────────────
def _b64(b: bytes) -> str: return base64.urlsafe_b64encode(b).decode().rstrip("=")
def _unb64(s: str) -> bytes: return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def make_token(user_id: str, companies: list[str], roles: list[str] | None = None) -> str:
    payload = {"sub": user_id, "companies": companies, "roles": roles or [],
               "exp": int(time.time()) + TOKEN_TTL_S}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(SECRET, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"

def read_token(tok: str) -> dict:
    try:
        body, sig = tok.split(".")
        good = _b64(hmac.new(SECRET, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            raise ValueError("signature")
        payload = json.loads(_unb64(body))
        if payload["exp"] < time.time():
            raise ValueError("expiré")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Jeton invalide ou expiré.")


# ─────────────── Autorisation fonctionnelle (RBAC, deny-by-default) - P0-03 ───────────────
# Matrice action -> rôles autorisés. Toute action non listée est refusée par défaut.
# Limite connue : le rôle est pris comme union sur le périmètre de l'utilisateur (pas encore
# rôle-par-société). Le périmètre société reste vérifié séparément (_require_company + RLS).
PERMISSIONS: dict[str, set[str]] = {
    "me.read":            {"admin", "paie", "rh", "comptable", "auditeur", "employe"},
    "rates.read":         {"admin", "paie", "rh", "comptable", "auditeur", "employe"},
    "company.read":       {"admin", "paie", "rh", "comptable", "auditeur"},
    "employee.read":      {"admin", "paie", "rh", "comptable", "auditeur"},
    "employee.create":    {"admin", "rh"},
    "employee.rupture":   {"admin", "rh"},
    "leave.request":      {"admin", "rh", "employe"},
    "leave.validate":     {"admin", "rh"},
    "leave.balance.read": {"admin", "rh", "paie", "auditeur", "employe"},
    "variable.add":       {"admin", "paie", "rh"},
    "variable.import":    {"admin", "paie", "rh"},
    "period.open":        {"admin", "paie"},
    "period.calculate":   {"admin", "paie"},
    "period.close":       {"admin", "paie"},
    "run.controls.read":  {"admin", "paie", "comptable", "auditeur"},
    "run.payslips.read":  {"admin", "paie", "comptable", "auditeur", "rh"},
    "run.declaration.read": {"admin", "paie", "comptable", "auditeur"},
    "declaration.persist": {"admin", "paie", "comptable"},
    "accounting.persist":  {"admin", "comptable"},
    "payout.create":      {"admin", "paie"},
    "payout.read":        {"admin", "paie", "comptable", "auditeur"},
    "campaign.manage":    {"admin", "paie"},
    "reporting.read":     {"admin", "paie", "comptable", "auditeur", "rh"},
    "notifications.read": {"admin", "paie", "rh"},
    "document.generate":  {"admin", "rh"},
    "documents.read":     {"admin", "rh", "auditeur"},
    # Gouvernance : l'administrateur désigné par l'abonné règle la matrice de droits
    # et la politique 4-eyes (deny-by-default + garde anti-lockout côté service).
    "permissions.manage": {"admin"},
    "governance.manage":  {"admin"},
}


class Ctx:
    def __init__(self, user_id: str, companies: list[str], roles: list[str], conn,
                 workspaces: list[str] | None = None):
        self.user_id, self.companies, self.roles, self.conn = user_id, companies, roles, conn
        self.workspaces = workspaces or []

def current_ctx(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="En-tête Authorization: Bearer requis.")
    payload = read_token(authorization[7:])
    user_id = payload["sub"]
    conn = _conn()
    try:
        # Révocation immédiate (P1-10) : le périmètre et les rôles sont RE-DÉRIVÉS depuis
        # la base à chaque requête (le jeton n'est qu'un cache). Un grant retiré ou un
        # rôle modifié prend effet aussitôt, sans attendre l'expiration du jeton.
        companies = [str(x) for x in (conn.execute(
            "SELECT authorized_companies(%s)", (user_id,)).fetchone()[0] or [])]
        roles = [r[0] for r in conn.execute(
            "SELECT DISTINCT r.code FROM access_grant g JOIN role r ON r.id=g.role_id "
            "WHERE g.user_id=%s AND (g.date_fin IS NULL OR g.date_fin >= current_date)",
            (user_id,)).fetchall()]
        set_scope(conn, companies)
        # Workspaces de l'utilisateur (abonnés) = workspaces de ses sociétés en périmètre.
        # Sert à résoudre la matrice de droits CONFIGURABLE par abonné (permission_override).
        workspaces = []
        if companies:
            workspaces = [str(r[0]) for r in conn.execute(
                "SELECT DISTINCT workspace_id FROM company "
                "WHERE id = ANY(%s) AND workspace_id IS NOT NULL", (companies,)).fetchall()]
        yield Ctx(user_id, companies, roles, conn, workspaces)
    finally:
        _release(conn)

def require(action: str):
    """Dépendance FastAPI : autorise `action` (deny-by-default) puis fournit le Ctx.
    La matrice par défaut (PERMISSIONS) est surchargée par les choix de l'abonné
    (permission_override, par workspace) — cf. effective_allowed_roles."""
    def _dep(ctx: Ctx = Depends(current_ctx)) -> Ctx:
        allowed = effective_allowed_roles(ctx.conn, action, ctx.workspaces,
                                          PERMISSIONS.get(action, set()))
        if not (set(ctx.roles) & allowed):
            raise HTTPException(status_code=403,
                                detail=f"Action '{action}' non autorisée pour votre rôle.")
        return ctx
    return _dep


# ─────────────── Auth : téléphone + OTP ───────────────
class OtpRequest(BaseModel):
    telephone: str
    canal: str = "sms"          # sms | whatsapp

class OtpVerify(BaseModel):
    telephone: str
    code: str

def _hash_otp(code: str, salt: str) -> str:
    return hashlib.sha256((salt + code).encode()).hexdigest()

@app.post("/v1/auth/request-otp")
def request_otp(body: OtpRequest):
    conn = _conn()
    try:
        row = conn.execute("SELECT id FROM app_user WHERE telephone=%s AND statut='actif'",
                           (body.telephone,)).fetchone()
        # Anti-énumération (P1-10) : réponse générique si le numéro est inconnu. Aucun
        # compte n'est créé (les utilisateurs sont provisionnés par l'employeur, pas d'auto-signup).
        if not row:
            return {"sent": True, "canal": body.canal, "expire_dans_min": OTP_TTL_MIN}
        user_id = row[0]
        # Anti-abus (P1-10) : limite les défis récents non consommés par téléphone.
        recent = conn.execute(
            "SELECT count(*) FROM otp_challenge WHERE telephone=%s AND consomme_at IS NULL "
            "AND created_at > now() - make_interval(mins => %s)",
            (body.telephone, OTP_TTL_MIN)).fetchone()[0]
        if recent >= 3:
            raise HTTPException(status_code=429,
                                detail="Trop de demandes de code. Réessayez dans quelques minutes.")
        code = f"{secrets.randbelow(10**6):06d}"
        salt = secrets.token_hex(8)
        expire = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MIN)
        conn.execute(
            "INSERT INTO otp_challenge(user_id,telephone,canal,code_hash,expire_at) "
            "VALUES (%s,%s,%s,%s,%s)",
            (user_id, body.telephone, body.canal, salt + ":" + _hash_otp(code, salt), expire))
        # Envoi réel du code (WhatsApp/SMS selon le canal ; repli 'log' si clés absentes).
        gw = {"whatsapp": WhatsAppGateway, "sms": SmsGateway}.get(body.canal, LogGateway)()
        msg = f"WaSalaire : votre code de connexion est {code} (valable {OTP_TTL_MIN} min)."
        envoi = gw.send(body.telephone, msg)
        out = {"sent": envoi["statut"] == "envoye", "canal": body.canal,
               "statut_envoi": envoi["statut"], "expire_dans_min": OTP_TTL_MIN}
        if envoi["statut"] != "envoye":
            # Aucun canal configuré : en DEV on renvoie le code ; en PROD on signale l'anomalie.
            if DEV:
                out["dev_code"] = code
            else:
                out["avertissement"] = ("Aucun canal d'envoi OTP configuré "
                                         "(WHATSAPP_TOKEN / SMS_API_KEY manquant).")
        return out
    finally:
        _release(conn)

@app.post("/v1/auth/verify-otp")
def verify_otp(body: OtpVerify):
    conn = _conn()
    try:
        ch = conn.execute(
            "SELECT id,user_id,code_hash,tentatives FROM otp_challenge "
            "WHERE telephone=%s AND consomme_at IS NULL AND expire_at > now() "
            "ORDER BY created_at DESC LIMIT 1", (body.telephone,)).fetchone()
        if not ch:
            raise HTTPException(status_code=400, detail="Aucun code valide (expiré ?). Redemandez un OTP.")
        cid, user_id, stored, tries = ch
        if tries >= 5:
            raise HTTPException(status_code=429, detail="Trop de tentatives.")
        salt, digest = stored.split(":", 1)
        if not hmac.compare_digest(digest, _hash_otp(body.code, salt)):
            conn.execute("UPDATE otp_challenge SET tentatives=tentatives+1 WHERE id=%s", (cid,))
            raise HTTPException(status_code=401, detail="Code incorrect.")
        conn.execute("UPDATE otp_challenge SET consomme_at=now() WHERE id=%s", (cid,))
        conn.execute("UPDATE app_user SET telephone_verifie=true WHERE id=%s", (user_id,))
        companies = conn.execute("SELECT authorized_companies(%s)", (user_id,)).fetchone()[0] or []
        companies = [str(c) for c in companies]
        roles = [r[0] for r in conn.execute(
            "SELECT DISTINCT r.code FROM access_grant g JOIN role r ON r.id=g.role_id "
            "WHERE g.user_id=%s AND (g.date_fin IS NULL OR g.date_fin >= current_date)",
            (user_id,)).fetchall()]
        return {"token": make_token(str(user_id), companies, roles),
                "user_id": str(user_id), "companies": companies, "roles": roles}
    finally:
        _release(conn)


# ─────────────── Cycle de paie (persisté, scope-isolé) ───────────────
class PeriodIn(BaseModel):
    company_id: str
    mois: int
    annee: int

class CalcIn(BaseModel):
    company_id: str
    period_id: str
    periode: date

def _require_company(ctx: Ctx, company_id: str):
    if company_id not in ctx.companies:
        raise HTTPException(status_code=403, detail="Société hors de votre périmètre.")

@app.get("/v1/me")
def me(ctx: Ctx = Depends(require("me.read"))):
    return {"user_id": ctx.user_id, "companies": ctx.companies, "roles": ctx.roles}

@app.get("/v1/companies")
def companies(ctx: Ctx = Depends(require("company.read"))):
    return {"companies": list_companies(ctx.conn)}

@app.get("/v1/employees")
def employees(company_id: str, ctx: Ctx = Depends(require("employee.read"))):
    _require_company(ctx, company_id)
    return {"company_id": company_id, "employes": list_employees(ctx.conn, company_id)}


# ─────────────── RH : entrée / sortie / congés ───────────────
class EmployeeIn(BaseModel):
    company_id: str
    matricule: str
    nom: str
    salaire_base: float
    type_contrat: str = "CDI"
    methode_paiement: str = "especes"
    num_cnss: str | None = None

class RuptureIn(BaseModel):
    company_id: str
    type_rupture: str
    anciennete_ans: float
    jours_travailles_dernier_mois: int = 30
    jours_conges_acquis_non_pris: int = 0
    preavis_indemnite: float = 0.0

class LeaveIn(BaseModel):
    company_id: str
    employee_id: str
    type: str = "conge_annuel"
    date_debut: str
    date_fin: str
    jours: float
    motif: str | None = None

@app.post("/v1/employees")
def create_emp(body: EmployeeIn, ctx: Ctx = Depends(require("employee.create"))):
    _require_company(ctx, body.company_id)
    try:
        return rh_create_employee(ctx.conn, body.company_id, body.matricule, body.nom,
                                  body.salaire_base, body.type_contrat,
                                  methode_paiement=body.methode_paiement, num_cnss=body.num_cnss,
                                  actor=ctx.user_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.post("/v1/employees/{employee_id}/rupture")
def emp_rupture(employee_id: str, body: RuptureIn, ctx: Ctx = Depends(require("employee.rupture"))):
    _require_company(ctx, body.company_id)
    try:
        return rh_rupture(ctx.conn, body.company_id, employee_id, body.type_rupture,
                          body.anciennete_ans, body.jours_travailles_dernier_mois,
                          body.jours_conges_acquis_non_pris, body.preavis_indemnite,
                          actor=ctx.user_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.post("/v1/leaves")
def leave_create(body: LeaveIn, ctx: Ctx = Depends(require("leave.request"))):
    _require_company(ctx, body.company_id)
    rid = request_leave(ctx.conn, body.company_id, body.employee_id, body.type,
                        body.date_debut, body.date_fin, body.jours, body.motif)
    return {"leave_id": rid, "statut": "en_attente"}

@app.post("/v1/leaves/{leave_id}/validate")
def leave_validate(leave_id: str, accord: bool = True, ctx: Ctx = Depends(require("leave.validate"))):
    validate_leave(ctx.conn, leave_id, ctx.user_id, accord)
    return {"leave_id": leave_id, "statut": "valide" if accord else "refuse"}

@app.get("/v1/employees/{employee_id}/leave-balance")
def leave_bal(employee_id: str, mois_service: int = 12, anciennete_ans: int = 0,
              ctx: Ctx = Depends(require("leave.balance.read"))):
    return leave_balance(ctx.conn, employee_id, mois_service, anciennete_ans)


# ─────────────── Campagne · Reporting · Notifications · WaDocs ───────────────
class CampaignIn(BaseModel):
    org_node_id: str
    mois: int
    annee: int

@app.post("/v1/campaigns")
def campaign_create(body: CampaignIn, ctx: Ctx = Depends(require("campaign.manage"))):
    return {"campaign_id": create_campaign(ctx.conn, body.org_node_id, body.mois, body.annee)}

@app.get("/v1/campaigns/{campaign_id}/status")
def campaign_stat(campaign_id: str, ctx: Ctx = Depends(require("campaign.manage"))):
    return campaign_status(ctx.conn, campaign_id)

@app.get("/v1/reporting")
def reporting(company_id: str, ctx: Ctx = Depends(require("reporting.read"))):
    _require_company(ctx, company_id)
    return reporting_summary(ctx.conn, company_id)

@app.get("/v1/notifications")
def notifications_list(company_id: str, ctx: Ctx = Depends(require("notifications.read"))):
    _require_company(ctx, company_id)
    return {"notifications": list_notifications(ctx.conn, company_id)}

class DocGenIn(BaseModel):
    company_id: str
    employee_id: str
    titre: str = "Contrat de travail"

@app.post("/v1/documents/generate")
def doc_generate(body: DocGenIn, ctx: Ctx = Depends(require("document.generate"))):
    _require_company(ctx, body.company_id)
    comp = ctx.conn.execute("SELECT raison_sociale, ifu FROM company WHERE id=%s",
                            (body.company_id,)).fetchone()
    emp = ctx.conn.execute(
        "SELECT e.nom, c.type, c.date_debut, c.salaire_base, p.intitule "
        "FROM employee e JOIN contract c ON c.employee_id=e.id AND c.statut='actif' "
        "LEFT JOIN position p ON p.id=c.position_id WHERE e.id=%s", (body.employee_id,)).fetchone()
    if not emp:
        raise HTTPException(status_code=404, detail="Salarié ou contrat actif introuvable.")
    context = {"Entreprise": {"raison_sociale": comp[0], "ifu": comp[1] or "—"},
               "Salarié": {"nom": emp[0]},
               "Contrat": {"type": emp[1], "date_debut": str(emp[2]),
                           "salaire": float(emp[3]), "poste": emp[4] or "Salarié"}}
    return generate_document(ctx.conn, body.company_id, body.titre, CONTRAT_TEMPLATE,
                             context, employee_id=body.employee_id)

@app.get("/v1/documents")
def documents_list(company_id: str, ctx: Ctx = Depends(require("documents.read"))):
    _require_company(ctx, company_id)
    return {"documents": list_documents(ctx.conn, company_id)}

@app.post("/v1/periods")
def create_period(body: PeriodIn, ctx: Ctx = Depends(require("period.open"))):
    _require_company(ctx, body.company_id)
    pid = open_period(ctx.conn, body.company_id, body.mois, body.annee, actor=ctx.user_id)
    return {"period_id": str(pid), "statut": "ouverte"}

@app.post("/v1/periods/calculate")
def calculate(body: CalcIn, ctx: Ctx = Depends(require("period.calculate"))):
    _require_company(ctx, body.company_id)
    run_id, n = calculate_run(ctx.conn, body.company_id, body.period_id, body.periode,
                              actor=ctx.user_id)
    return {"run_id": str(run_id), "bulletins": n}

@app.post("/v1/runs/{run_id}/close")
def close_run(run_id: str, period_id: str, override_reason: str | None = None,
              ctx: Ctx = Depends(require("period.close"))):
    validate_and_close(ctx.conn, period_id, run_id, actor=ctx.user_id,
                       override_reason=override_reason)
    return {"run_id": run_id, "statut": "cloturee"}

@app.get("/v1/runs/{run_id}/payslips")
def payslips(run_id: str, ctx: Ctx = Depends(require("run.payslips.read"))):
    return {"run_id": run_id, "bulletins": list_payslips(ctx.conn, run_id)}

@app.get("/v1/regulatory/rates")
def rates(at: date, ctx: Ctx = Depends(require("rates.read"))):
    codes = ["taux_pension_sal", "taux_pension_emp", "taux_pf", "taux_vps"]
    return {"at": at, "rates": {c: param(c, at) for c in codes}}


# ─────────────── Variables · contrôles · déclarations · décaissement ───────────────
class VariableIn(BaseModel):
    company_id: str
    period_id: str
    employee_id: str
    type: str
    montant: float

@app.post("/v1/periods/variables")
def add_var(body: VariableIn, ctx: Ctx = Depends(require("variable.add"))):
    _require_company(ctx, body.company_id)
    vid = add_variable(ctx.conn, body.company_id, body.employee_id, body.period_id,
                       body.type, body.montant, actor=ctx.user_id)
    return {"variable_id": str(vid)}

class VariableImportIn(BaseModel):
    company_id: str
    period_id: str
    lignes: list[dict]        # [{employee_id, type, montant, source_ref}]

@app.post("/v1/periods/variables/import")
def import_vars(body: VariableImportIn, ctx: Ctx = Depends(require("variable.import"))):
    """Import REJOUABLE (dédup par source_ref) — câble l'écran W44."""
    _require_company(ctx, body.company_id)
    try:
        return import_variables(ctx.conn, body.company_id, body.period_id,
                                body.lignes, actor=ctx.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─────────────── Administration : droits & gouvernance (admin de l'abonné) ───────────────
_ROLES_CONNUS = {"admin", "paie", "rh", "comptable", "auditeur", "employe"}

def _admin_workspace(ctx: Ctx, workspace_id: str | None) -> str:
    """Workspace (abonné) cible d'une action d'admin, borné au périmètre de l'utilisateur."""
    if workspace_id:
        if workspace_id not in ctx.workspaces:
            raise HTTPException(status_code=403, detail="Abonné hors de votre périmètre.")
        return workspace_id
    if len(ctx.workspaces) == 1:
        return ctx.workspaces[0]
    raise HTTPException(status_code=400,
                        detail="Précisez workspace_id (plusieurs abonnés dans votre périmètre).")

@app.get("/v1/admin/permissions")
def get_permissions(workspace_id: str | None = None,
                    ctx: Ctx = Depends(require("permissions.manage"))):
    ws = _admin_workspace(ctx, workspace_id)
    return {"workspace_id": ws,
            "defauts": {k: sorted(v) for k, v in PERMISSIONS.items()},
            "surcharges": list_permission_overrides(ctx.conn, ws)}

class PermissionIn(BaseModel):
    action: str
    role_code: str
    allowed: bool
    workspace_id: str | None = None

@app.put("/v1/admin/permissions")
def put_permission(body: PermissionIn, ctx: Ctx = Depends(require("permissions.manage"))):
    ws = _admin_workspace(ctx, body.workspace_id)
    if body.action not in PERMISSIONS:
        raise HTTPException(status_code=400, detail=f"Action inconnue : {body.action}")
    if body.role_code not in _ROLES_CONNUS:
        raise HTTPException(status_code=400, detail=f"Rôle inconnu : {body.role_code}")
    try:
        set_permission_override(ctx.conn, ws, body.action, body.role_code,
                                body.allowed, actor=ctx.user_id)
    except WorkflowError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"workspace_id": ws, "action": body.action,
            "role_code": body.role_code, "allowed": body.allowed}

@app.get("/v1/admin/governance")
def get_governance(workspace_id: str | None = None,
                   ctx: Ctx = Depends(require("governance.manage"))):
    ws = _admin_workspace(ctx, workspace_id)
    return {"workspace_id": ws, **get_governance_policy(ctx.conn, ws)}

class GovernanceIn(BaseModel):
    champ: str                # four_eyes_calcul_validation | four_eyes_validation_paiement
    valeur: bool
    workspace_id: str | None = None

@app.put("/v1/admin/governance")
def put_governance(body: GovernanceIn, ctx: Ctx = Depends(require("governance.manage"))):
    ws = _admin_workspace(ctx, body.workspace_id)
    try:
        set_governance_policy(ctx.conn, ws, body.champ, body.valeur, actor=ctx.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"workspace_id": ws, **get_governance_policy(ctx.conn, ws)}

@app.get("/v1/runs/{run_id}/controls")
def controls(run_id: str, ctx: Ctx = Depends(require("run.controls.read"))):
    ano = run_controls(ctx.conn, run_id)
    return {"run_id": run_id,
            "bloquants": sum(1 for a in ano if a["gravite"] == "bloquant"),
            "avertissements": sum(1 for a in ano if a["gravite"] == "avertissement"),
            "anomalies": ano}

@app.get("/v1/runs/{run_id}/declaration")
def declaration(run_id: str, ctx: Ctx = Depends(require("run.declaration.read"))):
    return {"run_id": run_id, **declaration_aggregate(ctx.conn, run_id)}

@app.post("/v1/runs/{run_id}/declarations")
def declarations_persist(run_id: str, ctx: Ctx = Depends(require("declaration.persist"))):
    # Persiste les déclarations du run clôturé. Dépôt/accusé officiel = VALIDATION EXTERNE.
    return {"run_id": run_id, "declarations": persist_declaration(ctx.conn, run_id, actor=ctx.user_id)}

@app.post("/v1/runs/{run_id}/accounting")
def accounting_persist(run_id: str, ctx: Ctx = Depends(require("accounting.persist"))):
    return {"run_id": run_id, **persist_accounting(ctx.conn, run_id, actor=ctx.user_id)}

@app.post("/v1/runs/{run_id}/payout")
def payout(run_id: str, company_id: str, ctx: Ctx = Depends(require("payout.create"))):
    _require_company(ctx, company_id)
    return {"run_id": run_id, **create_payout(ctx.conn, company_id, run_id, actor=ctx.user_id)}

@app.get("/v1/runs/{run_id}/payout")
def payout_list(run_id: str, ctx: Ctx = Depends(require("payout.read"))):
    return {"run_id": run_id, "items": list_payout(ctx.conn, run_id)}


# ─────────────── Frontend mobile-first (même origine) ───────────────
@app.get("/health", include_in_schema=False)
def health():
    # Sonde de disponibilité (P1-16/exploitation) : vérifie la connexion à la base.
    try:
        c = psycopg.connect("", autocommit=True)
        try:
            c.execute("SELECT 1")
        finally:
            c.close()
        return {"status": "ok", "db": "up"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "down"})

@app.get("/", include_in_schema=False)
def home():
    f = Path(__file__).parent / "frontend_v2.html"
    return FileResponse(f) if f.exists() else {"api": "WaSalaire v2", "docs": "/docs"}

@app.get("/console", include_in_schema=False)
def console():
    f = Path(__file__).parent / "console_web.html"
    return FileResponse(f) if f.exists() else {"error": "console_web.html introuvable"}

@app.get("/onboarding", include_in_schema=False)
def onboarding():
    f = Path(__file__).parent / "onboarding.html"
    return FileResponse(f) if f.exists() else {"error": "onboarding.html introuvable"}

_assets = Path(__file__).parent / "assets"
if _assets.exists():
    app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")
