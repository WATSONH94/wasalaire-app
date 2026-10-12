"""Tour de contrôle : RG-13M-001 (13e mois) & RG-AVANCE-001 (retenue avance)."""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from remunerations_speciales import treizieme_mois, retenue_avance
from saisies import quotite_saisissable

ok = 0
def check(label, got, exp):
    global ok
    c = got == exp; ok += 1 if c else 0
    print(f"  [{'PASS' if c else 'FAIL'}] {label} : {got} (attendu {exp})")

# RG-13M : 13e mois plein / prorata / taux partiel
check("13e mois plein (200k, 12m)", treizieme_mois(200000, 12)["montant"], 200000)
check("13e mois prorata (150k, 8m)", treizieme_mois(150000, 8)["montant"], 100000)
check("13e mois taux 0,5 (200k, 12m)", treizieme_mois(200000, 12, taux=0.5)["montant"], 100000)

# RG-AVANCE : plafonnée à la quotité cessible du net
plafond = quotite_saisissable(200000)["saisissable"]
r = retenue_avance(200000, 500000)                 # solde > plafond → retenue = plafond
check("avance plafonnée à la quotité", r["retenue_mois"], plafond)
check("avance : solde restant", r["solde_restant"], 500000 - plafond)
check("avance : avertissement seuils 1955 présent", "AVERTISSEMENT" in r, True)
r2 = retenue_avance(200000, 50000, quotite_max=100000)  # solde < plafond override → retenue = solde
check("avance < plafond → retenue = solde", r2["retenue_mois"], 50000)

print(f"\nRG 13e mois & avance : {ok}/7 PASS")
if ok != 7:
    raise SystemExit(1)
