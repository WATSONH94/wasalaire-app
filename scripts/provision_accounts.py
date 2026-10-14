#!/usr/bin/env python3
"""
Provisioning idempotent des comptes de test/administration WaSalaire.

Pour chaque compte : upsert `app_user` (email, hash argon2 du mot de passe initial,
must_change_password=TRUE, mfa_enforced=TRUE, provisioned_by='admin', statut='actif',
platform_role), + son organisation/plan/accès selon le scénario. Réexécutable sans doublon.

SÉCURITÉ :
- Les mots de passe sont LUS d'un fichier **gitignoré** `scripts/accounts_credentials.json`
  (format {"email": "motdepasse", ...}), jamais en dur dans ce fichier ni committés.
- Si un mot de passe manque, un mot de passe aléatoire est généré et écrit dans
  `scripts/accounts_initial_credentials.out.json` (gitignoré) pour remise sécurisée à l'admin.
- Seuls des HASHS sont stockés en base. Aucun mot de passe n'est affiché.
- MFA TOTP OBLIGATOIRE : les comptes sont créés NON enrôlés → l'enrôlement Authenticator est
  imposé à la première connexion (aucun accès métier avant). L'activation administrative ne vaut
  PAS vérification de l'adresse email (email_verifie reste FALSE ; provisioned_by='admin').

Exécuter avec les variables PG* superuser en environnement (comme les migrations) :
    python scripts/provision_accounts.py            # provisionne / met à jour
    python scripts/provision_accounts.py --dry-run  # affiche le plan sans écrire
"""
from __future__ import annotations
import argparse
import json
import os
import secrets
import sys
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))   # rend `auth_service` (racine du projet) importable quel que soit le cwd
from auth_service import hash_password  # noqa: E402
CRED_IN = HERE / "accounts_credentials.json"            # gitignoré : {email: motdepasse}
CRED_OUT = HERE / "accounts_initial_credentials.out.json"  # gitignoré : mots de passe générés

ROLES = ("admin", "paie", "rh", "comptable", "auditeur", "employe")

# Définition des 7 comptes (NON secret : emails + scénario). Les mots de passe viennent du fichier gitignoré.
ACCOUNTS = [
    {"email": "bodjrenouhugues1994@gmail.com", "platform_role": "admin_plateforme", "label": "Admin plateforme", "org": None},
    {"email": "hugues.techbo@gmail.com",       "platform_role": "super_admin",      "label": "Super-admin plateforme", "org": None},
    {"email": "hugues.formations@gmail.com",   "platform_role": "none", "label": "Bêta — grande entreprise multi-sites",
     "org": {"ws_type": "entreprise_directe", "ws_name": "Grande Entreprise Démo", "societe": "Grande Entreprise Démo SA",
             "plan": "entreprise", "beta": True, "etablissements": ["Siège Cotonou", "Site Parakou", "Site Bohicon"]}},
    {"email": "hugues.dscg2@gmail.com",        "platform_role": "none", "label": "Bêta — abonné accès complet",
     "org": {"ws_type": "entreprise_directe", "ws_name": "Abonné Complet Démo", "societe": "Abonné Complet SARL",
             "plan": "pro", "beta": True}},
    {"email": "huguesbodjrenou1994@gmail.com", "platform_role": "none", "label": "Bêta — cabinet multi-clients",
     "org": {"ws_type": "cabinet_comptable", "ws_name": "Cabinet Démo", "plan": "cabinet", "beta": True,
             "clients": ["Client Alpha SARL", "Client Beta SARL"]}},
    {"email": "watsonhugues1994@gmail.com",    "platform_role": "none", "label": "Freemium sans abonnement",
     "org": {"ws_type": "entreprise_directe", "ws_name": "Freemium Démo", "societe": "Freemium Démo SARL",
             "plan": "freemium", "beta": False}},
    {"email": "hugues.dscg@gmail.com",         "platform_role": "none", "label": "Bêta — entreprise classique",
     "org": {"ws_type": "entreprise_directe", "ws_name": "Entreprise Classique Démo", "societe": "Entreprise Classique SARL",
             "plan": "standard", "beta": True}},
]


