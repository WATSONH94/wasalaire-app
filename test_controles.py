"""Tests du moteur d'anomalies (RG-CTRL-001)."""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from datetime import date
from moteur_paie import Salarie, Rubrique, calcul_bulletin
from controles import (controler_bulletin, controler_declaration,
                       controler_equilibre_compta, bloquants)

P = date(2026, 1, 1)
ok = 0
def check(label, cond):
    global ok
    ok += 1 if cond else 0
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

# Bulletin sain (base 200 000) → aucune anomalie
b = calcul_bulletin(Salarie("A"), [Rubrique("Base", 200000)], P)
check("bulletin sain → 0 anomalie", controler_bulletin(b, 200000, P) == [])

# SMIG non atteint (base 40 000 < 52 000) → bloquant CTRL-SMIG
b2 = calcul_bulletin(Salarie("B"), [Rubrique("Base", 40000)], P)
a2 = controler_bulletin(b2, 40000, P)
check("SMIG non atteint → bloquant", any(x["code"] == "CTRL-SMIG" for x in bloquants(a2)))

# Net négatif (grosse retenue) → bloquant CTRL-NET-NEG
b3 = calcul_bulletin(Salarie("C"), [Rubrique("Base", 100000),
                                    Rubrique("Retenue", -500000, False, False, False)], P)
check("net négatif → bloquant", any(x["code"] == "CTRL-NET-NEG" for x in controler_bulletin(b3, 100000, P)))

# Écart > 30 % vs M-1 → avertissement
a4 = controler_bulletin(b, 200000, P, brut_m1=100000)  # +100 %
check("écart vs M-1 → avertissement", any(x["code"] == "CTRL-ECART-M1" and x["gravite"] == "avertissement" for x in a4))

# Σ individuels ≠ total → bloquant
check("Σ ≠ total → bloquant", controler_declaration(101500, 100000) != [])
check("Σ = total → OK", controler_declaration(101500, 101500) == [])

# Équilibre compta
check("débit ≠ crédit → bloquant", controler_equilibre_compta(1000, 900) != [])
check("débit = crédit → OK", controler_equilibre_compta(1000, 1000) == [])

print(f"\nControles (RG-CTRL-001) : {ok}/8 PASS")
if ok != 8:
    raise SystemExit(1)
