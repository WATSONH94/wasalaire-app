#!/usr/bin/env python3
"""
Gardes R15 / R16 : modele AMO (Decret 2025-672 + CGI Art.124).

R15 (Art.10) : part du souscripteur AU MOINS 80 % -> un parametrage sous 80 %
               est releve au plancher legal, jamais applique tel quel.
R16 (Art.124) : prime d'un contrat COLLECTIF employeur = hors base ITS ;
               contrat INDIVIDUEL exonere jusqu'a 80 %, part employeur au-dela
               de 80 % = avantage imposable ajoute a la base ITS.
Beneficiaires (Art.8) : au plus 4 enfants pris en compte dans la prime ANPS.

Lancer : python test_r15_r16_amo.py   (exit 0 si tout est conforme)
"""
from __future__ import annotations
import os, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from datetime import date
os.environ["WASALAIRE_AMO_DATE_EFFET"] = "2026-10-29"   # AMO active pour ces tests
from moteur_paie import Salarie, Rubrique, calcul_bulletin, Reglement, prime_amo_mensuelle_anps

PER = date(2026, 11, 1)   # >= 2026-10-29 : part_souscripteur_amo (0,80) resolue

res = []
def check(label, cond, detail=""):
    res.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))

class PartFixe(Reglement):
    """Reglement de test : force la part du souscripteur (sinon delegue au defaut)."""
    def __init__(self, part): self._part = part
    def taux(self, nom, d):
        if nom == "part_souscripteur_amo": return self._part
        return super().taux(nom, d)

salaire = [Rubrique("Salaire", 200000)]

# 1. Collectif, part 80 % : repartition 80/20, AUCUN avantage ITS.
b = calcul_bulletin(Salarie("C", prime_amo_mensuelle=10000, amo_contrat="collectif"), salaire, PER)
check("collectif 80% : amo_pat=8000 / amo_sal=2000", b["amo_pat"] == 8000 and b["amo_sal"] == 2000,
      detail=f"pat={b['amo_pat']} sal={b['amo_sal']}")
check("collectif : aucun avantage ITS, base_its=200000", b["amo_avantage_its"] == 0 and b["base_its"] == 200000,
      detail=f"avantage={b['amo_avantage_its']} base_its={b['base_its']}")

# 2. Individuel, part 80 % : exonere jusqu'a 80 % -> AUCUN avantage ITS.
b = calcul_bulletin(Salarie("I80", prime_amo_mensuelle=10000, amo_contrat="individuel"), salaire, PER)
check("individuel 80% : aucun avantage ITS", b["amo_avantage_its"] == 0 and b["base_its"] == 200000)

# 3. Individuel, part 100 % (employeur paie tout) : excedent au-dela de 80 % = avantage imposable.
b = calcul_bulletin(Salarie("I100", prime_amo_mensuelle=10000, amo_contrat="individuel"), salaire, PER,
                    reglement=PartFixe(1.00))
check("individuel 100% : avantage ITS = 2000 (20% de 10000)", b["amo_avantage_its"] == 2000,
      detail=f"avantage={b['amo_avantage_its']}")
check("individuel 100% : base ITS = 200000 + 2000", b["base_its"] == 202000, detail=f"base_its={b['base_its']}")
check("individuel 100% : amo_pat=10000 / amo_sal=0", b["amo_pat"] == 10000 and b["amo_sal"] == 0)

# 4. Collectif, part 100 % : employeur paie tout MAIS contrat collectif -> hors base ITS.
b = calcul_bulletin(Salarie("C100", prime_amo_mensuelle=10000, amo_contrat="collectif"), salaire, PER,
                    reglement=PartFixe(1.00))
check("collectif 100% : aucun avantage ITS (Art.124)", b["amo_avantage_its"] == 0 and b["base_its"] == 200000)

# 5. R15 : un parametrage SOUS 80 % est releve au plancher legal 80 %.
b = calcul_bulletin(Salarie("Bas", prime_amo_mensuelle=10000, amo_contrat="collectif"), salaire, PER,
                    reglement=PartFixe(0.70))
check("part 70% configuree -> clamp a 80% : amo_pat=8000 / amo_sal=2000",
      b["amo_pat"] == 8000 and b["amo_sal"] == 2000, detail=f"pat={b['amo_pat']} sal={b['amo_sal']}")

# 6. Beneficiaires (Art.8) : enfants plafonnes a 4 dans la prime ANPS de reference.
p4  = prime_amo_mensuelle_anps(nb_adultes=1, nb_enfants=4, periode=PER)
p10 = prime_amo_mensuelle_anps(nb_adultes=1, nb_enfants=10, periode=PER)
check("prime ANPS : enfants plafonnes a 4 (p(10 enfants) == p(4 enfants))", p10 == p4, detail=f"p4={p4} p10={p10}")

# 7. AMO inactive hors periode d'effet : aucune retenue (non-regression P0-05).
b = calcul_bulletin(Salarie("Avant", prime_amo_mensuelle=10000, amo_contrat="individuel"), salaire, date(2026, 9, 1))
check("AMO inactive avant date d'effet : amo=0 et base_its inchangee",
      b["amo_sal"] == 0 and b["amo_pat"] == 0 and b["amo_avantage_its"] == 0 and b["base_its"] == 200000)

n_ok = sum(res); n = len(res)
print(f"\nGARDES R15/R16 (modele AMO) : {n_ok}/{n} PASS")
sys.exit(0 if n_ok == n else 1)
