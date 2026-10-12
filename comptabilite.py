"""
Générateur d'écritures comptables de paie — SYSCOHADA révisé (AUDCIF 2017).
Transforme la sortie du moteur (calcul_bulletin) en écriture de journal équilibrée.
Comptes vérifiés sur le plan comptable officiel SYSCOHADA (dossier 09).

Garantit l'équilibre débit = crédit de chaque écriture (contrôle intégré).
Sous-comptes = défauts OHADA ; mapping paramétrable par entreprise en production.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date

from moteur_paie import Salarie, Rubrique, calcul_bulletin


# Comptes SYSCOHADA (défauts — dossier 09)
CPT = {
    "brut_national":      "6611",  # Appointements, salaires (national)
    "brut_expatrie":      "6621",  # Appointements, salaires (non national)
    "charges_soc_nat":    "6641",  # Charges sociales / personnel national
    "charges_soc_exp":    "6642",  # Charges sociales / non national
    "vps_charge":         "641",   # Impôts et taxes directs (VPS charge)
    "cnss_pf":            "4311",  # Sécurité sociale — prestations familiales
    "cnss_retraite":      "4313",  # Sécurité sociale — retraite obligatoire
    "cnss_atmp":          "4318",  # Sécurité sociale — autres cotisations (AT/MP)
    "amo":                "4332",  # Organismes sociaux (AMO — à caler, cf. dossier 04)
    "its_a_reverser":     "4472",  # État, impôts sur salaires (ITS)
    "vps_a_reverser":     "4421",  # État, autres impôts et taxes d'État (VPS)
    "net_a_payer":        "422",   # Personnel, rémunérations dues
    "banque":             "521",   # Banques
}


@dataclass
class LigneEcriture:
    compte: str
    libelle: str
    debit: float = 0
    credit: float = 0


@dataclass
class Ecriture:
    journal: str
    date: date
    libelle: str
    lignes: list[LigneEcriture] = field(default_factory=list)

    @property
    def total_debit(self) -> int:
        return round(sum(l.debit for l in self.lignes))

    @property
    def total_credit(self) -> int:
        return round(sum(l.credit for l in self.lignes))

    @property
    def equilibree(self) -> bool:
        return self.total_debit == self.total_credit

    def __str__(self) -> str:
        out = [f"{self.journal} — {self.date:%d/%m/%Y} — {self.libelle}"]
        for l in self.lignes:
            d = f"{l.debit:>12,.0f}".replace(",", " ") if l.debit else " " * 12
            c = f"{l.credit:>12,.0f}".replace(",", " ") if l.credit else " " * 12
            out.append(f"  {l.compte:6} {l.libelle:44} {d} {c}")
        eq = "✓ équilibrée" if self.equilibree else "✗ DÉSÉQUILIBRE"
        out.append(f"  {'':6} {'TOTAUX':44} "
                   f"{self.total_debit:>12,.0f}".replace(",", " ")
                   + f" {self.total_credit:>12,.0f}".replace(",", " ") + f"   [{eq}]")
        return "\n".join(out)


def ecriture_paie(sal: Salarie, rubriques: list[Rubrique], periode: date,
                  expatrie: bool = False,
                  saisies: float = 0, avances: float = 0) -> list[Ecriture]:
    """Produit les 3 écritures de paie du mois : (a) brut+retenues,
    (b) charges patronales, (c) paiement du net. Chaque écriture est équilibrée."""
    b = calcul_bulletin(sal, rubriques, periode)
    cpt_brut = CPT["brut_expatrie"] if expatrie else CPT["brut_national"]
    cpt_cs = CPT["charges_soc_exp"] if expatrie else CPT["charges_soc_nat"]
    net = b["net"] - saisies - avances

    # (a) Salaire brut et retenues salariales
    a = Ecriture("OD-PAIE", periode, "Salaires bruts et retenues salariales")
    a.lignes.append(LigneEcriture(cpt_brut, "Salaire brut", debit=b["brut"]))
    a.lignes.append(LigneEcriture(CPT["cnss_retraite"], "CNSS pension part salariale (3,6%)",
                                  credit=b["cnss_sal"]))
    a.lignes.append(LigneEcriture(CPT["its_a_reverser"], "ITS retenu (+ ORTB)", credit=b["its"]))
    if b["amo_sal"]:
        a.lignes.append(LigneEcriture(CPT["amo"], "AMO part salariale", credit=b["amo_sal"]))
    if saisies:
        a.lignes.append(LigneEcriture("4232", "Saisies-arrêts", credit=saisies))
    if avances:
        a.lignes.append(LigneEcriture("4211", "Récupération avances/acomptes", credit=avances))
    a.lignes.append(LigneEcriture(CPT["net_a_payer"], "Net à payer", credit=net))

    # (b) Charges patronales
    bb = Ecriture("OD-PAIE", periode, "Charges patronales (CNSS employeur + VPS)")
    # décomposition CNSS patronale
    from moteur_paie import param
    pf = round(b["assiette_cnss"] * param("taux_pf", periode))
    pension_emp = round(b["assiette_cnss"] * param("taux_pension_emp", periode))
    atmp = b["cnss_pat"] - pf - pension_emp
    bb.lignes.append(LigneEcriture(cpt_cs, "Charges sociales patronales", debit=b["cnss_pat"]))
    bb.lignes.append(LigneEcriture(CPT["vps_charge"], "VPS (charge)", debit=b["vps"]))
    if b["amo_pat"]:
        bb.lignes.append(LigneEcriture(cpt_cs, "AMO part employeur", debit=b["amo_pat"]))
    bb.lignes.append(LigneEcriture(CPT["cnss_pf"], "CNSS prestations familiales (9%)", credit=pf))
    bb.lignes.append(LigneEcriture(CPT["cnss_retraite"], "CNSS pension employeur (6,4%)",
                                   credit=pension_emp))
    bb.lignes.append(LigneEcriture(CPT["cnss_atmp"], "CNSS AT/MP", credit=atmp))
    bb.lignes.append(LigneEcriture(CPT["vps_a_reverser"], "VPS à reverser", credit=b["vps"]))
    if b["amo_pat"]:
        bb.lignes.append(LigneEcriture(CPT["amo"], "AMO à reverser (part emp.)", credit=b["amo_pat"]))

    # (c) Paiement du net
    c = Ecriture("BANQUE", periode, "Paiement des salaires")
    c.lignes.append(LigneEcriture(CPT["net_a_payer"], "Net à payer", debit=net))
    c.lignes.append(LigneEcriture(CPT["banque"], "Banque", credit=net))

    return [a, bb, c]


def provision_conges(allocation_estimee: float, periode: date,
                     taux_charges_patronales: float = 0.184) -> Ecriture:
    """Écriture de provision pour congés à payer (clôture) — dossier 09 §4.
    DÉBIT 6611 (dotation) / CRÉDIT 4281 (dette provisionnée congés)
    DÉBIT 6641 (charges sociales congés) / CRÉDIT 4382 (organismes sociaux congés).
    `taux_charges_patronales` par défaut = PF 9% + pension 6,4% + AT/MP moyen ~3%.
    """
    charges = round(allocation_estimee * taux_charges_patronales)
    e = Ecriture("OD-CLOTURE", periode, "Provision pour congés à payer (Art. 165)")
    e.lignes.append(LigneEcriture(CPT["brut_national"], "Dotation congés à payer",
                                  debit=round(allocation_estimee)))
    e.lignes.append(LigneEcriture("4281", "Dettes provisionnées congés à payer",
                                  credit=round(allocation_estimee)))
    e.lignes.append(LigneEcriture(CPT["charges_soc_nat"], "Charges sociales sur congés",
                                  debit=charges))
    e.lignes.append(LigneEcriture("4382", "Organismes sociaux, charges sur congés",
                                  credit=charges))
    return e


def provision_ifc(
    indemnite_retraite_projetee: float,
    anciennete_actuelle_ans: float,
    anciennete_a_la_retraite_ans: float,
    taux_actualisation: float,
    proba_presence: float,
    annees_avant_retraite: float,
    periode: date | None = None,
) -> dict:
    """Provision pour indemnité de fin de carrière (IFC) — SYSCOHADA Ch.21, compte 196.
    Méthode des unités de crédit projetées (simplifiée) :
      VAO = indemnité projetée × (ancienneté actuelle / ancienneté à la retraite)
            × proba_présence × facteur_actualisation.

    ⚠️ Les HYPOTHÈSES (taux d'actualisation, probabilité de présence, table) sont une
    DÉCISION DE POLITIQUE de l'entreprise, PAS une règle légale : elles sont des
    PARAMÈTRES, jamais inventées. L'obligation (montant retraite) vient de la CCGT Art. 57.
    """
    if anciennete_a_la_retraite_ans <= 0:
        raise ValueError("ancienneté à la retraite doit être > 0")
    droits_acquis = anciennete_actuelle_ans / anciennete_a_la_retraite_ans
    facteur_actualisation = 1 / ((1 + taux_actualisation) ** annees_avant_retraite)
    vao = (indemnite_retraite_projetee * droits_acquis
           * proba_presence * facteur_actualisation)
    e = Ecriture("OD-CLOTURE", periode or date.today(),
                 "Provision IFC (engagement de retraite, unités de crédit projetées)")
    e.lignes.append(LigneEcriture("6911", "Dotation aux provisions pour risques (IFC)",
                                  debit=round(vao)))
    e.lignes.append(LigneEcriture("196", "Provisions pour pensions et obligations similaires",
                                  credit=round(vao)))
    return {
        "valeur_actuelle_obligation": round(vao),
        "droits_acquis_pct": round(droits_acquis * 100, 1),
        "facteur_actualisation": round(facteur_actualisation, 4),
        "ecriture": e,
        "source": "SYSCOHADA Ch.21 (compte 196) ; obligation CCGT Art. 57. "
                  "Hypothèses = politique entreprise (paramètres, à valider actuaire).",
    }


def export_fec_csv(ecritures: list[Ecriture], chemin: str) -> str:
    """Export CSV (type journal comptable) importable dans un logiciel tiers."""
    import csv
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Journal", "Date", "Compte", "Libellé", "Débit", "Crédit"])
        for e in ecritures:
            for l in e.lignes:
                w.writerow([e.journal, e.date.strftime("%d/%m/%Y"), l.compte,
                            l.libelle, round(l.debit) or "", round(l.credit) or ""])
    return chemin


if __name__ == "__main__":
    sal = Salarie("Démo", at_mp=0.02)
    rub = [Rubrique("Salaire de base", 200000)]
    ecritures = ecriture_paie(sal, rub, date(2026, 1, 1))
    for e in ecritures:
        print(e)
        print()
    print("── Provision congés (clôture) ──")
    pc = provision_conges(200000, date(2026, 12, 31))
    print(pc)
    print()
    ecritures.append(pc)
    toutes_equilibrees = all(e.equilibree for e in ecritures)
    print(f"Toutes les écritures équilibrées : {toutes_equilibrees}")
    export_fec_csv(ecritures, "journal_paie_demo.csv")
    print("Export CSV : journal_paie_demo.csv")
