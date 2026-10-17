"""
Service RH — câble l'entrée/sortie salarié et les congés au backend.
S'appuie sur le moteur testé (`solde_tout_compte`, `conges_maternite`) et le SMIG.
Les connexions passées portent leur scope (scope-RLS) ; ce module ne gère pas l'isolation.
"""
from __future__ import annotations
from datetime import date

from moteur_paie import param
from conges_maternite import droit_conges_annuels, allocation_conge
from solde_tout_compte import solde_tout_compte, TYPES_RUPTURE
from audit import audit


# ─────────────── Entrée salarié (création) ───────────────
def create_employee(conn, company_id: str, matricule: str, nom: str,
                    salaire_base: float, type_contrat: str = "CDI",
                    date_debut: str | None = None, methode_paiement: str = "especes",
                    num_cnss: str | None = None, periode: date | None = None,
                    actor: str | None = None) -> dict:
    """Crée un salarié + son contrat. Contrôle SMIG bloquant (RG-SAL-001)."""
    smig = param("smig", periode or date.today())
    if salaire_base < smig:
        raise ValueError(f"Salaire ({salaire_base:.0f}) < SMIG ({smig:.0f}) - création refusée (RG-SAL-001).")
    emp_id = conn.execute(
        "INSERT INTO employee(company_id, matricule, nom, num_cnss, methode_paiement) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (company_id, matricule, nom, num_cnss, methode_paiement)).fetchone()[0]
    conn.execute(
        "INSERT INTO contract(company_id, employee_id, type, date_debut, salaire_base, mode, statut) "
        "VALUES (%s,%s,%s,%s,%s,'mensuel','actif')",
        (company_id, emp_id, type_contrat, date_debut or date.today().isoformat(), salaire_base))
    audit(conn, "employee.create", "employee", company_id, actor,
          apres={"employee_id": str(emp_id), "matricule": matricule, "salaire_base": salaire_base})
    return {"employee_id": str(emp_id), "matricule": matricule, "cnss_manquant": num_cnss is None}


# ─────────────── Sortie salarié (solde de tout compte) ───────────────
def rupture(conn, company_id: str, employee_id: str, type_rupture: str,
            anciennete_ans: float, jours_travailles_dernier_mois: int = 30,
            jours_conges_acquis_non_pris: int = 0, preavis_indemnite: float = 0.0,
            actor: str | None = None, preview: bool = False) -> dict:
    """Calcule le solde de tout compte. `preview=True` : CALCUL SEUL, aucun effet
    (ne clôt pas le contrat, pas d'audit) → sert à montrer les montants avant de confirmer.
    `preview=False` : COMMIT = clôt le contrat actif + trace l'opération."""
    if type_rupture not in TYPES_RUPTURE:
        raise ValueError(f"type_rupture ∈ {sorted(TYPES_RUPTURE)}")
    # Filtre company_id : ne jamais agir sur le salarié d'une autre société (P0-06/P2-02).
    row = conn.execute(
        "SELECT c.salaire_base FROM contract c WHERE c.employee_id=%s AND c.company_id=%s "
        "AND c.statut='actif' ORDER BY c.date_debut DESC LIMIT 1",
        (employee_id, company_id)).fetchone()
    if not row:
        raise ValueError("Aucun contrat actif pour ce salarié dans cette société.")
    salaire = float(row[0])
    res = solde_tout_compte(
        type_rupture=type_rupture, salaire_mensuel=salaire, salaire_moyen_12m=salaire,
        anciennete_ans=anciennete_ans, jours_travailles_dernier_mois=jours_travailles_dernier_mois,
        jours_conges_acquis_non_pris=jours_conges_acquis_non_pris,
        salaires_12m_pour_conges=salaire * 12, preavis_indemnite=preavis_indemnite)
    res.pop("detail_fiscal", None)
    res["preview"] = bool(preview)
    if preview:
        return res   # aucun effet de bord : le contrat reste actif
    conn.execute("UPDATE contract SET statut='clos' WHERE employee_id=%s AND company_id=%s "
                 "AND statut='actif'", (employee_id, company_id))
    audit(conn, "employee.rupture", "contract", company_id, actor,
          apres={"employee_id": str(employee_id), "type_rupture": type_rupture,
                 "anciennete_ans": anciennete_ans})
    return res


# ─────────────── Congés & absences ───────────────
def request_leave(conn, company_id: str, employee_id: str, type_: str,
                  date_debut: str, date_fin: str, jours: float, motif: str | None = None) -> str:
    return str(conn.execute(
        "INSERT INTO leave_request(company_id, employee_id, type, date_debut, date_fin, jours, motif) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (company_id, employee_id, type_, date_debut, date_fin, jours, motif)).fetchone()[0])


def validate_leave(conn, request_id: str, user_id: str | None, accord: bool) -> None:
    row = conn.execute("SELECT company_id, statut FROM leave_request WHERE id=%s",
                       (request_id,)).fetchone()
    conn.execute("UPDATE leave_request SET statut=%s, valide_par=%s WHERE id=%s",
                 ("valide" if accord else "refuse", user_id, request_id))
    if row:
        audit(conn, "leave.validate", "leave_request", str(row[0]), user_id,
              avant={"statut": row[1]}, apres={"statut": "valide" if accord else "refuse"})


def list_leaves(conn, company_id: str) -> list[dict]:
    """Liste les demandes de congé/absence d'une société (RLS : périmètre déjà posé)."""
    rows = conn.execute(
        "SELECT l.id, e.nom, e.matricule, l.type, l.date_debut, l.date_fin, l.jours, "
        "       l.statut, l.motif "
        "FROM leave_request l JOIN employee e ON e.id = l.employee_id "
        "WHERE l.company_id = %s ORDER BY l.created_at DESC LIMIT 200", (company_id,)).fetchall()
    return [dict(id=str(r[0]), nom=r[1], matricule=r[2], type=r[3],
                 date_debut=str(r[4]), date_fin=str(r[5]), jours=float(r[6]),
                 statut=r[7], motif=r[8]) for r in rows]


def leave_balance(conn, employee_id: str, mois_service: int = 12, anciennete_ans: int = 0,
                  annee: int | None = None) -> dict:
    """Solde de congés = acquis (Art. 158) − pris (demandes validées DE L'ANNÉE).
    L'année de référence est filtrée (par défaut l'année courante) - corrige N/P2-02."""
    acquis = droit_conges_annuels(mois_service=mois_service, anciennete_ans=anciennete_ans)["jours_acquis"]
    an = annee if annee is not None else date.today().year
    pris = conn.execute(
        "SELECT COALESCE(SUM(jours),0) FROM leave_request "
        "WHERE employee_id=%s AND type='conge_annuel' AND statut='valide' "
        "AND EXTRACT(YEAR FROM date_debut)=%s", (employee_id, an)).fetchone()[0]
    pris = float(pris or 0)
    return {"acquis": acquis, "pris": pris, "solde": round(acquis - pris, 1), "annee": an,
            "source": "Code Art. 158 (acquisition) ; pris = demandes validées de l'année"}
