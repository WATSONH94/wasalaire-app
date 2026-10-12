"""
Solde de tout compte (rupture) — Bénin. Intègre les briques :
- salaire du mois au prorata (remunerations_speciales.prorata),
- indemnité compensatrice de congés non pris (conges_maternite.allocation_conge),
- indemnité de rupture selon le type (conges_maternite : licenciement/retraite),
- traitement fiscal ITS des sommes exceptionnelles (remunerations_speciales, Art. 126).

Matérialise le Workflow 3 (`17/parcours-workflows-critiques.md`). Aucune règle inventée ;
chaque composante cite sa source. À contresigner par un juriste social avant production.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date

from conges_maternite import (allocation_conge, indemnite_licenciement,
                              indemnite_depart_retraite, capital_deces)
from remunerations_speciales import prorata, its_remuneration_exceptionnelle


TYPES_RUPTURE = {"licenciement", "demission", "retraite", "fin_cdd", "deces"}


def solde_tout_compte(
    type_rupture: str,
    salaire_mensuel: float,
    salaire_moyen_12m: float,
    anciennete_ans: float,
    jours_travailles_dernier_mois: int,
    jours_conges_acquis_non_pris: int,
    salaires_12m_pour_conges: float,
    preavis_indemnite: float = 0.0,
    jours_conges_annuels: int = 24,
) -> dict:
    """Calcule le solde de tout compte. `preavis_indemnite` = indemnité
    compensatrice de préavis si non effectué (0 sinon)."""
    if type_rupture not in TYPES_RUPTURE:
        raise ValueError(f"Type de rupture inconnu : {type_rupture}")

    # 1) Salaire du mois au prorata (défaut trentièmes)
    salaire_mois = prorata(salaire_mensuel, jours_travailles_dernier_mois)["montant"]

    # 2) Indemnité compensatrice de congés non pris (Art. 165)
    ind_conges = allocation_conge(
        salaires_12m_pour_conges, jours_pris=jours_conges_acquis_non_pris,
        jours_annuels=jours_conges_annuels)["montant"]

    # 3) Indemnité de rupture selon le type
    ind_rupture = 0
    type_exceptionnel = "autre"
    if type_rupture in ("licenciement", "fin_cdd"):
        # fin_cdd = indemnité de fin de collaboration = indemnité de licenciement (Loi 2017-05 Art. 13)
        ind_rupture = indemnite_licenciement(salaire_moyen_12m, anciennete_ans)["montant"]
        type_exceptionnel = "ifc"  # indemnité de licenciement → abattement 25 % (Art. 126)
    elif type_rupture == "retraite":
        ind_rupture = indemnite_depart_retraite(salaire_moyen_12m, anciennete_ans)["montant"]
        type_exceptionnel = "ifc"
    elif type_rupture == "deces":
        # Capital décès (CCGT Art. 37) = indemnité licenciement + 1 mois base/année
        ind_rupture = capital_deces(salaire_moyen_12m, salaire_mensuel, anciennete_ans)["montant"]
        type_exceptionnel = "ifc"  # ⚠️ fiscalité année du décès À CONFIRMER (jury J2)
    # démission : pas d'indemnité de licenciement

    # 4) Traitement fiscal ITS
    #    - Rémunérations exceptionnelles (rupture) : indemnité de rupture (abattement 25 % si IFC),
    #      + préavis + congés = imposables (Art. 126 / CGI Art. 120 §1).
    #    Le salaire du mois suit l'ITS normal (calculé au bulletin) ; ici on isole l'exceptionnel.
    rem_exceptionnelle = ind_rupture
    rem_mois_imposable = salaire_mois + ind_conges + preavis_indemnite
    its = its_remuneration_exceptionnelle(
        salaire_moyen_12m, rem_mois_imposable, rem_exceptionnelle,
        type_exceptionnel=type_exceptionnel)

    total_brut = salaire_mois + ind_conges + ind_rupture + preavis_indemnite
    net_estime = total_brut - its["its"]

    return {
        "type_rupture": type_rupture,
        "salaire_mois_prorata": salaire_mois,
        "indemnite_conges": ind_conges,
        "indemnite_preavis": round(preavis_indemnite),
        "indemnite_rupture": ind_rupture,
        "total_brut": round(total_brut),
        "its_estime": its["its"],
        "abattement_rupture": its["abattement_applique"],
        "net_estime": round(net_estime),
        "detail_fiscal": its,
        "source": "Prorata (RG-PRORATA-001) · congés (Art.165) · licenciement (CCGT Art.36) · "
                  "fin CDD (Loi 2017-05 Art.13) · retraite (CCGT Art.57) · décès (CCGT Art.37) · "
                  "fiscalité (CGI Art.126). ⚠️ Contresignature juriste social requise.",
    }


if __name__ == "__main__":
    r = solde_tout_compte(
        type_rupture="licenciement",
        salaire_mensuel=200000, salaire_moyen_12m=200000,
        anciennete_ans=8, jours_travailles_dernier_mois=20,
        jours_conges_acquis_non_pris=10, salaires_12m_pour_conges=2_400_000,
        preavis_indemnite=200000)
    print("── Solde de tout compte (licenciement, 8 ans) ──")
    for k, v in r.items():
        if k != "detail_fiscal":
            print(f"  {k:22} = {v}")
