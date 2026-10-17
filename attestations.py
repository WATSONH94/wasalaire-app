"""
Attestations RH (travail, salaire, virement) — Bénin.

Rendu TEXTE à partir des données réelles (société, salarié, contrat actif, dernier
bulletin persisté). Aucune donnée inventée : un champ absent est rendu « — » et jamais
deviné. L'export PDF/archivage signé reste une étape ultérieure (comme WaDocs).
"""
from __future__ import annotations
from datetime import date

MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]

TYPES = {"travail", "salaire", "virement"}

_LABEL = {"travail": "Attestation de travail",
          "salaire": "Attestation de salaire",
          "virement": "Attestation de paiement par virement"}


def _fmt_date(d) -> str:
    if not d:
        return "—"
    if isinstance(d, str):
        return d
    return f"{d.day} {MOIS[d.month]} {d.year}"


def _fmt_money(v) -> str:
    try:
        return f"{int(round(float(v))):,}".replace(",", " ") + " FCFA"
    except Exception:
        return "—"


def build_context(conn, company_id: str, employee_id: str) -> dict:
    """Assemble le contexte d'attestation depuis la base (sous périmètre RLS).
    Lève ValueError si le salarié est introuvable (ou hors périmètre)."""
    row = conn.execute(
        "SELECT c.raison_sociale, c.ifu, c.num_employeur_cnss, "
        "       e.nom, e.matricule, e.num_cnss, e.genre, "
        "       e.methode_paiement, e.momo_operateur, e.momo_numero, "
        "       ct.type, ct.date_debut, ct.salaire_base, pos.intitule "
        "FROM employee e JOIN company c ON c.id = e.company_id "
        "LEFT JOIN LATERAL (SELECT * FROM contract x WHERE x.employee_id = e.id "
        "    AND x.statut = 'actif' ORDER BY x.date_debut DESC LIMIT 1) ct ON true "
        "LEFT JOIN position pos ON pos.id = ct.position_id "
        "WHERE e.id = %s AND e.company_id = %s",
        (employee_id, company_id)).fetchone()
    if not row:
        raise ValueError("Salarié introuvable (ou hors périmètre).")
    (raison, ifu, num_emp_cnss, nom, matricule, num_cnss, genre,
     methode, momo_op, momo_num, type_contrat, date_debut, salaire_base, poste) = row

    # Dernier bulletin persisté (par période la plus récente).
    last = conn.execute(
        "SELECT p.net_a_payer, p.brut, pp.mois, pp.annee "
        "FROM payslip p JOIN payroll_run r ON r.id = p.run_id "
        "JOIN payroll_period pp ON pp.id = r.period_id "
        "WHERE p.employee_id = %s AND p.resultat IS NOT NULL "
        "ORDER BY pp.annee DESC, pp.mois DESC LIMIT 1", (employee_id,)).fetchone()

    methode_lib = {"mobile_money": "Mobile Money", "virement": "Virement bancaire",
                   "especes": "Espèces", "cheque": "Chèque"}.get(methode, methode or "—")
    compte = "—"
    if methode == "mobile_money" and momo_num:
        compte = f"{momo_op or 'Mobile Money'} {momo_num}"

    return {
        "societe": {"raison_sociale": raison or "—", "ifu": ifu or "—",
                    "num_employeur_cnss": num_emp_cnss or "—"},
        "salarie": {"nom": nom or "—", "matricule": matricule or "—",
                    "num_cnss": num_cnss or "—", "genre": genre},
        "contrat": {"type": type_contrat or "—", "poste": poste or "—",
                    "date_debut": _fmt_date(date_debut),
                    "salaire_base": salaire_base},
        "paiement": {"methode": methode_lib, "compte": compte},
        "dernier_bulletin": (
            {"net": float(last[0]), "brut": float(last[1]),
             "periode": f"{MOIS[last[2]]} {last[3]}"} if last else None),
    }


def render(type_attestation: str, ctx: dict, lieu: str = "Cotonou",
           aujourdhui: date | None = None) -> dict:
    """Produit {type, titre, contenu} — texte prêt à imprimer. Aucun champ deviné."""
    if type_attestation not in TYPES:
        raise ValueError(f"Type d'attestation inconnu : {type_attestation}")
    j = aujourdhui or date.today()
    s, e, ct, pay = ctx["societe"], ctx["salarie"], ctx["contrat"], ctx["paiement"]
    civ = {"H": "Monsieur", "F": "Madame"}.get(e.get("genre") or "", "Monsieur/Madame")
    entete = (f"{s['raison_sociale']}\nIFU : {s['ifu']}  ·  N° employeur CNSS : {s['num_employeur_cnss']}\n"
              f"{'—' * 48}\n")
    pied = (f"\n\nFait à {lieu}, le {_fmt_date(j)}.\n\n"
            f"Pour {s['raison_sociale']},\nLa Direction")

    if type_attestation == "travail":
        corps = (
            f"Je soussigné(e), représentant de {s['raison_sociale']}, atteste que "
            f"{civ} {e['nom']} (matricule {e['matricule']}, n° CNSS {e['num_cnss']}) "
            f"est employé(e) au sein de notre entreprise en qualité de « {ct['poste']} », "
            f"sous contrat de type {ct['type']}, depuis le {ct['date_debut']}.\n\n"
            f"La présente attestation est délivrée à l'intéressé(e) pour servir et valoir "
            f"ce que de droit.")
    elif type_attestation == "salaire":
        base = _fmt_money(ct["salaire_base"])
        db = ctx["dernier_bulletin"]
        ligne_net = (f"\nSur le dernier bulletin établi ({db['periode']}), son salaire net à payer "
                     f"s'est élevé à {_fmt_money(db['net'])} pour un brut de {_fmt_money(db['brut'])}."
                     if db else "")
        corps = (
            f"Je soussigné(e), représentant de {s['raison_sociale']}, atteste que "
            f"{civ} {e['nom']} (matricule {e['matricule']}), occupant le poste de "
            f"« {ct['poste']} » sous contrat {ct['type']} depuis le {ct['date_debut']}, "
            f"perçoit une rémunération mensuelle de base de {base}.{ligne_net}\n\n"
            f"La présente attestation est délivrée pour servir et valoir ce que de droit.")
    else:  # virement
        db = ctx["dernier_bulletin"]
        ligne_net = (f" Le dernier versement ({db['periode']}) s'élevait à {_fmt_money(db['net'])}."
                     if db else "")
        corps = (
            f"Je soussigné(e), représentant de {s['raison_sociale']}, atteste que la "
            f"rémunération de {civ} {e['nom']} (matricule {e['matricule']}) est réglée par "
            f"{pay['methode']} sur le compte : {pay['compte']}.{ligne_net}\n\n"
            f"La présente attestation est délivrée pour servir et valoir ce que de droit.")

    titre = _LABEL[type_attestation]
    contenu = f"{entete}\n{titre.upper()}\n\n{corps}{pied}"
    return {"type": type_attestation, "titre": titre, "contenu": contenu}


def generate(conn, company_id: str, employee_id: str, type_attestation: str) -> dict:
    """Pipeline complet : contexte réel → rendu texte."""
    ctx = build_context(conn, company_id, employee_id)
    out = render(type_attestation, ctx)
    out["salarie"] = ctx["salarie"]["nom"]
    return out
