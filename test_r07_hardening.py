#!/usr/bin/env python3
"""
Garde R07 : durcissement authentification / secrets.

Verifie le comportement FAIL-CLOSED au demarrage (le plus critique, cite par
l'audit) sans base de donnees : l'import du module API est tente dans un
sous-processus avec un environnement controle.

  - PROD (DEV=0) + secret faible/absent  -> demarrage REFUSE (RuntimeError).
  - PROD (DEV=0) + secret fort            -> demarrage OK, pas d'avertissement DEV.
  - DEMO (DEV=1)                          -> demarrage OK + avertissement explicite
                                             (le mode demo n'est jamais silencieux).

Les protections OTP (anti-rejeu, verrouillage a 5 tentatives, rate-limit a 3
demandes, anti-enumeration, OTP hache) sont couvertes par test_accounts (16/16)
et test_security (8/8) sur base.

Lancer : python test_r07_hardening.py   (exit 0 si tout est conforme)
"""
from __future__ import annotations
import os, sys, subprocess

res = []
def check(label, cond, detail=""):
    res.append(bool(cond))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))

def try_import(dev: str, secret):
    """Importe api_v2 dans un sous-processus avec un env minimal controle.
    Retourne (returncode, stderr)."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("WASALAIRE_") and k not in ("PGDATABASE",)}
    env["PYTHONUTF8"] = "1"; env["PYTHONIOENCODING"] = "utf-8"
    env["WASALAIRE_DEV"] = dev
    if secret is not None:
        env["WASALAIRE_SECRET"] = secret
    p = subprocess.run([sys.executable, "-c", "import api_v2"],
                       cwd=os.path.dirname(os.path.abspath(__file__)),
                       env=env, capture_output=True, text=True)
    return p.returncode, (p.stderr or "")

# A. PROD + secret faible connu -> refus
rc, err = try_import("0", "dev-secret-change-me")
check("PROD + secret faible -> demarrage refuse", rc != 0 and ("refus" in err.lower() or "RuntimeError" in err),
      detail=f"rc={rc}")

# B. PROD + secret absent -> refus
rc, err = try_import("0", None)
check("PROD + secret absent -> demarrage refuse", rc != 0, detail=f"rc={rc}")

# C. PROD + secret trop court -> refus
rc, err = try_import("0", "court")
check("PROD + secret < 16 car. -> demarrage refuse", rc != 0, detail=f"rc={rc}")

# D. PROD + secret fort -> OK, sans avertissement DEV
rc, err = try_import("0", "un_secret_de_production_tres_long_et_aleatoire_000")
check("PROD + secret fort -> demarrage OK", rc == 0, detail=f"rc={rc}")
check("PROD : pas d'avertissement mode demo", "AVERTISSEMENT" not in err)

# E. DEMO (DEV=1) -> OK + avertissement explicite (jamais silencieux)
rc, err = try_import("1", "dev-secret-change-me")
check("DEMO (DEV=1) -> demarrage OK", rc == 0, detail=f"rc={rc}")
check("DEMO : avertissement explicite present", "AVERTISSEMENT" in err)

n_ok = sum(res); n = len(res)
print(f"\nGARDE R07 (fail-closed + mode demo explicite) : {n_ok}/{n} PASS")
sys.exit(0 if n_ok == n else 1)