def _one(cur, sql, params=()):
    cur.execute(sql, params)
    r = cur.fetchone()
    return r[0] if r else None


def load_passwords() -> dict[str, str]:
    creds = {}
    if CRED_IN.exists():
        creds = json.loads(CRED_IN.read_text(encoding="utf-8"))
    generated = {}
    for acc in ACCOUNTS:
        if acc["email"] not in creds or not creds[acc["email"]]:
            pw = secrets.token_urlsafe(12)           # mot de passe initial aléatoire fort
            creds[acc["email"]] = pw
            generated[acc["email"]] = pw
    if generated:
        CRED_OUT.write_text(json.dumps(generated, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[info] {len(generated)} mot(s) de passe généré(s) → {CRED_OUT.name} (gitignoré, à remettre en sécurité).")
    return creds


def ensure_roles(cur) -> dict[str, str]:
    ids = {}
    for code in ROLES:
        rid = _one(cur, "SELECT id FROM role WHERE code=%s", (code,)) \
            or _one(cur, "INSERT INTO role(code) VALUES (%s) RETURNING id", (code,))
        ids[code] = rid
    return ids


def ensure_plan(cur, code: str) -> str:
    pid = _one(cur, "SELECT id FROM plan WHERE code=%s", (code,))
    if not pid:
        raise SystemExit(f"Plan inconnu '{code}' (migration 009 non appliquée ?).")
    return pid


def ensure_user(cur, email: str, password_hash: str, platform_role: str) -> str:
    uid = _one(cur, "SELECT id FROM app_user WHERE lower(email)=lower(%s)", (email,))
    if uid:
        # Mise à jour sans écraser un éventuel enrôlement MFA déjà réalisé par l'utilisateur.
        cur.execute(
            "UPDATE app_user SET password_hash=%s, must_change_password=true, statut='actif', "
            "provisioned_by='admin', mfa_enforced=true, platform_role=%s WHERE id=%s",
            (password_hash, platform_role, uid))
    else:
        uid = _one(cur,
            "INSERT INTO app_user(email, password_hash, must_change_password, statut, "
            "provisioned_by, email_verifie, mfa_enforced, platform_role) "
            "VALUES (%s,%s,true,'actif','admin',false,true,%s) RETURNING id",
            (email, password_hash, platform_role))
    return uid


def ensure_workspace(cur, nom: str, wtype: str) -> str:
    return (_one(cur, "SELECT id FROM workspace WHERE nom=%s AND type=%s", (nom, wtype))
            or _one(cur, "INSERT INTO workspace(nom,type) VALUES (%s,%s) RETURNING id", (nom, wtype)))


def ensure_node(cur, workspace_id, type_, nom, parent_id=None, company_id=None) -> str:
    if company_id:
        nid = _one(cur, "SELECT id FROM org_node WHERE company_id=%s", (company_id,))
        if nid:
            return nid
    else:
        nid = _one(cur, "SELECT id FROM org_node WHERE tenant_id=%s AND type=%s AND nom=%s "
                   "AND parent_id IS NOT DISTINCT FROM %s", (workspace_id, type_, nom, parent_id))
        if nid:
            return nid
    return _one(cur,
        "INSERT INTO org_node(tenant_id,type,parent_id,nom,company_id) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (workspace_id, type_, parent_id, nom, company_id))


def ensure_company(cur, workspace_id, nom) -> str:
    return (_one(cur, "SELECT id FROM company WHERE workspace_id=%s AND raison_sociale=%s", (workspace_id, nom))
            or _one(cur, "INSERT INTO company(workspace_id,raison_sociale) VALUES (%s,%s) RETURNING id",
                    (workspace_id, nom)))


def ensure_establishment(cur, company_id, nom):
    if not _one(cur, "SELECT id FROM establishment WHERE company_id=%s AND nom=%s", (company_id, nom)):
        cur.execute("INSERT INTO establishment(company_id,nom) VALUES (%s,%s)", (company_id, nom))


def ensure_subscription(cur, workspace_id, plan_id, is_beta):
    sid = _one(cur, "SELECT id FROM subscription WHERE workspace_id=%s", (workspace_id,))
    statut = "beta" if is_beta else "active"
    if sid:
        cur.execute("UPDATE subscription SET plan_id=%s, is_beta=%s, statut=%s WHERE id=%s",
                    (plan_id, is_beta, statut, sid))
    else:
        cur.execute("INSERT INTO subscription(workspace_id,plan_id,statut,is_beta) VALUES (%s,%s,%s,%s)",
                    (workspace_id, plan_id, statut, is_beta))


def ensure_grant(cur, user_id, node_id, role_id):
    if not _one(cur, "SELECT id FROM access_grant WHERE user_id=%s AND org_node_id=%s AND role_id=%s "
                "AND (date_fin IS NULL OR date_fin >= current_date)", (user_id, node_id, role_id)):
        cur.execute("INSERT INTO access_grant(user_id,org_node_id,role_id) VALUES (%s,%s,%s)",
                    (user_id, node_id, role_id))


def provision_org(cur, roles, uid, org):
    wid = ensure_workspace(cur, org["ws_name"], org["ws_type"])
    ensure_subscription(cur, wid, ensure_plan(cur, org["plan"]), org.get("beta", False))
    if org["ws_type"] == "cabinet_comptable":
        cabinet = ensure_node(cur, wid, "cabinet", org["ws_name"])
        for client_nom in org.get("clients", []):
            client_node = ensure_node(cur, wid, "client", client_nom, parent_id=cabinet)
            comp = ensure_company(cur, wid, client_nom)
            ensure_node(cur, wid, "societe", client_nom, parent_id=client_node, company_id=comp)
        ensure_grant(cur, uid, cabinet, roles["admin"])         # admin cabinet → toutes les sociétés clientes
    else:  # entreprise_directe
        comp = ensure_company(cur, wid, org["societe"])
        soc = ensure_node(cur, wid, "societe", org["societe"], company_id=comp)
        for etab in org.get("etablissements", []):
            ensure_establishment(cur, comp, etab)
        ensure_grant(cur, uid, soc, roles["admin"])


def main() -> int:
    ap = argparse.ArgumentParser(description="Provisioning des comptes WaSalaire (idempotent).")
    ap.add_argument("--dry-run", action="store_true", help="n'écrit rien, affiche le plan")
    args = ap.parse_args()

    passwords = load_passwords()
    with psycopg.connect("", autocommit=False) as conn:
        with conn.cursor() as cur:
            roles = ensure_roles(cur)
            summary = []
            for acc in ACCOUNTS:
                email = acc["email"]
                if args.dry_run:
                    summary.append((email, acc["label"], acc["platform_role"],
                                    (acc["org"]["plan"] if acc["org"] else "—")))
                    continue
                uid = ensure_user(cur, email, hash_password(passwords[email]), acc["platform_role"])
                if acc["org"]:
                    provision_org(cur, roles, uid, acc["org"])
                summary.append((email, acc["label"], acc["platform_role"],
                                (acc["org"]["plan"] if acc["org"] else "—")))
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()

    print("\n=== Récapitulatif des 7 comptes (mots de passe NON affichés) ===")
    print(f"{'Email':<34} {'Profil':<38} {'Rôle plateforme':<17} Plan")
    for email, label, prole, plan in summary:
        print(f"{email:<34} {label:<38} {prole:<17} {plan}")
    print("\nTous : must_change_password=TRUE, MFA Authenticator OBLIGATOIRE (enrôlement à la 1re connexion),"
          " email NON vérifié (provisioned_by=admin). Aucun accès métier avant enrôlement MFA.")
    if not args.dry_run:
        print("Récupération des identifiants initiaux : fichier gitignoré "
              f"'{CRED_IN.name}' (fournis) ou '{CRED_OUT.name}' (générés).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
