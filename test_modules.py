"""
Tests non-régression des modules de production (congés, maternité, rupture,
export CNSS, bulletin PDF). Chaque attendu est ancré sur un article.
Lancer : python test_modules.py
"""
from __future__ import annotations
import os
from datetime import date

from conges_maternite import (droit_conges_annuels, allocation_conge,
                              conge_maternite, indemnite_licenciement,
                              indemnite_depart_retraite)
from export_cnss import LigneSalarie, generer_liste_nominative, controle_coherence
from bulletin import Employeur, InfosSalarie, generer_bulletin_pdf
from comptabilite import ecriture_paie, provision_conges, provision_ifc
from declaration_fiscale import declaration_its_vps
from remunerations_speciales import (heures_supplementaires, prorata,
                                     its_remuneration_exceptionnelle)
from saisies import assiette_saisissable, quotite_saisissable
from solde_tout_compte import solde_tout_compte
from moteur_paie import Salarie, Rubrique

ok = ecart = 0


def check(nom, obtenu, attendu):
    global ok, ecart
    if obtenu == attendu:
        print(f"  [OK]    {nom} = {obtenu}")
        ok += 1
    else:
        print(f"  [ECART] {nom} : obtenu {obtenu} != attendu {attendu}")
        ecart += 1


print("== Congés (Art. 158) ==")
# 12 mois, 22 ans ancienneté → 24 + 2 = 26 j
check("conges_22ans", droit_conges_annuels(12, anciennete_ans=22)["jours_acquis"], 26)
# 12 mois, 31 ans → 24 + 6 = 30 (plafond)
check("conges_31ans", droit_conges_annuels(12, anciennete_ans=31)["jours_acquis"], 30)
# mère > 21 ans, 5 enfants → 24 + 2×(5-3) = 28
check("conges_mere_5enf",
      droit_conges_annuels(12, sexe="F", age=30, enfants_a_charge=5)["jours_acquis"], 28)

print("== Allocation congé (Art. 165) ==")
# 2 400 000 sur 12 mois, 24 j pris sur 24 → 200 000
check("alloc_conge_24j", allocation_conge(2_400_000, jours_pris=24)["montant"], 200000)
# avec 120 000 d'exclusions (primes rendement) → (2 280 000)/12 = 190 000
check("alloc_conge_exclu",
      allocation_conge(2_400_000, exclusions_12m=120_000, jours_pris=24)["montant"], 190000)

print("== Maternité (Art. 170) ==")
m = conge_maternite(150_000)
check("maternite_semaines", m["semaines"], 14)
# CNSS rembourse 50 % → part employeur = total - remb
check("maternite_charge_emp",
      m["a_la_charge_employeur_net"], m["salaire_maintenu_100pct"] - m["remboursement_cnss_50pct"])

print("== Licenciement (CCGT 2005 Art. 36) ==")
# 8 ans, salaire 200 000 → 5×0,30 + 3×0,35 = 300 000 + 210 000 = 510 000
check("licenciement_8ans", indemnite_licenciement(200_000, 8)["montant"], 510000)
# 12 ans → 5×0,30 + 5×0,35 + 2×0,40 = 300 000 + 350 000 + 160 000 = 810 000
check("licenciement_12ans", indemnite_licenciement(200_000, 12)["montant"], 810000)

print("== Départ retraite (CCGT 2005 Art. 57, min 3 mois) ==")
# 8 ans : max(510 000 ; 3×200 000=600 000) = 600 000
check("retraite_min3mois", indemnite_depart_retraite(200_000, 8)["montant"], 600000)

print("== Export CNSS (contrôle de cohérence) ==")
lignes = [
    LigneSalarie("BJ-001", "A", "a", salaire_brut=184990, jours_ou_heures=26),
    LigneSalarie("BJ-002", "B", "b", salaire_brut=250000, jours_ou_heures=26),
]
check("cnss_masse", controle_coherence(lignes)["masse_salariale"], 434990)
res_cnss = generer_liste_nominative(lignes, "EMP-1", 9, 2026,
                                    "_test_cnss.xlsx")
check("cnss_nb", res_cnss["nb_travailleurs"], 2)
check("cnss_fichier_existe", os.path.exists(res_cnss["fichier"]), True)

print("== Bulletin PDF (3 assiettes) ==")
emp = Employeur("TEST SARL")
infos = InfosSalarie("Test")
sal = Salarie("Test", categorie="cadre", at_mp=0.02)
rub = [Rubrique("Base", 150000),
       Rubrique("Transport", 15000, soumis_cnss=False)]
rb = generer_bulletin_pdf(emp, infos, sal, rub, date(2026, 1, 1), "_test_bulletin.pdf")
check("bulletin_brut", rb["brut"], 165000)
check("bulletin_assiette_cnss", rb["assiette_cnss"], 150000)   # transport exclu
check("bulletin_base_its", rb["base_its"], 165000)             # transport inclus
check("bulletin_fichier_existe", os.path.exists(rb["fichier"]), True)

