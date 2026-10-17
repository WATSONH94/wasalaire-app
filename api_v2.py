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
    persist_declaration, persist_accounting, pay_registers, payment_register,
    list_employees, list_companies, WorkflowError,
    create_campaign, attach_run_to_campaign, campaign_status, payroll_overview, reporting_summary,
    import_variables, effective_allowed_roles, set_permission_override,
    list_permission_overrides, get_governance_policy, set_governance_policy,
)
from rh_service import (create_employee as rh_create_employee, rupture as rh_rupture,
                        request_leave, validate_leave, leave_balance, list_leaves)
from onboarding_service import (
    create_establishment, list_establishments, create_department, list_departments,
    create_position, list_positions, create_contract, list_contracts,
)
from auth_service import (
    authenticate, AuthError, start_totp_enrollment, confirm_totp_enrollment,
    verify_mfa, change_password, verify_password, log_event,
)
from entitlements import check_can_add_employee, QuotaError
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

def _log_breakglass_if_superadmin(conn, user_id: str) -> None:
    """Trace l'octroi d'un accès transverse à un super-admin plateforme (audit break-glass)."""
    row = conn.execute("SELECT platform_role FROM app_user WHERE id=%s", (user_id,)).fetchone()
    if row and row[0] == "super_admin":
        log_event(conn, "breakglass_grant", user_id=user_id,
                  detail={"note": "acces transverse tous tenants accorde a la connexion"})


def _scope_and_roles(conn, user_id: str) -> tuple[list[str], list[str]]:
    """Périmètre (sociétés autorisées) + rôles tenant, re-dérivés de la base (révocation immédiate)."""
    companies = [str(x) for x in (conn.execute(
        "SELECT authorized_companies(%s)", (user_id,)).fetchone()[0] or [])]
    roles = [r[0] for r in conn.execute(
        "SELECT DISTINCT r.code FROM access_grant g JOIN role r ON r.id=g.role_id "
        "WHERE g.user_id=%s AND (g.date_fin IS NULL OR g.date_fin >= current_date)",
        (user_id,)).fetchall()]
    return companies, roles


def make_token(user_id: str, companies: list[str], roles: list[str] | None = None,
               mfa: bool = True, must_change: bool = False) -> str:
    # `mfa` : l'authentification forte est satisfaite (OTP ou TOTP) → accès métier autorisé.
    # `pwd` : un changement de mot de passe est requis avant tout accès.
    payload = {"sub": user_id, "companies": companies, "roles": roles or [],
               "mfa": bool(mfa), "pwd": bool(must_change),
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
    "structure.read":     {"admin", "paie", "rh", "comptable", "auditeur"},
    "establishment.create": {"admin", "rh"},
    "department.create":  {"admin", "rh"},
    "position.create":    {"admin", "rh"},
    "contract.create":    {"admin", "rh"},
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
                 workspaces: list[str] | None = None, mfa: bool = True, must_change: bool = False,
                 platform_role: str = "none"):
        self.user_id, self.companies, self.roles, self.conn = user_id, companies, roles, conn
        self.workspaces = workspaces or []
        self.mfa, self.must_change = mfa, must_change
        self.platform_role = platform_role

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
        companies, roles = _scope_and_roles(conn, user_id)
        prow = conn.execute("SELECT platform_role FROM app_user WHERE id=%s", (user_id,)).fetchone()
        prole = prow[0] if prow else "none"
        # Super-admin plateforme = accès TRANSVERSE (break-glass) : périmètre = toutes les
        # sociétés + rôles tenant complets. L'octroi est tracé au moment de la connexion
        # (security_event 'breakglass_grant'), cf. mint du jeton complet.
        # ⚠️ À l'échelle, remplacer par un rôle BYPASSRLS dédié (ici : liste explicite).
        if prole == "super_admin":
            # `all_company_ids()` est SECURITY DEFINER → contourne la RLS pour LISTER les ids
            # (sinon la liste serait elle-même filtrée par un périmètre encore vide).
            companies = [str(x) for x in (conn.execute(
                "SELECT all_company_ids()").fetchone()[0] or [])]
            roles = sorted(set(roles) | {"admin", "paie", "rh", "comptable", "auditeur"})
        set_scope(conn, companies)
        # Workspaces de l'utilisateur (abonnés) = workspaces de ses sociétés en périmètre.
        # Sert à résoudre la matrice de droits CONFIGURABLE par abonné (permission_override).
        workspaces = []
        if companies:
            workspaces = [str(r[0]) for r in conn.execute(
                "SELECT DISTINCT workspace_id FROM company "
                "WHERE id = ANY(%s) AND workspace_id IS NOT NULL", (companies,)).fetchall()]
        yield Ctx(user_id, companies, roles, conn, workspaces,
                  mfa=bool(payload.get("mfa", True)), must_change=bool(payload.get("pwd", False)),
                  platform_role=prole)
    finally:
        _release(conn)

