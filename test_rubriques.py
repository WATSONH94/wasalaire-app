#!/usr/bin/env python3
"""Recette du CATALOGUE de rubriques (assiettes) — garantit qu'un utilisateur non expert
obtient une paie EXACTE. Les assiettes attendues proviennent des règles VALIDÉES
(13-BASE-REGLES-METIER/regles-metier.md). Toute dérive ici = bulletin faux => échec.

Lancer : python test_rubriques.py   (exit 0 si tout est conforme)
"""
from __future__ import annotations
import sys
from datetime import date
from moteur_paie import Salarie, Rubrique, calcul_bulletin
from payroll_service import STANDARD_RUBRIQUES

# Assiettes attendues par code : (soumis_cnss, soumis_its, soumis_vps, nature). Source légale.
ATTENDU = {
    "prime":               (True,  True,  True,  "gain"),            # rémunération
    "gratification":       (True,  True,  True,  "gain"),
    "avantage_nature":     (True,  True,  True,  "gain"),            # CGI Art.123
    "indemnite_transport": (False, True,  True,  "gain"),            # hors CNSS (Loi 98-019 Art.22) ; ITS (CGI Art.122)
    "heures_sup":          (True,  True,  True,  "gain"),            # RG-HS-001
    "prime_anciennete":    (True,  True,  True,  "gain"),            # RG-ANCIENNETE-001
    "absence":             (True,  True,  True,  "retenue_brut"),    # réduit le brut (ST-05)
    "avance":              (False, False, False, "retenue_net"),     # prélevée sur le net
}


def run() -> bool:
    ok = ko = 0
    print("=" * 68); print("RECETTE CATALOGUE RUBRIQUES — assiettes légales"); print("=" * 68)
    # 1. Chaque code du catalogue a les assiettes/nature attendues.
    for code, (lib, c, i, v, nat) in STANDARD_RUBRIQUES.items():
        att = ATTENDU.get(code)
        if att is None:
            print(f"  [NOUVEAU] {code} absent de la recette — à valider"); ko += 1; continue
        got = (c, i, v, nat)
        if got == att:
            print(f"  [OK]    {code:20} cnss={c} its={i} vps={v} {nat}"); ok += 1
        else:
            print(f"  [ERREUR] {code}: attendu {att}, obtenu {got}"); ko += 1
    # 2. Tout code attendu est présent (pas de rubrique validée disparue).
    for code in ATTENDU:
        if code not in STANDARD_RUBRIQUES:
            print(f"  [MANQUANT] {code} retiré du catalogue !"); ko += 1

    # 3. Preuve sur un bulletin : transport (hors CNSS) ne gonfle PAS l'assiette CNSS.
    per = date(2026, 1, 1); sal = Salarie("Démo", at_mp=0.02)
    rub = [Rubrique("Salaire de base", 250000),
           Rubrique("Indemnité de transport", 20000, False, True, True)]
    b = calcul_bulletin(sal, rub, per)
    cas = {"assiette_cnss": 250000.0, "base_its": 270000.0, "cnss_sal": 9000}
    ec = {k: (cas[k], b[k]) for k in cas if b[k] != cas[k]}
    if ec:
        print(f"  [ERREUR] bulletin transport: {ec}"); ko += 1
    else:
        print("  [OK]    bulletin: salaire 250000 + transport 20000 -> CNSS sur 250000, ITS sur 270000"); ok += 1

    print("=" * 68); print(f"RÉSULTAT : {ok} OK / {ko} erreur(s)"); print("=" * 68)
    return ko == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
