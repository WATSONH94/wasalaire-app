#!/usr/bin/env python3
"""
Bootstrap d'un locataire (tenant) WaSalaire + premier administrateur.

Crée, de façon idempotente et EN RÔLE SUPERUSER (hors RLS) :
  1. les rôles applicatifs (admin, paie, rh, comptable, auditeur, employe) ;
  2. un workspace (abonné) — type cabinet_comptable ou entreprise_directe ;
  3. l'arbre org_node minimal : un nœud racine (cabinet) + un nœud société lié à une `company` ;
  4. le premier utilisateur (identité téléphone, statut actif) ;
  5. un access_grant de l'admin sur le nœud racine → périmètre = toutes les sociétés du sous-arbre.

Pourquoi un script superuser et non un endpoint : la création du PREMIER tenant est un
amorçage ; la RLS `WITH CHECK` interdit d'insérer une société hors périmètre, or le périmètre
n'existe pas encore. L'amorçage privilégié résout ce cercle sans affaiblir la RLS applicative.
La création de tenants/ sociétés SUPPLÉMENTAIRES par un cabinet se fera via des fonctions
SECURITY DEFINER dédiées (migration d'onboarding), avec contrôle d'autorisation.

Usage (variables PG* superuser en environnement, comme les migrations) :
    python scripts/bootstrap_tenant.py \
        --telephone +22990000000 \
        --admin-nom "Admin WaSalaire" \
        --workspace "Cabinet Démo" --workspace-type cabinet_comptable \
        --societe "Société Démo SARL" --ifu 0000000000000

Réexécution : si l'utilisateur (téléphone) ou le workspace (nom) existent déjà, ils sont
réutilisés ; aucun doublon n'est créé. Affiche les identifiants créés (jamais de secret).
"""
from __future__ import annotations
import argparse
import os
import sys

import psycopg

ROLES = ("admin", "paie", "rh", "comptable", "auditeur", "employe")


def _one(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def ensure_roles(cur) -> dict[str, str]:
    ids: dict[str, str] = {}
    for code in ROLES:
        rid = _one(cur, "SELECT id FROM role WHERE code=%s", (code,))
        if rid is None:
            rid = _one(cur, "INSERT INTO role(code) VALUES (%s) RETURNING id", (code,))
        ids[code] = str(rid)
    return ids


def ensure_workspace(cur, nom: str, wtype: str) -> str:
    wid = _one(cur, "SELECT id FROM workspace WHERE nom=%s AND type=%s", (nom, wtype))
    if wid is None:
        wid = _one(cur,
                   "INSERT INTO workspace(nom, type) VALUES (%s,%s) RETURNING id",
                   (nom, wtype))
    return str(wid)


def ensure_cabinet_node(cur, workspace_id: str, nom: str) -> str:
    nid = _one(cur,
               "SELECT id FROM org_node WHERE tenant_id=%s AND type='cabinet' AND nom=%s",
               (workspace_id, nom))
    if nid is None:
        nid = _one(cur,
                   "INSERT INTO org_node(tenant_id, type, nom) VALUES (%s,'cabinet',%s) RETURNING id",
                   (workspace_id, nom))
    return str(nid)


def ensure_societe(cur, workspace_id: str, parent_node_id: str, nom: str,
                   ifu: str | None) -> tuple[str, str]:
    """Crée (ou retrouve) une `company` + son nœud org 'societe'. Retourne (company_id, node_id)."""
    cid = _one(cur,
               "SELECT id FROM company WHERE workspace_id=%s AND raison_sociale=%s",
               (workspace_id, nom))
    if cid is None:
        cid = _one(cur,
                   "INSERT INTO company(workspace_id, raison_sociale, ifu) VALUES (%s,%s,%s) RETURNING id",
                   (workspace_id, nom, ifu))
    nid = _one(cur, "SELECT id FROM org_node WHERE company_id=%s", (cid,))
    if nid is None:
        nid = _one(cur,
                   "INSERT INTO org_node(tenant_id, type, parent_id, nom, company_id) "
                   "VALUES (%s,'societe',%s,%s,%s) RETURNING id",
                   (workspace_id, parent_node_id, nom, cid))
    return str(cid), str(nid)


def ensure_admin(cur, telephone: str, nom: str, email: str | None) -> str:
    uid = _one(cur, "SELECT id FROM app_user WHERE telephone=%s", (telephone,))
    if uid is None:
        uid = _one(cur,
                   "INSERT INTO app_user(email, telephone, statut) VALUES (%s,%s,'actif') RETURNING id",
                   (email, telephone))
    else:
        cur.execute("UPDATE app_user SET statut='actif' WHERE id=%s", (uid,))
    return str(uid)


def ensure_grant(cur, user_id: str, node_id: str, role_id: str) -> str:
    gid = _one(cur,
               "SELECT id FROM access_grant WHERE user_id=%s AND org_node_id=%s AND role_id=%s "
               "AND (date_fin IS NULL OR date_fin >= current_date)",
               (user_id, node_id, role_id))
    if gid is None:
        gid = _one(cur,
                   "INSERT INTO access_grant(user_id, org_node_id, role_id) VALUES (%s,%s,%s) RETURNING id",
                   (user_id, node_id, role_id))
    return str(gid)


def main() -> int:
    p = argparse.ArgumentParser(description="Bootstrap tenant WaSalaire + 1er admin.")
    p.add_argument("--telephone", required=True, help="Téléphone E.164 de l'admin, ex +22990000000")
    p.add_argument("--admin-nom", default="Administrateur")
    p.add_argument("--admin-email", default=None)
    p.add_argument("--workspace", required=True, help="Nom de l'abonné (cabinet/entreprise)")
    p.add_argument("--workspace-type", default="cabinet_comptable",
                   choices=["cabinet_comptable", "entreprise_directe"])
    p.add_argument("--societe", default=None, help="Raison sociale d'une société initiale (optionnel)")
    p.add_argument("--ifu", default=None, help="IFU de la société initiale (optionnel)")
    args = p.parse_args()

    tel = args.telephone.strip()
    if not tel.startswith("+") or not tel[1:].isdigit():
        print(f"Téléphone invalide (E.164 attendu, ex +22990000000) : {tel}", file=sys.stderr)
        return 2

    # Connexion superuser (PG* en environnement, comme run_migrations.sh).
    with psycopg.connect("", autocommit=False) as conn:
        with conn.cursor() as cur:
            roles = ensure_roles(cur)
            wid = ensure_workspace(cur, args.workspace, args.workspace_type)
            cabinet_nid = ensure_cabinet_node(cur, wid, args.workspace)
            uid = ensure_admin(cur, tel, args.admin_nom, args.admin_email)
            ensure_grant(cur, uid, cabinet_nid, roles["admin"])
            societe_out = ""
            if args.societe:
                cid, snid = ensure_societe(cur, wid, cabinet_nid, args.societe, args.ifu)
                societe_out = f"\n  société     : {args.societe}  (company_id={cid}, node={snid})"
        conn.commit()

    print("Bootstrap OK (idempotent) :"
          f"\n  workspace   : {args.workspace} ({args.workspace_type})  id={wid}"
          f"\n  nœud cabinet: {cabinet_nid}"
          f"\n  admin       : {args.admin_nom}  tél={tel}  user_id={uid}  rôle=admin"
          f"{societe_out}"
          "\n\nConnexion : POST /v1/auth/request-otp puis /v1/auth/verify-otp avec ce téléphone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