def require(action: str):
    """Dépendance FastAPI : autorise `action` (deny-by-default) puis fournit le Ctx.
    La matrice par défaut (PERMISSIONS) est surchargée par les choix de l'abonné
    (permission_override, par workspace) — cf. effective_allowed_roles."""
    def _dep(ctx: Ctx = Depends(current_ctx)) -> Ctx:
        # Barrières d'authentification forte : aucun accès métier tant que la MFA n'est pas
        # satisfaite, ni tant qu'un changement de mot de passe obligatoire n'est pas effectué.
        if ctx.must_change:
            raise HTTPException(status_code=409,
                                detail="Changement de mot de passe requis avant tout accès.")
        if not ctx.mfa:
            raise HTTPException(status_code=403,
                                detail="Authentification à deux facteurs requise.")
        allowed = effective_allowed_roles(ctx.conn, action, ctx.workspaces,
                                          PERMISSIONS.get(action, set()))
        if not (set(ctx.roles) & allowed):
            raise HTTPException(status_code=403,
                                detail=f"Action '{action}' non autorisée pour votre rôle.")
        return ctx
    return _dep


def require_platform(roles: set[str]):
    """Dépendance pour l'administration de la PLATEFORME (SaaS), distincte des rôles tenant."""
    def _dep(ctx: Ctx = Depends(current_ctx)) -> Ctx:
        if ctx.must_change:
            raise HTTPException(status_code=409, detail="Changement de mot de passe requis.")
        if not ctx.mfa:
            raise HTTPException(status_code=403, detail="Authentification à deux facteurs requise.")
        if ctx.platform_role not in roles:
            raise HTTPException(status_code=403, detail="Réservé à l'administration de la plateforme.")
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


# ─────────────── Auth web : email + mot de passe + MFA TOTP (obligatoire) ───────────────
# Flux : /login (email+mdp) → pré-jeton (SANS accès métier) + étape à franchir
#   ('change_password' | 'mfa_setup' | 'mfa') → puis /password/change, /mfa/setup+confirm
#   ou /mfa/verify → jeton complet (mfa=true) donnant l'accès métier.
def current_prectx(authorization: str | None = Header(default=None)):
    """Dépendance pour les endpoints d'authentification : valide un (pré-)jeton et fournit
    (payload, conn). N'exige PAS que la MFA soit satisfaite."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="En-tête Authorization: Bearer requis.")
    payload = read_token(authorization[7:])
    conn = _conn()
    try:
        yield (payload, conn)
    finally:
        _release(conn)

class PwdLogin(BaseModel):
    email: str
    password: str

class MfaCode(BaseModel):
    code: str

class PwdChange(BaseModel):
    new_password: str
    current_password: str | None = None

def _client_ip(request: Request):
    import ipaddress
    h = request.client.host if request.client else None
    try:
        ipaddress.ip_address(h)   # n'accepte que des IP valides (le type colonne est inet)
        return h
    except (ValueError, TypeError):
        return None

@app.post("/v1/auth/login")
def password_login(body: PwdLogin, request: Request):
    """Étape 1 : email + mot de passe. Renvoie un PRÉ-jeton (sans accès métier) + l'étape suivante."""
    conn = _conn()
    try:
        try:
            res = authenticate(conn, body.email, body.password, ip=_client_ip(request))
        except AuthError as e:
            raise HTTPException(status_code=429 if e.code == "locked" else 401, detail=str(e))
        uid = res["user_id"]
        stage = ("change_password" if res["must_change_password"]
                 else "mfa_setup" if not res["totp_enrolled"] else "mfa")
        pre = make_token(uid, [], [], mfa=False, must_change=res["must_change_password"])
        return {"token": pre, "stage": stage, "user_id": uid}
    finally:
        _release(conn)

