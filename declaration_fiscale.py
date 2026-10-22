"""
Générateur de la déclaration fiscale mensuelle ITS + VPS — Bénin (DGI).
Source : CGI Art. 129 (ITS, échéance le 10 du mois suivant), Art. 195 (VPS, même
déclaration, base = base ITS). Déclaration unique sur e-services.impots.bj.

Produit un récapitulatif par salarié + agrégats, avec contrôle de cohérence,
et un export CSV (séparateur ';') vers le gabarit e-services.
⚠️ Gabarit exact des colonnes e-services à récupérer sur la plateforme (réserve).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date

from moteur_paie import Salarie, Rubrique, calcul_bulletin

MOIS_FR = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]


@dataclass
class LigneITS:
    matricule: str
    nom: str
    brut: int
    base_its: int
    its: int
    base_vps: int
    vps: int


def declaration_its_vps(
    salaries: list[tuple[Salarie, list[Rubrique], str, str]],
    periode: date,
) -> dict:
    """Construit la déclaration ITS/VPS à partir des bulletins.
    `salaries` = liste de (Salarie, rubriques, matricule, nom).
    Échéance = le 10 du mois suivant (CGI Art. 129)."""
    lignes: list[LigneITS] = []
    for sal, rubriques, matricule, nom in salaries:
        b = calcul_bulletin(sal, rubriques, periode)
        # base VPS = base ITS (CGI Art.193) : valeur unique fournie par le moteur (R11),
        # plus de recalcul independant susceptible de diverger.
        base_vps = b["base_vps"]
        lignes.append(LigneITS(matricule, nom, b["brut"], b["base_its"],
                               b["its"], base_vps, b["vps"]))

    tot_brut = sum(l.brut for l in lignes)
    tot_its = sum(l.its for l in lignes)
    tot_vps = sum(l.vps for l in lignes)

    # échéance = le 10 du mois suivant
    mois_suiv = periode.month % 12 + 1
    annee_suiv = periode.year + (1 if periode.month == 12 else 0)
    echeance = date(annee_suiv, mois_suiv, 10)

    return {
        "periode": f"{MOIS_FR[periode.month]} {periode.year}",
        "echeance": echeance,
        "nb_salaries": len(lignes),
        "total_brut": tot_brut,
        "total_its": tot_its,
        "total_vps": tot_vps,
        "total_a_reverser": tot_its + tot_vps,
        "lignes": lignes,
        "source": "CGI Art. 129 (ITS, le 10) + Art. 195 (VPS) — déclaration unique e-services",
    }


def export_csv(decl: dict, chemin: str) -> str:
    """Export CSV (séparateur ';') du récapitulatif ITS/VPS."""
    import csv
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["# Déclaration ITS/VPS", decl["periode"],
                    "Échéance", decl["echeance"].strftime("%d/%m/%Y")])
        w.writerow(["Matricule", "Nom", "Brut", "Base ITS", "ITS",
                    "Base VPS", "VPS"])
        for l in decl["lignes"]:
            w.writerow([l.matricule, l.nom, l.brut, l.base_its, l.its,
                        l.base_vps, l.vps])
        w.writerow(["", "TOTAL", decl["total_brut"], "", decl["total_its"],
                    "", decl["total_vps"]])
        w.writerow(["", "À REVERSER DGI (ITS+VPS)", "", "", "", "",
                    decl["total_a_reverser"]])
    return chemin


if __name__ == "__main__":
    sals = [
        (Salarie("A", at_mp=0.02), [Rubrique("Base", 150000),
                                    Rubrique("Transport", 15000, soumis_cnss=False)],
         "M001", "DOSSOU Awa"),
        (Salarie("B", categorie="cadre", at_mp=0.03), [Rubrique("Base", 600000)],
         "M002", "AGBODJAN Koffi"),
    ]
    decl = declaration_its_vps(sals, date(2026, 1, 1))
    print(f"Déclaration ITS/VPS — {decl['periode']}")
    print(f"Échéance DGI : {decl['echeance']:%d/%m/%Y}")
    print(f"{'Matricule':8} {'Nom':18} {'Brut':>10} {'ITS':>10} {'VPS':>8}")
    for l in decl["lignes"]:
        print(f"{l.matricule:8} {l.nom:18} {l.brut:>10,} {l.its:>10,} {l.vps:>8,}".replace(",", " "))
    print(f"{'':8} {'TOTAL':18} {decl['total_brut']:>10,} {decl['total_its']:>10,} {decl['total_vps']:>8,}".replace(",", " "))
    print(f"À reverser DGI : {decl['total_a_reverser']:,}".replace(",", " "))
    export_csv(decl, "declaration_its_vps_demo.csv")
    print("Export CSV : declaration_its_vps_demo.csv")
