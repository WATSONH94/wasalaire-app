"""
Tests de recette — exécute les scénarios ST-xx (dossier 22) sur le moteur
et vérifie les résultats attendus (validation de la base réglementaire).
Lancer : python test_scenarios.py
"""
import os
from datetime import date
# L'AMO n'est plus codée en dur (P0-05) : pour exercer le chemin AMO, le test
# simule l'instrument officiel approuvé en fixant la date d'effet (test uniquement).
os.environ.setdefault("WASALAIRE_AMO_DATE_EFFET", "2026-10-29")
from moteur_paie import Salarie, Rubrique, calcul_bulletin

JANV_2026 = date(2026, 1, 1)
JUIN_2026 = date(2026, 6, 1)
SEPT_2026 = date(2026, 9, 1)
NOV_2026  = date(2026, 11, 1)

# (id, salarié, rubriques, période, attendus {champ: valeur})
CAS = [
    ("ST-01 SMIG",
     Salarie("A", at_mp=0.02),
     [Rubrique("Base", 52000)], JANV_2026,
     {"cnss_sal": 1872, "its": 0, "net": 50128, "cout_employeur": 63128}),

    ("ST-02 Salaire élevé",
     Salarie("B", at_mp=0.02),
     [Rubrique("Base", 1000000)], JANV_2026,
     {"cnss_sal": 36000, "its": 221500, "net": 742500, "cout_employeur": 1214000}),

    ("ST-03 Primes + transport (3 assiettes)",
     Salarie("C", at_mp=0.02),
     [Rubrique("Base", 150000),
      Rubrique("Prime rendement", 30000),
      Rubrique("Indemnité transport", 20000, soumis_cnss=False)],  # transport hors CNSS
     JANV_2026,
     {"assiette_cnss": 180000, "base_its": 200000,
      "cnss_sal": 6480, "its": 16500, "net": 177020, "cout_employeur": 239320}),

    ("ST-04 Heures supplémentaires (8h@12% + 2h@35%)",
     Salarie("D", at_mp=0.02),
     [Rubrique("Base", 173330),
      Rubrique("HS 41-48e (8h @+12%)", 8960),
      Rubrique("HS >48e (2h @+35%)", 2700)], JANV_2026,
     {"brut": 184990, "cnss_sal": 6660, "its": 14249, "net": 164081}),  # base ITS 184990 -> 14248,5 arrondi half-up = 14249

    ("ST-05 Absence non rémunérée (brut payé après retenue)",
     Salarie("I", at_mp=0.02),
     [Rubrique("Brut payé (200000 − 3/22 j)", 172727)], JANV_2026,
     {"cnss_sal": 6218, "its": 12409, "net": 154100}),

    ("ST-13 Avantages en nature (logement + véhicule)",
     Salarie("J", categorie="cadre", at_mp=0.02),
     [Rubrique("Base", 400000),
      Rubrique("Logement (15% base)", 60000),
      Rubrique("Véhicule 4 roues (forfait)", 30000)], JANV_2026,
     {"assiette_cnss": 490000, "base_its": 490000,
      "cnss_sal": 17640, "its": 69600, "net": 402760}),

    ("ST-17 Versioning — septembre 2026 (AVANT AMO, pas de retenue)",
     Salarie("K", at_mp=0.02, prime_amo_mensuelle=(16000*2 + 9000*2)/12),
     [Rubrique("Base", 200000)], SEPT_2026,
     {"amo_sal": 0, "its": 16500, "net": 176300}),  # AMO non applicable avant 29/10/2026

    ("ST-14 Cadre 600 000",
     Salarie("E", categorie="cadre", at_mp=0.02),
     [Rubrique("Base", 600000)], JANV_2026,
     {"its": 101500, "cnss_sal": 21600, "net": 476900}),

    ("ST-15 Non-cadre 90 000",
     Salarie("F", at_mp=0.02),
     [Rubrique("Base", 90000)], JANV_2026,
     {"its": 3000, "cnss_sal": 3240, "net": 83760}),

    ("ST-19 Redevance ORTB (juin)",
     Salarie("G", at_mp=0.02),
     [Rubrique("Base", 200000)], JUIN_2026,
     {"its": 19500, "net": 173300}),  # 16500 + 3000 ORTB

    ("ST-20 AMO (nov. 2026, famille 2 ad + 2 enf)",
     Salarie("H", at_mp=0.02, prime_amo_mensuelle=(16000*2 + 9000*2)/12),
     [Rubrique("Base", 200000)], NOV_2026,
     {"cnss_sal": 7200, "its": 16500, "amo_sal": 833, "net": 175467}),
]


def run():
    ok, ko = 0, 0
    print("=" * 68)
    print("RECETTE DU MOTEUR DE PAIE — scénarios ST-xx")
    print("=" * 68)
    for cid, sal, rub, per, attendus in CAS:
        res = calcul_bulletin(sal, rub, per)
        erreurs = {k: (attendus[k], res[k]) for k in attendus if res[k] != attendus[k]}
        statut = "[OK]" if not erreurs else "[ECART]"
        print(f"\n{cid:40} {statut}")
        print(f"   brut={res['brut']:>9,} | CNSS_sal={res['cnss_sal']:>7,} | "
              f"ITS={res['its']:>7,} | net={res['net']:>9,} | coût={res['cout_employeur']:>10,}"
              .replace(",", " "))
        if erreurs:
            for k, (att, got) in erreurs.items():
                print(f"   ⚠ {k}: attendu {att}, obtenu {got}")
            ko += 1
        else:
            ok += 1
    print("\n" + "=" * 68)
    print(f"RÉSULTAT : {ok} OK / {ko} écart(s) sur {len(CAS)} scénarios")
    print("=" * 68)
    return ko == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