@app.post("/v1/auth/password/change")
def password_change(body: PwdChange, request: Request, ctx=Depends(current_prectx)):
    """Changement de mot de passe (forcé à la 1re connexion, ou volontaire avec ré-auth)."""
    payload, conn = ctx
    uid = payload["sub"]
    forced = bool(payload.get("pwd"))
    if not forced:
        row = conn.execute("SELECT password_hash FROM app_user WHERE id=%s", (uid,)).fetchone()
        if not body.current_password or not verify_password(body.current_password, row[0] if row else None):
            raise HTTPException(status_code=401, detail="Mot de passe actuel incorrect.")
    try:
        change_password(conn, uid, body.new_password, ip=_client_ip(request))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    row = conn.execute("SELECT totp_enrolled FROM app_user WHERE id=%s", (uid,)).fetchone()
    stage = "mfa" if (row and row[0]) else "mfa_setup"
    return {"token": make_token(uid, [], [], mfa=False, must_change=False), "stage": stage}

@app.post("/v1/auth/mfa/setup")
def mfa_setup(ctx=Depends(current_prectx)):
    """Génère le secret TOTP + l'URI otpauth (QR). À scanner dans l'app Authenticator."""
    payload, conn = ctx
    if payload.get("pwd"):
        raise HTTPException(status_code=409, detail="Changez d'abord votre mot de passe.")
    uid = payload["sub"]
    row = conn.execute("SELECT email FROM app_user WHERE id=%s", (uid,)).fetchone()
    if not row or not row[0]:
        raise HTTPException(status_code=400, detail="Email requis pour l'enrôlement TOTP.")
    return start_totp_enrollment(conn, uid, row[0])

@app.post("/v1/auth/mfa/confirm")
def mfa_confirm(body: MfaCode, request: Request, ctx=Depends(current_prectx)):
    """Vérifie le 1er code TOTP → active la MFA, renvoie les codes de récupération + jeton complet."""
    payload, conn = ctx
    if payload.get("pwd"):
        raise HTTPException(status_code=409, detail="Changez d'abord votre mot de passe.")
    uid = payload["sub"]
    try:
        codes = confirm_totp_enrollment(conn, uid, body.code, ip=_client_ip(request))
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    companies, roles = _scope_and_roles(conn, uid)
    _log_breakglass_if_superadmin(conn, uid)
    return {"token": make_token(uid, companies, roles, mfa=True), "recovery_codes": codes,
            "companies": companies, "roles": roles}

@app.post("/v1/auth/mfa/verify")
def mfa_verify(body: MfaCode, request: Request, ctx=Depends(current_prectx)):
    """Étape 2 (connexions suivantes) : code TOTP ou code de récupération → jeton complet."""
    payload, conn = ctx
    if payload.get("pwd"):
        raise HTTPException(status_code=409, detail="Changez d'abord votre mot de passe.")
    uid = payload["sub"]
    if not verify_mfa(conn, uid, body.code, ip=_client_ip(request)):
        raise HTTPException(status_code=401, detail="Code incorrect.")
    companies, roles = _scope_and_roles(conn, uid)
    _log_breakglass_if_superadmin(conn, uid)
    return {"token": make_token(uid, companies, roles, mfa=True),
            "companies": companies, "roles": roles}


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
    email = platform_role = None
    totp_enrolled = mfa_enforced = False
    try:
        row = ctx.conn.execute(
            "SELECT email, platform_role, totp_enrolled, mfa_enforced FROM app_user WHERE id=%s",
            (ctx.user_id,)).fetchone()
        if row:
            email, platform_role, totp_enrolled, mfa_enforced = row
    except Exception:
        pass
    return {"user_id": ctx.user_id, "companies": ctx.companies, "roles": ctx.roles,
            "email": email, "platform_role": platform_role,
            "mfa_enrolled": bool(totp_enrolled), "mfa_enforced": bool(mfa_enforced)}

@app.get("/v1/companies")
def companies(ctx: Ctx = Depends(require("company.read"))):
    return {"companies": list_companies(ctx.conn)}

@app.get("/v1/org/admin-nodes")
def org_admin_nodes(ctx: Ctx = Depends(require("me.read"))):
    """Nœuds d'organisation sous lesquels l'utilisateur peut créer une société (il y est admin)."""
    rows = ctx.conn.execute(
        "SELECT node_id, node_type, nom FROM admin_nodes(%s) ORDER BY nom", (ctx.user_id,)).fetchall()
    return {"nodes": [{"id": str(r[0]), "type": r[1], "nom": r[2]} for r in rows]}

