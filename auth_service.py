"""
Service d'authentification WaSalaire — email + mot de passe + MFA TOTP (obligatoire).

Complète l'identité téléphone+OTP d'`api_v2` (ne la remplace pas) : un même `app_user`
peut se connecter par téléphone+OTP (mobile) OU par email+mot de passe+TOTP (web).

Sécurité :
- Mots de passe : hachés **argon2id** (jamais en clair).
- Secret TOTP : chiffré au repos (**Fernet**, clé dérivée de WASALAIRE_SECRET).
- Codes de récupération : hachés (usage unique).
- Verrouillage anti-bruteforce + journal `security_event`.
- Aucun accès métier tant que l'enrôlement MFA obligatoire n'est pas terminé (géré par le jeton).

La connexion passée en argument n'a pas besoin de périmètre (ces tables ne sont pas RLS).
"""
from __future__ import annotations
import os, re, json, base64, hashlib, secrets

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError
from cryptography.fernet import Fernet

_ph = PasswordHasher()
ISSUER = "WaSalaire"
LOCKOUT_THRESHOLD = 5       # échecs consécutifs
LOCKOUT_WINDOW_MIN = 15     # fenêtre glissante (minutes)
RECOVERY_CODES_COUNT = 8


class AuthError(Exception):
    """Échec d'authentification (identifiants, verrouillage, MFA)."""
    def __init__(self, message: str, code: str = "auth"):
        super().__init__(message)
        self.code = code


# ─────────────── Mots de passe (argon2id) ───────────────
def hash_password(pw: str) -> str:
    return _ph.hash(pw)

def verify_password(pw: str, h: str | None) -> bool:
    if not h:
        return False
    try:
        return _ph.verify(h, pw)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False

def needs_rehash(h: str) -> bool:
    try:
        return _ph.check_needs_rehash(h)
    except Exception:
        return False

def check_password_strength(pw: str) -> None:
    """Politique « mot de passe fort » pour les mots de passe CHOISIS par l'utilisateur.
    Lève ValueError si insuffisant (10+ car., minuscule + majuscule + chiffre)."""
    if (len(pw) < 10 or not re.search(r"[a-z]", pw)
            or not re.search(r"[A-Z]", pw) or not re.search(r"\d", pw)):
        raise ValueError("Mot de passe trop faible : au moins 10 caractères, "
                         "avec une majuscule, une minuscule et un chiffre.")


# ─────────────── Secret TOTP : chiffrement au repos ───────────────
def _fernet() -> Fernet:
    secret = os.environ.get("WASALAIRE_SECRET", "dev-secret-change-me").encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)

def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()

def decrypt_secret(enc: str) -> str:
    return _fernet().decrypt(enc.encode()).decode()


# ─────────────── TOTP (RFC 6238) ───────────────
def new_totp_secret() -> str:
    return pyotp.random_base32()

