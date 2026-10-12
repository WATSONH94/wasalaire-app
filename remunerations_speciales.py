"""
Rémunérations spéciales — Bénin.
- Heures supplémentaires (Code du travail Art. 147, taux minimaux légaux).
- Prorata d'entrée/sortie (choix contractuel, défaut trentièmes).
- ITS sur rémunérations exceptionnelles (CGI Art. 126, mécanisme du salaire moyen).

Aucune règle inventée ; taux HS = minima légaux surchargables par convention.
⚠️ Le détail d'articulation de l'Art. 126 (ordre abattement/quotient) est reproduit
tel que rédigé au CGI ; à faire confirmer par doctrine DGI (marqué comme réserve).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date

from moteur_paie import bareme_its

# ─────────────────────────────────────────────────────────────
# 1) HEURES SUPPLÉMENTAIRES (Art. 147) — taux MINIMAUX
# ─────────────────────────────────────────────────────────────
DUREE_LEGALE_HEBDO = 40
DIVISEUR_HORAIRE = 52 * 40 / 12  # ≈ 173,33 (surchargable par convention)

# Majorations minimales légales (Art. 147). Une convention peut majorer → max(légal, conv).
MAJORATIONS_HS = {
    "jour_41_48":     0.12,   # 41e à 48e heure
    "jour_au_dela_48": 0.35,  # au-delà de la 48e (⚑ 35 %, pas 30 %)
    "dimanche_ferie": 0.50,   # jour, dimanches & jours fériés
    "nuit_semaine":   0.50,   # nuit (21h-5h) en semaine
    "nuit_dim_ferie": 1.00,   # nuit dimanches & fériés
}


def taux_horaire(salaire_mensuel: float, diviseur: float = DIVISEUR_HORAIRE) -> float:
    return salaire_mensuel / diviseur


def heures_supplementaires(salaire_mensuel: float, heures: dict[str, float],
                           majorations: dict[str, float] | None = None,
                           diviseur: float = DIVISEUR_HORAIRE) -> dict:
    """Calcule le montant des heures supplémentaires par catégorie.
    `heures` = {"jour_41_48": 8, "jour_au_dela_48": 2, ...}.
    Majoration = taux_horaire × (1 + taux) pour chaque heure de la catégorie."""
    maj = {**MAJORATIONS_HS, **(majorations or {})}  # surcharge conventionnelle
    th = taux_horaire(salaire_mensuel, diviseur)
    detail = {}
    total = 0.0
    for cat, nb in heures.items():
        if nb <= 0:
            continue
        if cat not in maj:
            raise ValueError(f"Catégorie HS inconnue : {cat}")
        montant = th * (1 + maj[cat]) * nb
        detail[cat] = {"heures": nb, "taux_majoration": maj[cat], "montant": round(montant)}
        total += montant
    return {
        "taux_horaire": round(th, 2),
        "detail": detail,
        "total": round(total),
        "source": "Code du travail Art. 147 (minima légaux) ; base ITS+CNSS (Art. 122)",
    }


# ─────────────────────────────────────────────────────────────
# 2) PRORATA ENTRÉE / SORTIE
# ─────────────────────────────────────────────────────────────
def prorata(salaire_mensuel: float, jours_presents: int,
            methode: str = "trentiemes", jours_ouvrables_mois: int = 26) -> dict:
    """Prorata du salaire pour un mois incomplet.
    - "trentiemes" (défaut) : ÷ 30 (RG-PRORATA-001, choix par défaut).
    - "jours_ouvrables" : ÷ nombre de jours ouvrables du mois.
    Aucune règle légale imposée → paramètre contractuel/conventionnel."""
    if methode == "trentiemes":
        montant = salaire_mensuel * jours_presents / 30
    elif methode == "jours_ouvrables":
        montant = salaire_mensuel * jours_presents / jours_ouvrables_mois
    else:
        raise ValueError(f"Méthode de prorata inconnue : {methode}")
    return {
        "methode": methode,
        "jours_presents": jours_presents,
        "montant": round(montant),
        "source": "Aucune règle légale — choix contractuel (RG-PRORATA-001, défaut ÷30)",
    }


# ─────────────────────────────────────────────────────────────
# 3) ITS SUR RÉMUNÉRATIONS EXCEPTIONNELLES (CGI Art. 126)
# ─────────────────────────────────────────────────────────────
# Types bénéficiant de l'abattement 25 % (Art. 126 §3 b).
TYPES_ABATTEMENT_25 = {"ifc", "depart_volontaire"}


def its_remuneration_exceptionnelle(
    salaire_moyen_12m: float,
    remuneration_mois: float,
    remuneration_exceptionnelle: float,
    type_exceptionnel: str = "ifc",
) -> dict:
    """ITS applicable aux rémunérations exceptionnelles — mécanisme du salaire moyen
    (CGI Art. 126) :
      1. impôt sur le salaire moyen des 12 derniers mois (13e mois inclus) ;
      2. multiplier par (rémunération du mois + rém. exceptionnelles) / salaire moyen ;
      3. abattement de 25 % sur les rém. exceptionnelles type IFC/départ volontaire.
    """
    abattement = 0.25 if type_exceptionnel in TYPES_ABATTEMENT_25 else 0.0
    rem_exc_nette = remuneration_exceptionnelle * (1 - abattement)

    impot_moyen = bareme_its(salaire_moyen_12m)
    base = remuneration_mois + rem_exc_nette
    its = impot_moyen * base / salaire_moyen_12m if salaire_moyen_12m else 0

    return {
        "impot_moyen": impot_moyen,
        "abattement_applique": abattement,
        "remuneration_exceptionnelle_nette": round(rem_exc_nette),
        "base_quotient": round(base),
        "its": round(its),
        "source": "CGI Art. 126 (salaire moyen 12 mois + abattement 25% IFC/départ). "
                  "⚠️ Articulation exacte à confirmer par doctrine DGI.",
    }


# ─────────────────────────────────────────────────────────────
# 4) 13e MOIS / GRATIFICATION (conventionnel) — RG-13M-001
# ─────────────────────────────────────────────────────────────
def treizieme_mois(salaire_base: float, mois_travailles_annee: float = 12,
                   taux: float = 1.0) -> dict:
    """13e mois / gratification — **conventionnel** (la CCGT générale n'en prévoit pas).
    Montant = `taux` × salaire de base, proratisé par les mois travaillés dans l'année.
    Fiscalement traité en rémunération exceptionnelle (CGI Art. 126 : salaire moyen)."""
    mois = min(max(mois_travailles_annee, 0), 12)
    montant = salaire_base * taux * mois / 12
    return {
        "taux": taux, "mois_travailles": mois,
        "montant": round(montant),
        "source": "Conventionnel (RG-13M-001) ; fiscal = rém. exceptionnelle CGI Art. 126",
    }


# ─────────────────────────────────────────────────────────────
# 5) RETENUE POUR REMBOURSEMENT D'AVANCE — RG-AVANCE-001
# ─────────────────────────────────────────────────────────────
def retenue_avance(salaire_net: float, solde_avance_du: float,
                   quotite_max: float | None = None) -> dict:
    """Retenue mensuelle de remboursement d'une **avance** (somme prêtée d'avance).
    Plafonnée à la **quotité cessible** du net (Décret 55-972, via `saisies`) —
    ⚠️ seuils 1955 à confirmer. L'**acompte** (travail déjà fait) n'est PAS plafonné."""
    from saisies import quotite_saisissable
    q = quotite_saisissable(salaire_net)
    plafond = q["saisissable"] if quotite_max is None else quotite_max
    retenue = min(solde_avance_du, plafond)
    res = {
        "plafond_quotite": round(plafond),
        "retenue_mois": round(retenue),
        "solde_restant": round(solde_avance_du - retenue),
        "source": "RG-AVANCE-001 : plafond = quotité cessible (Décret 55-972) — Code Art. 216-219",
    }
    if quotite_max is None and "AVERTISSEMENT" in q:
        res["AVERTISSEMENT"] = q["AVERTISSEMENT"]
    return res


if __name__ == "__main__":
    print("── Heures sup (salaire 173 330 → th 1000 ; 8h@12% + 2h@35%) ──")
    r = heures_supplementaires(173330, {"jour_41_48": 8, "jour_au_dela_48": 2})
    print(r)
    print("\n── Prorata (200 000, 15 j, trentièmes) ──")
    print(prorata(200000, 15))
    print("\n── ITS exceptionnel (salaire moyen 200 000, mois 200 000, IFC 500 000) ──")
    print(its_remuneration_exceptionnelle(200000, 200000, 500000, "ifc"))