class CompanyCreateIn(BaseModel):
    parent_node_id: str
    raison_sociale: str
    ifu: str | None = None

@app.post("/v1/companies")
def create_company(body: CompanyCreateIn, ctx: Ctx = Depends(require("me.read"))):
    """Crée une société sous un nœud dont l'appelant est administrateur (autorisation
    contrôlée côté SECURITY DEFINER, pas déléguée à la RLS). Idempotent par raison sociale."""
    try:
        row = ctx.conn.execute(
            "SELECT create_company_under_node(%s, %s, %s, %s)",
            (ctx.user_id, body.parent_node_id, body.raison_sociale, body.ifu)).fetchone()
    except Exception as e:
        msg = str(getattr(e, "diag", None) and e.diag.message_primary or e).strip()
        raise HTTPException(status_code=403, detail=msg or "Création refusée")
    return {"company_id": str(row[0])}

@app.get("/v1/companies/{company_id}/runs")
def company_runs(company_id: str, ctx: Ctx = Depends(require("run.declaration.read"))):
    """Cycles de paie calculés d'une société (pour Déclarations / historique). RLS-scopé."""
    _require_company(ctx, company_id)
    rows = ctx.conn.execute(
        "SELECT r.id, pp.mois, pp.annee, pp.statut, r.date_execution, pp.id, r.actif "
        "FROM payroll_run r JOIN payroll_period pp ON pp.id = r.period_id "
        "WHERE r.company_id = %s ORDER BY r.date_execution DESC", (company_id,)).fetchall()
    return {"runs": [{"run_id": str(r[0]), "mois": r[1], "annee": r[2], "statut": r[3],
                      "date_execution": r[4].isoformat() if r[4] else None,
                      "period_id": str(r[5]), "actif": r[6]} for r in rows]}

@app.get("/v1/employees")
def employees(company_id: str, ctx: Ctx = Depends(require("employee.read"))):
    _require_company(ctx, company_id)
    return {"company_id": company_id, "employes": list_employees(ctx.conn, company_id)}


@app.get("/v1/employees/{employee_id}/attestation")
def attestation(employee_id: str, company_id: str, type: str = "travail",
                ctx: Ctx = Depends(require("documents.read"))):
    # Attestation RH (travail / salaire / virement) : rendu texte depuis les données
    # réelles (aucun champ inventé). Lecture seule.
    _require_company(ctx, company_id)
    from attestations import generate
    try:
        return generate(ctx.conn, company_id, employee_id, type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    preview: bool = False   # True = calcul seul (ne clôt pas le contrat)

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
        check_can_add_employee(ctx.conn, body.company_id)   # quota du plan d'abonnement
    except QuotaError as e:
        raise HTTPException(status_code=402, detail=str(e))  # 402 : limite du plan atteinte
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
                          actor=ctx.user_id, preview=body.preview)
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

@app.get("/v1/companies/{company_id}/leaves")
def company_leaves(company_id: str, ctx: Ctx = Depends(require("leave.balance.read"))):
    _require_company(ctx, company_id)
    return {"company_id": company_id, "leaves": list_leaves(ctx.conn, company_id)}


# ─────────────── Structure société : établissement / département / poste / contrat ───────────────
class EstablishmentIn(BaseModel):
    company_id: str
    nom: str
    adresse: str | None = None
    num_cnss_etab: str | None = None

class DepartmentIn(BaseModel):
    company_id: str
    nom: str
    centre_de_cout: str | None = None

class PositionIn(BaseModel):
    company_id: str
    intitule: str
    categorie: str | None = None
    classification_conv: str | None = None

class ContractIn(BaseModel):
    company_id: str
    employee_id: str
    type_contrat: str = "CDI"
    date_debut: str
    salaire_base: float
    mode: str = "mensuel"
    position_id: str | None = None
    department_id: str | None = None
    establishment_id: str | None = None
    date_fin: str | None = None
    periode_essai_fin: str | None = None
    remplacer_actif: bool = False

def _onboarding_create(fn, ctx, company_id, **kw):
    _require_company(ctx, company_id)
    try:
        return fn(ctx.conn, company_id, actor=ctx.user_id, **kw)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.post("/v1/establishments")
