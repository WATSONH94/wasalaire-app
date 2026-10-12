"""
Test du RÉFÉRENTIEL RÉGLEMENTAIRE UNIQUE (P1-02).
- Le moteur Python (PARAMS + barème) est la SOURCE EXÉCUTABLE unique.
- La table SQL `rate_table` n'est qu'un MIROIR de référence : ce test vérifie
  qu'elle ne diverge pas du moteur (sinon une mise à jour SQL donnerait l'illusion
  d'un effet qu'elle n'a pas).
- `rule_set_signature` est déterministe et sert d'étiquette de version/hash du run.

Prérequis : cluster + migrations ; PG* en env. Base fraîche recommandée.
"""
from __future__ import annotations
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from datetime import date
import psycopg
from moteur_paie import PARAMS, rule_set_signature

res = []
def check(label, cond, detail=""):
    res.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))

def main():
    conn = psycopg.connect("", autocommit=True)
    # 1) Le miroir SQL ne doit jamais CONTREDIRE le moteur (source exécutable unique).
    #    Invariant : chaque entrée de rate_table correspond à un PARAMS (SQL ⊆ moteur).
    #    Le moteur peut porter des paramètres supplémentaires (le SQL reste une référence
    #    partielle), mais aucune valeur SQL ne doit diverger de la valeur exécutée.
    sql = {(c, float(v), d.isoformat())
           for c, v, d in conn.execute("SELECT code, valeur, date_effet FROM rate_table").fetchall()}
    py = {(n, float(v), de.isoformat()) for (n, v, de, _s) in PARAMS}
    divergences = sql - py
    check("rate_table (SQL) ne contredit pas le moteur (SQL ⊆ PARAMS)",
          not divergences, f"divergences={sorted(divergences)}")

    # 2) Signature déterministe et versionnée.
    s1 = rule_set_signature(date(2026, 1, 1))
    s2 = rule_set_signature(date(2026, 1, 1))
    check("rule_set_signature déterministe (même date -> même hash)", s1 == s2)
    check("rule_set_signature porte version + hash + date",
          s1["version"].startswith("2026.") and len(s1["hash"]) == 64)

    # 3) Une date différente peut produire une version différente (sélection par date).
    s3 = rule_set_signature(date(2023, 1, 1))  # avant certaines dates d'effet
    check("sélection par date de paie (jeu 2023 != jeu 2026)", s3["hash"] != s1["hash"])

    conn.close()
    ok = sum(res)
    print(f"\nRéférentiel unique (P1-02) : {ok}/{len(res)} PASS")
    if ok != len(res): raise SystemExit(1)

if __name__ == "__main__":
    main()
