#!/usr/bin/env python3
"""
Gardes R11 (assiette VPS = assiette ITS, CGI Art.193) et R12 (calcul monetaire
en Decimal de bout en bout, pas de derive float avant arrondi).

Lancer : python test_r11_r12.py   (exit 0 si tout est conforme)
"""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from datetime import date
from decimal import Decimal
from moteur_paie import Salarie, Rubrique, calcul_bulletin, arrondi_fcfa, mul_fcfa, bareme_its

res = []
def check(label, cond, detail=""):
    res.append(bool(cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))

per = date(2026, 1, 1)

# ---- R12 : arrondi half-up deterministe (pas d'arrondi bancaire) ----
check("arrondi_fcfa(0.5)=1 (half-up)", arrondi_fcfa(Decimal("0.5")) == 1)
check("arrondi_fcfa(1.5)=2 (half-up, pas banquier)", arrondi_fcfa(Decimal("1.5")) == 2)
check("arrondi_fcfa(2.5)=3 (half-up, pas banquier)", arrondi_fcfa(Decimal("2.5")) == 3)

# ---- R12 : le produit se fait en Decimal AVANT l'arrondi ----
# 375 x 0,036 = 13,5 exact -> 14. La voie float (0,036 non representable) donnait 13.
check("mul_fcfa(375, 0.036)=14 (Decimal exact, pas 13)", mul_fcfa(375, 0.036) == 14,
      detail=f"obtenu {mul_fcfa(375, 0.036)}")
check("mul_fcfa(1375, 0.036)=50 (13,5->14 ; 49,5->50)", mul_fcfa(1375, 0.036) == 50)

# ---- R12 : impact bout-en-bout dans le bulletin (CNSS sur assiette 375) ----
sal = Salarie("R12", at_mp=0.02)
b375 = calcul_bulletin(sal, [Rubrique("Base", 375)], per)
check("bulletin assiette 375 -> cnss_sal=14 (etait 13 en float)", b375["cnss_sal"] == 14,
      detail=f"cnss_sal={b375['cnss_sal']}")

# ---- R11 : une rubrique soumise ITS mais PAS VPS ne fait PAS diverger l'assiette ----
rub_div = [Rubrique("Salaire", 100000, soumis_cnss=True, soumis_its=True, soumis_vps=False)]
bdiv = calcul_bulletin(sal, rub_div, per)
check("base_vps == base_its malgre soumis_vps=False (Art.193)",
      bdiv["base_vps"] == bdiv["base_its"] == 100000,
      detail=f"base_its={bdiv['base_its']} base_vps={bdiv['base_vps']}")
check("vps calcule sur la base ITS (100000 x 4% = 4000)", bdiv["vps"] == 4000,
      detail=f"vps={bdiv['vps']}")

# ---- R11 : cas nominal (assiettes alignees) inchange ----
bok = calcul_bulletin(sal, [Rubrique("Salaire", 200000)], per)
check("cas nominal: base_vps == base_its == 200000", bok["base_vps"] == bok["base_its"] == 200000)

n_ok = sum(res); n = len(res)
print(f"\nGARDES R11/R12 : {n_ok}/{n} PASS")
sys.exit(0 if n_ok == n else 1)
