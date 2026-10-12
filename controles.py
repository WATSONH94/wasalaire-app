"""
Moteur de contrôles d'anomalies (RG-CTRL-001) — « anomalie = action ».
S'applique aux sorties de `moteur_paie.calcul_bulletin`. Ne calcule pas la paie ;
il vérifie la cohérence AVANT validation/clôture et renvoie une liste triée par
gravité, chaque anomalie portant sa règle et sa source (pour le lien UX direct).

Testé : `python test_controles.py`.
"""
from __future__ import annotations
from datetime import date
from moteur_paie import param

SEUIL_ECART_DEFAUT = 0.30  # écart de brut vs M-1 → avertissement (paramétrable)


def _a(gravite, code, message, regle, source, employe=None):
    return {"gravite": gravite, "code": code, "message": message,
            "regle": regle, "source": source, "employe": employe}


def controler_bulletin(b: dict, salaire_base_temps_plein: float, periode: date,
                       employe: str | None = None, brut_m1: float | None = None,
                       seuil_ecart: float = SEUIL_ECART_DEFAUT) -> list[dict]:
    """Contrôles sur un bulletin calculé. Retourne les anomalies (⛔ puis ⚠️)."""
    ano: list[dict] = []
    smig = param("smig", periode)

    # (a) SMIG — bloquant
    if salaire_base_temps_plein < smig:
        ano.append(_a("bloquant", "CTRL-SMIG",
                      f"Salaire de base ({salaire_base_temps_plein:,.0f}) < SMIG ({smig:,.0f}).".replace(",", " "),
                      "RG-SAL-001", "Décret 2022-692", employe))

    # (b) net négatif — bloquant
    if b.get("net", 0) < 0:
        ano.append(_a("bloquant", "CTRL-NET-NEG",
                      f"Net à payer négatif ({b['net']:,.0f}).".replace(",", " "),
                      "RG-CTRL-001", "cohérence paie", employe))

    # (c) cohérence des assiettes — bloquant
    brut = b.get("brut", 0)
    for cle, lib in (("assiette_cnss", "assiette CNSS"), ("base_its", "base ITS")):
        val = b.get(cle, 0)
        if val < 0:
            ano.append(_a("bloquant", "CTRL-ASSIETTE-NEG",
                          f"{lib} négative ({val:,.0f}).".replace(",", " "),
                          "RG-CTRL-001", "cohérence assiettes", employe))
        if val > brut:
            ano.append(_a("bloquant", "CTRL-ASSIETTE-SUP",
                          f"{lib} ({val:,.0f}) supérieure au brut ({brut:,.0f}).".replace(",", " "),
                          "RG-CTRL-001", "cohérence assiettes", employe))

    # (e) écart vs M-1 — avertissement
    if brut_m1 is not None and brut_m1 > 0:
        ecart = abs(brut - brut_m1) / brut_m1
        if ecart > seuil_ecart:
            ano.append(_a("avertissement", "CTRL-ECART-M1",
                          f"Brut en écart de {ecart*100:.0f} % vs le mois précédent.",
                          "RG-CTRL-001", "seuil paramétrable", employe))

    ano.sort(key=lambda x: 0 if x["gravite"] == "bloquant" else 1)
    return ano


def controler_declaration(somme_individuels: float, total_declare: float,
                          libelle: str = "déclaration") -> list[dict]:
    """(d) Σ des individuels doit égaler le total déclaré — bloquant."""
    if round(somme_individuels) != round(total_declare):
        return [_a("bloquant", "CTRL-SOMME",
                   f"{libelle} : Σ individuels ({somme_individuels:,.0f}) ≠ total ({total_declare:,.0f}).".replace(",", " "),
                   "RG-CTRL-001", "cohérence déclarative")]
    return []


def controler_equilibre_compta(total_debit: float, total_credit: float) -> list[dict]:
    """Écritures : débit = crédit — bloquant (SYSCOHADA)."""
    if round(total_debit, 2) != round(total_credit, 2):
        return [_a("bloquant", "CTRL-EQUILIBRE",
                   f"Écriture déséquilibrée : débit {total_debit:,.0f} ≠ crédit {total_credit:,.0f}.".replace(",", " "),
                   "RG-CTRL-001", "SYSCOHADA")]
    return []


def bloquants(anomalies: list[dict]) -> list[dict]:
    return [a for a in anomalies if a["gravite"] == "bloquant"]
