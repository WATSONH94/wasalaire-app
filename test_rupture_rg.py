"""Tours de contrôle des RG rupture nouvellement codées :
RG-MALADIE-001 (CCGT Art.19), RG-DECES-001 (CCGT Art.37), RG-CDD-001 (Loi 2017-05 Art.13).
Valeurs attendues calculées à la main (croisement)."""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from conges_maternite import maintien_maladie, capital_deces, indemnite_licenciement
from solde_tout_compte import solde_tout_compte

ok = 0
def check(label, got, exp):
    global ok
    cond = got == exp
    ok += 1 if cond else 0
    print(f"  [{'PASS' if cond else 'FAIL'}] {label} : {got} (attendu {exp})")

# ── RG-MALADIE-001 (CCGT Art.19) ──
# 3 ans (12m-5ans) → plein 3 + demi 3 ; absence 4 mois = 3×200000 + 0,5×200000 = 700 000
check("maladie 3 ans, 4 mois", maintien_maladie(200000, 3, 4)["montant_maintenu"], 700000)
# 7 ans (>5) → plein 6 ; absence 8 mois = 6×200000 = 1 200 000 (mois 7-8 non payés)
check("maladie 7 ans, 8 mois", maintien_maladie(200000, 7, 8)["montant_maintenu"], 1200000)
# <12 mois → plein = préavis (1 mois) ; absence 2 mois = 1×200000
check("maladie <1 an, 2 mois", maintien_maladie(200000, 0.5, 2, preavis_mois=1)["montant_maintenu"], 200000)

# ── RG-DECES-001 (CCGT Art.37) ──
# licenciement(200k,8) = 30%×5 + 35%×3 = (1,5+1,05)×200000 = 510 000
check("indemnité licenciement 8 ans", indemnite_licenciement(200000, 8)["montant"], 510000)
# capital décès = 510 000 + 1 mois base × 8 ans (200000×8=1 600 000) = 2 110 000
cd = capital_deces(200000, 200000, 8)
check("capital décès (part ancienneté)", cd["part_anciennete_1mois_par_an"], 1600000)
check("capital décès (total)", cd["montant"], 2110000)

# solde de tout compte type décès → indemnite_rupture = capital décès
s_dec = solde_tout_compte("deces", 200000, 200000, 8, 30, 0, 2400000, 0)
check("solde décès → indemnité rupture", s_dec["indemnite_rupture"], 2110000)

# ── RG-CDD-001 (Loi 2017-05 Art.13) : fin CDD = licenciement ──
# anciennete 3 ans → 30%×3 = 180 000
s_cdd = solde_tout_compte("fin_cdd", 200000, 200000, 3, 30, 0, 2400000, 0)
s_lic = solde_tout_compte("licenciement", 200000, 200000, 3, 30, 0, 2400000, 0)
check("fin CDD → indemnité rupture", s_cdd["indemnite_rupture"], 180000)
check("fin CDD == licenciement (même barème)", s_cdd["indemnite_rupture"], s_lic["indemnite_rupture"])

print(f"\nRG rupture (maladie/décès/fin CDD) : {ok}/9 PASS")
if ok != 9:
    raise SystemExit(1)