print("== Comptabilité SYSCOHADA (dossier 09, équilibre débit=crédit) ==")
ecr = ecriture_paie(Salarie("T", at_mp=0.02), [Rubrique("Base", 200000)], date(2026, 1, 1))
check("compta_3_ecritures", len(ecr), 3)
check("compta_toutes_equilibrees", all(e.equilibree for e in ecr), True)
# (a) reproduit l'exemple du dossier : brut 200 000 au débit du 6611
check("compta_a_debit", ecr[0].total_debit, 200000)
check("compta_a_net_422", next(l.credit for l in ecr[0].lignes if l.compte == "422"), 176300)
# (b) charges patronales : total 42 800 (34 800 + 8 000)
check("compta_b_debit", ecr[1].total_debit, 42800)

print("== Déclaration fiscale ITS/VPS (CGI Art. 129/195) ==")
sals = [
    (Salarie("A", at_mp=0.02), [Rubrique("Base", 150000),
                                Rubrique("Transport", 15000, soumis_cnss=False)], "M1", "A"),
    (Salarie("B", categorie="cadre", at_mp=0.03), [Rubrique("Base", 600000)], "M2", "B"),
]
decl = declaration_its_vps(sals, date(2026, 1, 1))
check("decl_its_total", decl["total_its"], 112750)      # 11 250 + 101 500
check("decl_vps_total", decl["total_vps"], 30600)       # 6 600 + 24 000
check("decl_a_reverser", decl["total_a_reverser"], 143350)
check("decl_echeance_le10", decl["echeance"], date(2026, 2, 10))  # le 10 du mois suivant

print("== Provision congés (clôture, dossier 09 §4) ==")
pc = provision_conges(200000, date(2026, 12, 31))
check("prov_equilibree", pc.equilibree, True)
check("prov_dotation", pc.total_debit, 236800)          # 200 000 + 36 800 charges

print("== Heures supplémentaires (Art. 147) ==")
# th=1000, 8h@12% + 2h@35% = 8960 + 2700 = 11660 (= ST-04)
hs = heures_supplementaires(173330, {"jour_41_48": 8, "jour_au_dela_48": 2})
check("hs_total_ST04", hs["total"], 11660)
# nuit dimanche/férié = +100%
hs2 = heures_supplementaires(173330, {"nuit_dim_ferie": 1})
check("hs_nuit_dim_100pct", hs2["total"], 2000)

print("== Prorata entrée/sortie ==")
check("prorata_15j_trentiemes", prorata(200000, 15)["montant"], 100000)

print("== ITS rémunération exceptionnelle (Art. 126) ==")
# impot_moyen(200000)=16500 ; IFC 500000×0,75=375000 ; base 575000 ; 16500×575000/200000
rex = its_remuneration_exceptionnelle(200000, 200000, 500000, "ifc")
check("art126_impot_moyen", rex["impot_moyen"], 16500)
check("art126_abattement", rex["abattement_applique"], 0.25)
check("art126_its", rex["its"], 47438)
# sans abattement (13e mois) : base = 200000+300000=500000 → 16500×500000/200000=41250
rex2 = its_remuneration_exceptionnelle(200000, 200000, 300000, "13e_mois")
check("art126_sans_abattement", rex2["its"], 41250)

print("== Saisies sur salaire (barème 55-972, ⚠️ à confirmer) ==")
ass = assiette_saisissable(200000, insaisissables=23700)
check("saisie_assiette", ass, 176300)
q = quotite_saisissable(ass)
check("saisie_avertissement_present", "AVERTISSEMENT" in q, True)  # réserve seuils 1955
check("saisie_somme_coherente", q["saisissable"] + q["insaisissable"], round(ass))

print("== Provision IFC (unités de crédit projetées, hypothèses = paramètres) ==")
ifc = provision_ifc(indemnite_retraite_projetee=1_000_000,
                    anciennete_actuelle_ans=10, anciennete_a_la_retraite_ans=20,
                    taux_actualisation=0.05, proba_presence=0.8,
                    annees_avant_retraite=10, periode=date(2026, 12, 31))
check("ifc_ecriture_equilibree", ifc["ecriture"].equilibree, True)
check("ifc_droits_50pct", ifc["droits_acquis_pct"], 50.0)  # 10/20

print("== Solde de tout compte (intégration workflow 3) ==")
stc = solde_tout_compte(
    type_rupture="licenciement", salaire_mensuel=200000, salaire_moyen_12m=200000,
    anciennete_ans=8, jours_travailles_dernier_mois=20,
    jours_conges_acquis_non_pris=10, salaires_12m_pour_conges=2_400_000,
    preavis_indemnite=200000)
check("stc_prorata", stc["salaire_mois_prorata"], 133333)
check("stc_conges", stc["indemnite_conges"], 83333)
check("stc_rupture", stc["indemnite_rupture"], 510000)
check("stc_total_brut", stc["total_brut"], 926666)
check("stc_its_art126", stc["its_estime"], 65931)
check("stc_net", stc["net_estime"], 860735)
# démission : pas d'indemnité de licenciement
stc_dem = solde_tout_compte("demission", 200000, 200000, 8, 30, 0, 2_400_000)
check("stc_demission_sans_rupture", stc_dem["indemnite_rupture"], 0)

# Nettoyage des fichiers de test
for f in ("_test_cnss.xlsx", "_test_bulletin.pdf"):
    if os.path.exists(f):
        os.remove(f)

print(f"\n=== RÉSULTAT : {ok} OK / {ecart} écart ===")
raise SystemExit(1 if ecart else 0)