def establishment_create(body: EstablishmentIn, ctx: Ctx = Depends(require("establishment.create"))):
    return _onboarding_create(create_establishment, ctx, body.company_id,
                              nom=body.nom, adresse=body.adresse, num_cnss_etab=body.num_cnss_etab)

@app.get("/v1/establishments")
def establishments_list(company_id: str, ctx: Ctx = Depends(require("structure.read"))):
    _require_company(ctx, company_id)
    return {"company_id": company_id, "etablissements": list_establishments(ctx.conn, company_id)}

@app.post("/v1/departments")
def department_create(body: DepartmentIn, ctx: Ctx = Depends(require("department.create"))):
    return _onboarding_create(create_department, ctx, body.company_id,
                              nom=body.nom, centre_de_cout=body.centre_de_cout)

@app.get("/v1/departments")
def departments_list(company_id: str, ctx: Ctx = Depends(require("structure.read"))):
    _require_company(ctx, company_id)
    return {"company_id": company_id, "departements": list_departments(ctx.conn, company_id)}

@app.post("/v1/positions")
def position_create(body: PositionIn, ctx: Ctx = Depends(require("position.create"))):
    return _onboarding_create(create_position, ctx, body.company_id,
                              intitule=body.intitule, categorie=body.categorie,
                              classification_conv=body.classification_conv)

@app.get("/v1/positions")
def positions_list(company_id: str, ctx: Ctx = Depends(require("structure.read"))):
    _require_company(ctx, company_id)
    return {"company_id": company_id, "postes": list_positions(ctx.conn, company_id)}

@app.post("/v1/contracts")
def contract_create(body: ContractIn, ctx: Ctx = Depends(require("contract.create"))):
    return _onboarding_create(create_contract, ctx, body.company_id,
                              employee_id=body.employee_id, type_contrat=body.type_contrat,
                              date_debut=body.date_debut, salaire_base=body.salaire_base,
                              mode=body.mode, position_id=body.position_id,
                              department_id=body.department_id, establishment_id=body.establishment_id,
                              date_fin=body.date_fin, periode_essai_fin=body.periode_essai_fin,
                              remplacer_actif=body.remplacer_actif)

@app.get("/v1/contracts")
def contracts_list(company_id: str, employee_id: str | None = None,
                   ctx: Ctx = Depends(require("structure.read"))):
    _require_company(ctx, company_id)
    return {"company_id": company_id, "contrats": list_contracts(ctx.conn, company_id, employee_id)}


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

@app.get("/v1/org/payroll-overview")
def org_payroll_overview(mois: int, annee: int, ctx: Ctx = Depends(require("company.read"))):
    # Avancement de la paie du mois pour toutes les sociétés du périmètre (RLS).
    return payroll_overview(ctx.conn, mois, annee)

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

@app.get("/v1/rubriques")
def rubriques_catalogue(ctx: Ctx = Depends(require("variable.add"))):
    """Catalogue standard des rubriques de paie (assiettes CNSS/ITS/VPS pré-configurées
    depuis les règles validées) : permet une saisie guidée garantissant une paie EXACTE."""
    from payroll_service import STANDARD_RUBRIQUES
    return {"rubriques": [
        {"code": code, "libelle": lib, "soumis_cnss": c, "soumis_its": i, "soumis_vps": v, "nature": nat}
        for code, (lib, c, i, v, nat) in STANDARD_RUBRIQUES.items()
    ]}

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

@app.get("/v1/runs/{run_id}/registres")
def registres(run_id: str, ctx: Ctx = Depends(require("run.declaration.read"))):
    # Registres légaux (livre de paie, bordereau CNSS, bordereau DGI) assemblés depuis
    # les bulletins persistés — aucune recomputation. Lecture seule.
    try:
        return {"run_id": run_id, **pay_registers(ctx.conn, run_id)}
    except WorkflowError as e:
        raise HTTPException(status_code=404, detail=str(e))

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

@app.get("/v1/runs/{run_id}/registre-paiement")
def registre_paiement(run_id: str, ctx: Ctx = Depends(require("payout.read"))):
    # Registre légal des paiements (Code du Travail art. 224-226). Lecture seule.
    try:
        return {"run_id": run_id, **payment_register(ctx.conn, run_id)}
    except WorkflowError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────── Administration INTERNE WaSalaire (back-office éditeur SaaS) ───────────────
# Rôles internes (platform_role) ≠ rôles clients (access_grant). Capacités contrôlées serveur.
_PLATFORM_ROLES = {"admin_plateforme", "super_admin"}
_INTERNAL_ROLES = {"super_admin", "admin_plateforme", "support", "conformite", "commercial"}