def totp_uri(secret: str, email: str) -> str:
    """URI otpauth:// à encoder en QR code pour l'application Authenticator."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)

def verify_totp(secret: str, code: str) -> bool:
    try:
        return pyotp.TOTP(secret).verify(str(code).strip(), valid_window=1)
    except Exception:
        return False


# ─────────────── Codes de récupération ───────────────
def new_recovery_codes(n: int = RECOVERY_CODES_COUNT) -> list[str]:
    return ["-".join(secrets.token_hex(2) for _ in range(2)) for _ in range(n)]

def _norm_code(code: str) -> str:
    return code.strip().lower().replace(" ", "")

def hash_recovery_code(code: str) -> str:
    return _ph.hash(_norm_code(code))

def verify_recovery_code(code: str, h: str) -> bool:
    try:
        return _ph.verify(h, _norm_code(code))
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


# ─────────────── Journal de sécurité + verrouillage ───────────────
def log_event(conn, type_: str, user_id=None, email=None, ip=None, detail=None) -> None:
    conn.execute(
        "INSERT INTO security_event(user_id, email, type, ip, detail) VALUES (%s,%s,%s,%s,%s)",
        (user_id, (email.lower() if email else None), type_, ip,
         json.dumps(detail) if detail else None))

def is_locked(conn, email: str) -> bool:
    n = conn.execute(
        "SELECT count(*) FROM security_event WHERE email=%s AND type='login_fail' "
        "AND created_at > now() - make_interval(mins => %s)",
        (email.lower(), LOCKOUT_WINDOW_MIN)).fetchone()[0]
    return n >= LOCKOUT_THRESHOLD


# ─────────────── Flux de connexion (DB) ───────────────
def get_user_auth(conn, email: str):
    return conn.execute(
        "SELECT id, password_hash, must_change_password, totp_enrolled, totp_secret_enc, "
        "mfa_enforced, statut, platform_role FROM app_user WHERE lower(email)=lower(%s)",
        (email,)).fetchone()

def authenticate(conn, email: str, password: str, ip=None) -> dict:
    """Étape 1 : email + mot de passe. Retourne l'état d'authentification (sans accès métier
    tant que MFA non satisfaite). Lève AuthError (verrouillage / identifiants / compte inactif)."""
    email = email.strip()
    if is_locked(conn, email):
        log_event(conn, "lockout", email=email, ip=ip)
        raise AuthError("Trop de tentatives. Réessayez dans quelques minutes.", "locked")
    row = get_user_auth(conn, email)
    # Réponse générique anti-énumération : même message identifiants invalides.
    if not row or not verify_password(password, row[1]):
        log_event(conn, "login_fail", user_id=(row[0] if row else None), email=email, ip=ip)
        raise AuthError("Email ou mot de passe incorrect.", "invalid")
    user_id, _h, must_change, totp_enrolled, _enc, mfa_enforced, statut, platform_role = row
    if statut != "actif":
        raise AuthError("Compte inactif.", "inactive")
    log_event(conn, "login_ok", user_id=user_id, email=email, ip=ip)
    return {
        "user_id": str(user_id),
        "must_change_password": bool(must_change),
        "mfa_enforced": bool(mfa_enforced),
        "totp_enrolled": bool(totp_enrolled),
        "platform_role": platform_role,
    }

def start_totp_enrollment(conn, user_id: str, email: str) -> dict:
    """Génère un secret TOTP (chiffré stocké), renvoie le secret en clair + l'URI (QR) UNE fois.
    L'enrôlement n'est confirmé qu'après vérification d'un code (confirm_totp_enrollment)."""
    secret = new_totp_secret()
    conn.execute("UPDATE app_user SET totp_secret_enc=%s, totp_enrolled=false WHERE id=%s",
                 (encrypt_secret(secret), user_id))
    return {"secret": secret, "otpauth_uri": totp_uri(secret, email)}

def confirm_totp_enrollment(conn, user_id: str, code: str, ip=None) -> list[str]:
    """Vérifie le 1er code, active l'enrôlement et génère des codes de récupération (rendus UNE fois)."""
    row = conn.execute("SELECT totp_secret_enc FROM app_user WHERE id=%s", (user_id,)).fetchone()
    if not row or not row[0]:
        raise AuthError("Aucun enrôlement TOTP en cours.", "no_totp")
    if not verify_totp(decrypt_secret(row[0]), code):
        log_event(conn, "mfa_fail", user_id=user_id, ip=ip, detail={"phase": "enroll"})
        raise AuthError("Code incorrect.", "mfa_invalid")
    conn.execute("UPDATE app_user SET totp_enrolled=true WHERE id=%s", (user_id,))
    # (Re)génère les codes de récupération : invalide les anciens (UPDATE, jamais DELETE), stocke les hashs.
    conn.execute("UPDATE mfa_recovery_code SET used_at=now() WHERE user_id=%s AND used_at IS NULL",
                 (user_id,))
    codes = new_recovery_codes()
    for c in codes:
        conn.execute("INSERT INTO mfa_recovery_code(user_id, code_hash) VALUES (%s,%s)",
                     (user_id, hash_recovery_code(c)))
    log_event(conn, "totp_enrolled", user_id=user_id, ip=ip)
    return codes

def verify_mfa(conn, user_id: str, code: str, ip=None) -> bool:
    """Étape 2 : code TOTP (ou code de récupération usage unique). Retourne True si valide."""
    row = conn.execute(
        "SELECT totp_secret_enc, totp_enrolled FROM app_user WHERE id=%s", (user_id,)).fetchone()
    if not row or not row[1] or not row[0]:
        raise AuthError("MFA non enrôlée.", "no_totp")
    if verify_totp(decrypt_secret(row[0]), code):
        log_event(conn, "mfa_ok", user_id=user_id, ip=ip)
        return True
    # Repli : code de récupération (usage unique)
    for rid, h in conn.execute(
            "SELECT id, code_hash FROM mfa_recovery_code WHERE user_id=%s AND used_at IS NULL",
            (user_id,)).fetchall():
        if verify_recovery_code(code, h):
            conn.execute("UPDATE mfa_recovery_code SET used_at=now() WHERE id=%s", (rid,))
            log_event(conn, "mfa_ok", user_id=user_id, ip=ip, detail={"via": "recovery"})
            return True
    log_event(conn, "mfa_fail", user_id=user_id, ip=ip)
    return False

def change_password(conn, user_id: str, new_password: str, ip=None) -> None:
    """Change le mot de passe (politique forte), lève le drapeau de changement obligatoire."""
    check_password_strength(new_password)
    conn.execute("UPDATE app_user SET password_hash=%s, must_change_password=false WHERE id=%s",
                 (hash_password(new_password), user_id))
    log_event(conn, "password_changed", user_id=user_id, ip=ip)


# ─────────────── Rôle plateforme (SaaS) ───────────────
def platform_role(conn, user_id: str) -> str:
    row = conn.execute("SELECT platform_role FROM app_user WHERE id=%s", (user_id,)).fetchone()
    return row[0] if row else "none"
