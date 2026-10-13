"""
Service d'onboarding — création de la structure d'une société déjà en périmètre.

Couvre la chaîne manquante : établissement → département → poste → contrat,
et les listes de lecture associées. L'amorçage du PREMIER tenant (cabinet + société
+ admin) relève de `scripts/bootstrap_tenant.py` (superuser) ; la création de sociétés
SUPPLÉMENTAIRES par un cabinet relèvera de fonctions SECURITY DEFINER dédiées.

Isolation : la connexion passée porte déjà son périmètre (`set_scope`). Toute écriture
cible une `company_id` du périmètre → la RLS `WITH CHECK` (migration 007) la valide ;
une société hors périmètre est rejetée par la base, pas seulement par ce code.
"""
from __future__ import annotations
from datetime import date

from moteur_paie import param
from audit import audit

_CATEGORIES = {"cadre", "employe", "ouvrier_horaire"}
_TYPES_CONTRAT = {"CDI", "CDD", "apprentissage"}
_MODES = {"mensuel", "horaire"}


# ─────────────── Établissements ───────────────
def create_establishment(conn, company_id: str, nom: str, adresse: str | None = None,
                         num_cnss_etab: str | None = None, actor: str | None = None) -> dict:
    eid = conn.execute(
        "INSERT INTO establishment(company_id, nom, adresse, num_cnss_etab) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (company_id, nom, adresse, num_cnss_etab)).fetchone()[0]
    audit(conn, "establishment.create", "establishment", company_id, actor,
          apres={"establishment_id": str(eid), "nom": nom})
    return {"establishment_id": str(eid), "nom": nom}


def list_establishments(conn, company_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, nom, adresse, num_cnss_etab FROM establishment WHERE company_id=%s ORDER BY nom",
        (company_id,)).fetchall()
    return [{"id": str(r[0]), "nom": r[1], "adresse": r[2], "num_cnss_etab": r[3]} for r in rows]


# ─────────────── Départements ───────────────
def create_department(conn, company_id: str, nom: str, centre_de_cout: str | None = None,
                      actor: str | None = None) -> dict:
    did = conn.execute(
        "INSERT INTO department(company_id, nom, centre_de_cout) VALUES (%s,%s,%s) RETURNING id",
        (company_id, nom, centre_de_cout)).fetchone()[0]
    audit(conn, "department.create", "department", company_id, actor,
          apres={"department_id": str(did), "nom": nom})
    return {"department_id": str(did), "nom": nom}


def list_departments(conn, company_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, nom, centre_de_cout FROM department WHERE company_id=%s ORDER BY nom",
        (company_id,)).fetchall()
    return [{"id": str(r[0]), "nom": r[1], "centre_de_cout": r[2]} for r in rows]


# ─────────────── Postes ───────────────
def create_position(conn, company_id: str, intitule: str, categorie: str | None = None,
                    classification_conv: str | None = None, actor: str | None = None) -> dict:
    if categorie is not None and categorie not in _CATEGORIES:
        raise ValueError(f"categorie ∈ {sorted(_CATEGORIES)}")
    pid = conn.execute(
        "INSERT INTO position(company_id, intitule, categorie, classification_conv) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (company_id, intitule, categorie, classification_conv)).fetchone()[0]
    audit(conn, "position.create", "position", company_id, actor,
          apres={"position_id": str(pid), "intitule": intitule})
    return {"position_id": str(pid), "intitule": intitule}


def list_positions(conn, company_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, intitule, categorie, classification_conv FROM position "
        "WHERE company_id=%s ORDER BY intitule", (company_id,)).fetchall()
    return [{"id": str(r[0]), "intitule": r[1], "categorie": r[2], "classification_conv": r[3]}
            for r in rows]


# ─────────────── Contrats (avenant / nouveau contrat) ───────────────
def create_contract(conn, company_id: str, employee_id: str, type_contrat: str,
                    date_debut: str, salaire_base: float, mode: str = "mensuel",
                    position_id: str | None = None, department_id: str | None = None,
                    establishment_id: str | None = None, date_fin: str | None = None,
                    periode_essai_fin: str | None = None, remplacer_actif: bool = False,
                    actor: str | None = None) -> dict:
    """Crée un contrat pour un salarié de la société. Contrôle SMIG bloquant (RG-SAL-001).
    `remplacer_actif` clôt le contrat actif courant (avenant) avant d'en activer un nouveau."""
    if type_contrat not in _TYPES_CONTRAT:
        raise ValueError(f"type_contrat ∈ {sorted(_TYPES_CONTRAT)}")
    if mode not in _MODES:
        raise ValueError(f"mode ∈ {sorted(_MODES)}")
    smig = param("smig", date.today())
    if mode == "mensuel" and salaire_base < smig:
        raise ValueError(f"Salaire ({salaire_base:.0f}) < SMIG ({smig:.0f}) - refusé (RG-SAL-001).")
    # Le salarié doit appartenir à la société (sinon hors périmètre → rejeté par la RLS en lecture).
    owner = conn.execute(
        "SELECT 1 FROM employee WHERE id=%s AND company_id=%s", (employee_id, company_id)).fetchone()
    if not owner:
        raise ValueError("Salarié introuvable dans cette société.")
    if remplacer_actif:
        conn.execute("UPDATE contract SET statut='clos' WHERE employee_id=%s AND company_id=%s "
                     "AND statut='actif'", (employee_id, company_id))
    cid = conn.execute(
        "INSERT INTO contract(company_id, employee_id, type, date_debut, date_fin, "
        "periode_essai_fin, position_id, department_id, establishment_id, salaire_base, mode, statut) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'actif') RETURNING id",
        (company_id, employee_id, type_contrat, date_debut, date_fin, periode_essai_fin,
         position_id, department_id, establishment_id, salaire_base, mode)).fetchone()[0]
    audit(conn, "contract.create", "contract", company_id, actor,
          apres={"contract_id": str(cid), "employee_id": str(employee_id),
                 "type": type_contrat, "salaire_base": salaire_base})
    return {"contract_id": str(cid), "employee_id": str(employee_id)}


def list_contracts(conn, company_id: str, employee_id: str | None = None) -> list[dict]:
    if employee_id:
        rows = conn.execute(
            "SELECT id, employee_id, type, date_debut, date_fin, salaire_base, mode, statut "
            "FROM contract WHERE company_id=%s AND employee_id=%s ORDER BY date_debut DESC",
            (company_id, employee_id)).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, employee_id, type, date_debut, date_fin, salaire_base, mode, statut "
            "FROM contract WHERE company_id=%s ORDER BY date_debut DESC", (company_id,)).fetchall()
    return [{"id": str(r[0]), "employee_id": str(r[1]), "type": r[2], "date_debut": str(r[3]),
             "date_fin": str(r[4]) if r[4] else None, "salaire_base": float(r[5]),
             "mode": r[6], "statut": r[7]} for r in rows]