# Capacité interne -> rôles autorisés (super_admin est toujours autorisé, cf. require_internal).
INTERNAL_CAPS: dict[str, set[str]] = {
    "admin.dashboard.read":        _INTERNAL_ROLES,
    "admin.orgs.read":             {"admin_plateforme", "support", "commercial"},
    "admin.orgs.manage":           {"admin_plateforme"},
    "admin.internal_users.read":   {"admin_plateforme"},
    "admin.internal_users.manage": set(),                         # super_admin only
    "admin.client_users.read":     {"admin_plateforme", "support"},
    "admin.subscriptions.read":    {"admin_plateforme", "commercial"},
    "admin.subscriptions.manage":  {"admin_plateforme", "commercial"},
    "admin.referentials.read":     {"admin_plateforme", "conformite"},
    "admin.referentials.propose":  {"conformite"},
    "admin.referentials.validate": {"conformite"},                # + super_admin ; 4-eyes ≠ proposeur
    "admin.audit.read":            {"admin_plateforme"},
    "admin.support.read":          {"admin_plateforme", "support"},
    "admin.settings.manage":       set(),                         # super_admin only
}

def require_internal(cap: str):
    """Dépendance back-office ADMIN interne. super_admin toujours autorisé ; sinon selon la
    capacité. Toujours vérifié CÔTÉ SERVEUR (jamais délégué au front)."""
    def _dep(ctx: Ctx = Depends(current_ctx)) -> Ctx:
        if ctx.must_change:
            raise HTTPException(status_code=409, detail="Changement de mot de passe requis.")
        if not ctx.mfa:
            raise HTTPException(status_code=403, detail="Authentification à deux facteurs requise.")
        allowed = INTERNAL_CAPS.get(cap, set())
        if ctx.platform_role == "super_admin" or ctx.platform_role in allowed:
            return ctx
        raise HTTPException(status_code=403, detail="Réservé à l'administration WaSalaire.")
    return _dep

@app.get("/v1/admin/overview")
def admin_overview(ctx: Ctx = Depends(require_internal("admin.dashboard.read"))):
    row = ctx.conn.execute("SELECT admin_overview()").fetchone()
    return row[0] if row else {}

@app.get("/v1/admin/organizations")
def admin_organizations(ctx: Ctx = Depends(require_internal("admin.orgs.read"))):
    rows = ctx.conn.execute(
        "SELECT workspace_id, nom, type, nb_companies, plan, statut, is_beta, created_at "
        "FROM admin_organizations()").fetchall()
    return {"organizations": [{"id": str(r[0]), "nom": r[1], "type": r[2], "nb_companies": r[3],
                               "plan": r[4], "statut": r[5], "is_beta": r[6],
                               "created_at": r[7].isoformat() if r[7] else None} for r in rows]}

@app.get("/v1/admin/internal-users")
def admin_internal_users(ctx: Ctx = Depends(require_internal("admin.internal_users.read"))):
    rows = ctx.conn.execute(
        "SELECT id, email, platform_role, statut, totp_enrolled, must_change_password, created_at "
        "FROM admin_internal_users()").fetchall()
    return {"users": [{"id": str(r[0]), "email": r[1], "platform_role": r[2], "statut": r[3],
                       "totp_enrolled": r[4], "must_change_password": r[5],
                       "created_at": r[6].isoformat() if r[6] else None} for r in rows]}

class SetPlatformRoleIn(BaseModel):
    user_id: str
    platform_role: str

@app.put("/v1/admin/internal-users/role")
def admin_set_role(body: SetPlatformRoleIn, ctx: Ctx = Depends(require_internal("admin.internal_users.manage"))):
    try:
        ctx.conn.execute("SELECT admin_set_platform_role(%s, %s, %s)",
                         (ctx.user_id, body.user_id, body.platform_role)).fetchone()
    except Exception as e:
        msg = str(getattr(e, "diag", None) and e.diag.message_primary or e).strip()
        raise HTTPException(status_code=400, detail=msg or "Modification refusée")
    return {"user_id": body.user_id, "platform_role": body.platform_role}

@app.get("/v1/admin/referentials")
def admin_referentials(ctx: Ctx = Depends(require_internal("admin.referentials.read"))):
    row = ctx.conn.execute("SELECT reg_referentials_read()").fetchone()
    return row[0] if row else {}

