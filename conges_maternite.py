"""
Module congés payés, maternité & indemnités de rupture — Bénin.
Fondé sur : Code du travail L.98-004 Art. 152, 158-165, 170 ; Loi 98-019 (maternité) ;
CCGT 2005 Art. 36 (licenciement), 37 (décès), 57/82 (retraite).

⚠️ Prototype : montants de rupture à contresigner par un juriste social béninois.
Aucune règle inventée ; chaque fonction cite son article.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date


# ─────────────────────────────────────────────────────────────
# 1) ACQUISITION DES CONGÉS (Code Art. 158)
# ─────────────────────────────────────────────────────────────
JOURS_PAR_MOIS = 2            # Art. 158 : 2 j ouvrables / mois → 24 j/an
PLAFOND_JOURS = 30            # Art. 158 : plafond 30 j ouvrables / 12 mois


def droit_conges_annuels(
    mois_service: int,
    anciennete_ans: int = 0,
    age: int | None = None,
    enfants_a_charge: int = 0,
    sexe: str = "H",
) -> dict:
    """Jours de congé acquis (Art. 152 & 158).

    - Base : 2 j / mois de service effectif.
    - Majoration ancienneté (même entreprise) : +2 (20 ans), +4 (25 ans), +6 (30 ans).
    - Jeunes < 18 ans : 30 j ; mères (enfant à charge < 15 ans) : +2 j/enfant
      (< 21 ans) ou +2 j à partir du 4e enfant (> 21 ans).
    - Plafond global : 30 j ouvrables.
    """
    base = mois_service * JOURS_PAR_MOIS

    # Majoration ancienneté (Art. 158)
    maj_anc = 0
    if anciennete_ans >= 30:
        maj_anc = 6
    elif anciennete_ans >= 25:
        maj_anc = 4
    elif anciennete_ans >= 20:
        maj_anc = 2

    # Jeunes travailleurs (Art. 152)
    if age is not None and age < 18:
        base = max(base, 30)  # 30 j pour les < 18 ans (pour 12 mois)

    # Mères de famille (Art. 158)
    maj_enfants = 0
    if sexe == "F" and enfants_a_charge > 0:
        if age is not None and age < 21:
            maj_enfants = 2 * enfants_a_charge
        else:  # > 21 ans : +2 j à partir du 4e enfant
            maj_enfants = 2 * max(0, enfants_a_charge - 3)
        # Réduit à 1 j/enfant si congé normal ≤ 6 j (Art. 158)
        if base <= 6:
            maj_enfants = maj_enfants // 2

    total = base + maj_anc + maj_enfants
    return {
        "jours_base": mois_service * JOURS_PAR_MOIS,
        "majoration_anciennete": maj_anc,
        "majoration_enfants": maj_enfants,
        "jours_acquis": min(total, PLAFOND_JOURS),
        "plafonne": total > PLAFOND_JOURS,
        "source": "Code du travail Art. 152 & 158",
    }


# ─────────────────────────────────────────────────────────────
# 2) ALLOCATION DE CONGÉ (Code Art. 165)
# ─────────────────────────────────────────────────────────────
def allocation_conge(
    salaires_indemnites_12m: float,
    exclusions_12m: float = 0.0,
    jours_pris: int | None = None,
    jours_annuels: int = 24,
) -> dict:
    """Allocation de congé (Art. 165).

    ≥ 1/12 des salaires et indemnités des 12 mois précédents, DÉDUCTION FAITE
    des primes de rendement, remboursements de frais et indemnité de sujétion
    expatriés (`exclusions_12m`). Proratisée sur les jours effectivement pris.
    """
    assiette = salaires_indemnites_12m - exclusions_12m
    mensuel = assiette / 12
    if jours_pris is None:
        montant = mensuel  # allocation d'un mois de congé complet
    else:
        montant = mensuel * (jours_pris / jours_annuels)
    return {
        "assiette_12m": round(assiette),
        "allocation_mensuelle": round(mensuel),
        "montant": round(montant),
        "source": "Code du travail Art. 165 (min 1/12) ; imposable ITS (CGI Art. 120 §1)",
    }


# ─────────────────────────────────────────────────────────────
# 3) CONGÉ DE MATERNITÉ (Code Art. 170 + Loi 98-019)
# ─────────────────────────────────────────────────────────────
SEMAINES_MATERNITE = 14       # 6 avant + 8 après (Art. 170)
TAUX_REMB_CNSS = 0.50         # CNSS rembourse jusqu'à 50 % à l'employeur


def conge_maternite(salaire_mensuel: float, semaines: int = SEMAINES_MATERNITE) -> dict:
    """Congé maternité : maintien 100 % du salaire par l'employeur ;
    la CNSS rembourse jusqu'à 50 % à l'employeur (produit à recevoir).
    Le compteur maternité est distinct des congés annuels (ne les réduit pas)."""
    salaire_journalier = salaire_mensuel * 12 / 365
    jours = semaines * 7
    montant_total = round(salaire_journalier * jours)
    remb_cnss = round(montant_total * TAUX_REMB_CNSS)
    return {
        "semaines": semaines,
        "jours": jours,
        "salaire_maintenu_100pct": montant_total,
        "a_la_charge_employeur_net": montant_total - remb_cnss,
        "remboursement_cnss_50pct": remb_cnss,
        "source": "Code du travail Art. 170 + Loi 98-019 ; hors congés annuels (Art. 158)",
    }


# ─────────────────────────────────────────────────────────────
# 4) INDEMNITÉ DE LICENCIEMENT (CCGT 2005 Art. 36)
# ─────────────────────────────────────────────────────────────
# Barème individuel : % du salaire mensuel moyen, par tranche d'ancienneté.
BAREME_LICENCIEMENT_INDIV = [  # (borne_sup_ans, pourcentage/an) ; None = au-delà
    (5,    0.30),   # 1re à 5e année : 30 %
    (10,   0.35),   # 6e à 10e année : 35 %
    (None, 0.40),   # au-delà de 10 ans : 40 %
]


def indemnite_licenciement(salaire_moyen: float, anciennete_ans: float) -> dict:
    """Indemnité de licenciement individuel (CCGT 2005 Art. 36).
    Barème progressif par tranche : 30 % / 35 % / 40 % du salaire moyen par
    année de présence dans la tranche. Pas due si faute lourde (à gérer en amont).
    """
    montant, prev = 0.0, 0
    detail = []
    for borne, taux in BAREME_LICENCIEMENT_INDIV:
        hi = borne if borne is not None else anciennete_ans
        if anciennete_ans > prev:
            annees = min(anciennete_ans, hi) - prev
            part = salaire_moyen * taux * annees
            montant += part
            detail.append({"tranche": f"{prev}-{hi if borne else '+'} ans",
                            "taux": taux, "annees": round(annees, 2),
                            "montant": round(part)})
            prev = hi
        else:
            break
    return {
        "anciennete_ans": anciennete_ans,
        "montant": round(montant),
        "detail": detail,
        "source": "CCGT 2005 Art. 36 (indiv. 30/35/40) ; exonéré ITS partiellement (CGI Art. 120 §1)",
    }


# ─────────────────────────────────────────────────────────────
# 5) INDEMNITÉ DE DÉPART À LA RETRAITE (CCGT 2005 Art. 57)
# ─────────────────────────────────────────────────────────────
def indemnite_depart_retraite(salaire_moyen: float, anciennete_ans: float) -> dict:
    """Départ à la retraite = pourcentage de l'indemnité de licenciement,
    minimum 3 mois de salaire (CCGT Art. 57). Prototype : on retient le
    barème licenciement plafonné par le minimum légal de 3 mois."""
    base = indemnite_licenciement(salaire_moyen, anciennete_ans)["montant"]
    minimum = round(salaire_moyen * 3)
    montant = max(base, minimum)
    return {
        "montant": montant,
        "minimum_3_mois": minimum,
        "base_licenciement": base,
        "source": "CCGT 2005 Art. 57 (min 3 mois)",
    }


# ─────────────────────────────────────────────────────────────
# 6) MAINTIEN DE SALAIRE EN CAS DE MALADIE (CCGT 2005 Art. 19) — RG-MALADIE-001
# ─────────────────────────────────────────────────────────────
def maintien_maladie(salaire_mensuel: float, anciennete_ans: float,
                     mois_absence: float, preavis_mois: int = 1) -> dict:
    """Maintien de salaire dégressif en cas de maladie (CCGT Art. 19-20).

    Barème par ancienneté :
      - < 12 mois          → plein salaire pendant la durée du préavis (`preavis_mois`) ;
      - 12 mois à 5 ans    → plein 3 mois, puis demi 3 mois ;
      - > 5 ans            → plein 6 mois.
    Au-delà, le relais est assuré par la CNSS (indemnités journalières AT/MP) / non payé.
    Le salaire maintenu est **imposable ITS** (CGI Art. 122 §2).
    """
    if anciennete_ans < 1:
        plein_mois, demi_mois = preavis_mois, 0
    elif anciennete_ans <= 5:
        plein_mois, demi_mois = 3, 3
    else:
        plein_mois, demi_mois = 6, 0

    mois_plein = min(mois_absence, plein_mois)
    mois_demi = min(max(mois_absence - plein_mois, 0), demi_mois)
    montant = salaire_mensuel * mois_plein + salaire_mensuel * 0.5 * mois_demi
    return {
        "plein_mois": plein_mois, "demi_mois": demi_mois,
        "mois_payes_plein": mois_plein, "mois_payes_demi": mois_demi,
        "montant_maintenu": round(montant),
        "source": "CCGT 2005 Art. 19-20 ; salaire maintenu imposable ITS (CGI Art. 122 §2)",
    }


# ─────────────────────────────────────────────────────────────
# 7) CAPITAL DÉCÈS (CCGT 2005 Art. 37) — RG-DECES-001
# ─────────────────────────────────────────────────────────────
def capital_deces(salaire_moyen: float, salaire_base: float,
                  anciennete_ans: float) -> dict:
    """Capital décès versé aux ayants droit (CCGT Art. 37) :
    = indemnité de licenciement individuel due  +  1 mois de salaire de base par
    année de présence. (Le solde s'y ajoute : salaire de présence, allocation de
    congé, indemnités acquises — cf. `solde_tout_compte`.)
    ⚠️ Fiscalité de l'année du décès : article CGI exact À CONFIRMER (jury J2).
    """
    ind_lic = indemnite_licenciement(salaire_moyen, anciennete_ans)["montant"]
    part_anciennete = round(salaire_base * anciennete_ans)  # 1 mois base / année
    return {
        "indemnite_licenciement": ind_lic,
        "part_anciennete_1mois_par_an": part_anciennete,
        "montant": ind_lic + part_anciennete,
        "source": "CCGT 2005 Art. 37 (indemnité licenciement + 1 mois base/année)",
    }


if __name__ == "__main__":
    print("── Acquisition congés (18 mois, 22 ans ancienneté) ──")
    print(droit_conges_annuels(mois_service=12, anciennete_ans=22))
    print("\n── Allocation congé (brut 200k×12, 24 j pris) ──")
    print(allocation_conge(2_400_000, exclusions_12m=0, jours_pris=24))
    print("\n── Maternité (salaire 150k) ──")
    print(conge_maternite(150_000))
    print("\n── Licenciement (salaire 200k, 8 ans) ──")
    print(indemnite_licenciement(200_000, 8))
    print("\n── Départ retraite (salaire 200k, 8 ans) ──")
    print(indemnite_depart_retraite(200_000, 8))