@app.get("/v1/admin/referentials/changes")
def admin_reg_changes(ctx: Ctx = Depends(require_internal("admin.referentials.read"))):
    rows = ctx.conn.execute(
        "SELECT id, type, cible_code, payload, date_effet, source, note, statut, "
        "propose_par, valide_par, created_at, published_at FROM reg_changes_list()").fetchall()
    return {"changes": [{"id": str(r[0]), "type": r[1], "cible_code": r[2], "payload": r[3],
                         "date_effet": r[4].isoformat() if r[4] else None, "source": r[5], "note": r[6],
                         "statut": r[7], "propose_par": r[8], "valide_par": r[9],
                         "created_at": r[10].isoformat() if r[10] else None,
                         "published_at": r[11].isoformat() if r[11] else None} for r in rows]}

class RegProposeIn(BaseModel):
    type: str
    cible_code: str
    payload: dict
    date_effet: str
    source: str
    note: str | None = None

def _reg_call(ctx: Ctx, sql: str, params: tuple):
    try:
        return ctx.conn.execute(sql, params).fetchone()
    except Exception as e:
        msg = str(getattr(e, "diag", None) and e.diag.message_primary or e).strip()
        raise HTTPException(status_code=400, detail=msg or "Opération refusée")

@app.post("/v1/admin/referentials/changes")
def admin_reg_propose(body: RegProposeIn, ctx: Ctx = Depends(require_internal("admin.referentials.propose"))):
    import json as _json
    row = _reg_call(ctx, "SELECT reg_change_propose(%s,%s,%s,%s::jsonb,%s,%s,%s)",
                    (ctx.user_id, body.type, body.cible_code, _json.dumps(body.payload),
                     body.date_effet, body.source, body.note))
    return {"change_id": str(row[0])}

@app.post("/v1/admin/referentials/changes/{change_id}/validate")
def admin_reg_validate(change_id: str, ctx: Ctx = Depends(require_internal("admin.referentials.validate"))):
    _reg_call(ctx, "SELECT reg_change_validate(%s,%s)", (ctx.user_id, change_id))
    return {"change_id": change_id, "statut": "validee"}

@app.post("/v1/admin/referentials/changes/{change_id}/reject")
def admin_reg_reject(change_id: str, ctx: Ctx = Depends(require_internal("admin.referentials.validate"))):
    _reg_call(ctx, "SELECT reg_change_reject(%s,%s,%s)", (ctx.user_id, change_id, None))
    return {"change_id": change_id, "statut": "rejetee"}

@app.post("/v1/admin/referentials/changes/{change_id}/publish")
def admin_reg_publish(change_id: str, ctx: Ctx = Depends(require_internal("admin.referentials.validate"))):
    _reg_call(ctx, "SELECT reg_change_publish(%s,%s)", (ctx.user_id, change_id))
    return {"change_id": change_id, "statut": "publiee"}

@app.get("/v1/admin/audit")
def admin_audit(limit: int = 100, ctx: Ctx = Depends(require_internal("admin.audit.read"))):
    rows = ctx.conn.execute("SELECT id, user_id, email, type, ip, detail, created_at "
                            "FROM admin_audit(%s)", (limit,)).fetchall()
    return {"events": [{"id": str(r[0]), "user_id": str(r[1]) if r[1] else None, "email": r[2],
                        "type": r[3], "ip": r[4], "detail": r[5],
                        "created_at": r[6].isoformat() if r[6] else None} for r in rows]}

# ─────────────── Administration PLATEFORME (abonnements) ───────────────

@app.get("/v1/platform/users")
def platform_users(ctx: Ctx = Depends(require_internal("admin.client_users.read"))):
    rows = ctx.conn.execute(
        "SELECT id, email, platform_role, statut, totp_enrolled, must_change_password "
        "FROM app_user ORDER BY email").fetchall()
    return {"users": [{"id": str(r[0]), "email": r[1], "platform_role": r[2], "statut": r[3],
                       "totp_enrolled": r[4], "must_change_password": r[5]} for r in rows]}

@app.get("/v1/platform/subscriptions")
def platform_subscriptions(ctx: Ctx = Depends(require_internal("admin.subscriptions.read"))):
    rows = ctx.conn.execute(
        "SELECT w.id, w.nom, w.type, p.code, s.statut, s.is_beta "
        "FROM subscription s JOIN workspace w ON w.id=s.workspace_id "
        "JOIN plan p ON p.id=s.plan_id ORDER BY w.nom").fetchall()
    return {"subscriptions": [{"workspace_id": str(r[0]), "workspace": r[1], "type": r[2],
                               "plan": r[3], "statut": r[4], "is_beta": r[5]} for r in rows]}

@app.get("/v1/platform/plans")
def platform_plans(ctx: Ctx = Depends(require_internal("admin.subscriptions.read"))):
    rows = ctx.conn.execute("SELECT code, libelle, is_public, limites FROM plan ORDER BY code").fetchall()
    return {"plans": [{"code": r[0], "libelle": r[1], "is_public": r[2], "limites": r[3]} for r in rows]}

class SetPlanIn(BaseModel):
    workspace_id: str
    plan_code: str
    is_beta: bool = False

@app.put("/v1/platform/subscription")
def platform_set_plan(body: SetPlanIn, ctx: Ctx = Depends(require_internal("admin.subscriptions.manage"))):
    plan = ctx.conn.execute("SELECT id FROM plan WHERE code=%s", (body.plan_code,)).fetchone()
    if not plan:
        raise HTTPException(status_code=400, detail=f"Plan inconnu : {body.plan_code}")
    statut = "beta" if body.is_beta else "active"
    existing = ctx.conn.execute("SELECT id FROM subscription WHERE workspace_id=%s",
                                (body.workspace_id,)).fetchone()
    if existing:
        ctx.conn.execute("UPDATE subscription SET plan_id=%s, is_beta=%s, statut=%s WHERE workspace_id=%s",
                         (plan[0], body.is_beta, statut, body.workspace_id))
    else:
        ctx.conn.execute("INSERT INTO subscription(workspace_id,plan_id,statut,is_beta) VALUES (%s,%s,%s,%s)",
                         (body.workspace_id, plan[0], statut, body.is_beta))
    log_event(ctx.conn, "subscription_changed", user_id=ctx.user_id,
              detail={"workspace": body.workspace_id, "plan": body.plan_code, "is_beta": body.is_beta})
    return {"workspace_id": body.workspace_id, "plan": body.plan_code, "is_beta": body.is_beta}


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

# Service du front selon le HOST :
#   app.<domaine>  → SPA React (./webdist)         [la console/app]
#   <domaine>      → site vitrine statique (./vitrine)  [la façade publique]
# Deux surfaces, un seul déploiement. Domaines configurés sur l'app Coolify (Traefik route les deux).
_WEBDIST = Path(__file__).parent / "webdist"
_VITRINE = Path(__file__).parent / "vitrine"
_API_PREFIXES = ("v1/", "v1", "health", "docs", "openapi.json", "redoc")

def _serve_dir(base: Path, full_path: str, spa: bool):
    f = base / full_path if full_path else base / "index.html"
    if f.is_dir():
        f = f / "index.html"
    if f.is_file():
        return FileResponse(f)
    if not spa:   # vitrine : URL propre « /tarifs » → « tarifs.html »
        html = base / ((full_path or "index") + ".html")
        if html.is_file():
            return FileResponse(html)
    return FileResponse(base / "index.html")   # repli : SPA (routing client) ou accueil vitrine

if _WEBDIST.exists() or _VITRINE.exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_front(full_path: str, request: Request):
        if full_path.startswith(_API_PREFIXES):
            raise HTTPException(status_code=404, detail="Not found")
        host = request.headers.get("host", "").lower()
        # app.* = application CLIENT, admin.* = back-office INTERNE (même bundle SPA,
        # la surface est choisie côté client ; l'autorisation reste 100% serveur).
        if (host.startswith("app.") or host.startswith("admin.")) and _WEBDIST.exists():
            return _serve_dir(_WEBDIST, full_path, spa=True)
        if _VITRINE.exists():
            return _serve_dir(_VITRINE, full_path, spa=False)
        if _WEBDIST.exists():
            return _serve_dir(_WEBDIST, full_path, spa=True)
        return {"api": "WaSalaire v2", "docs": "/docs"}
else:
    @app.get("/", include_in_schema=False)
    def home():
        f = Path(__file__).parent / "frontend_v2.html"
        return FileResponse(f) if f.exists() else {"api": "WaSalaire v2", "docs": "/docs"}

    _assets = Path(__file__).parent / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")
