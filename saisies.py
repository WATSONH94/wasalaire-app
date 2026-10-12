"""
Saisie-arrêt & cession sur salaire — Bénin.
Procédure : OHADA AUPSRVE révisé 2023 (workflow tiers saisi / conciliation / greffe).
Barème des quotités saisissables : national, Décret 55-972 (progressif par tranches).

⚠️⚠️ RÉSERVE FORTE : les SEUILS du barème datent de 1955 et n'ont pas de revalorisation
postérieure retrouvée. Ils sont fournis comme DÉFAUT EXPLICITEMENT « À CONFIRMER » et
NON codés en dur comme certains. Le barème est un paramètre `bareme_saisie` surchargeable.
Ne jamais importer un barème d'un autre pays (ex. Côte d'Ivoire — écarté).
"""
from __future__ import annotations
from dataclasses import dataclass, field

# Barème 55-972 (mensuel) — fractions par tranche. ⚠️ SEUILS 1955 « À CONFIRMER ».
# (plafond_mensuel de la tranche, fraction saisissable) ; None = au-delà.
BAREME_SAISIE_1955 = {
    "statut": "DEFAUT_A_CONFIRMER",  # seuils de 1955, non revalorisés — réserve forte
    "source": "Décret 55-972 (via Mede/FES 2006) — seuils 1955 non revalorisés",
    "tranches": [
        (12500,   1/20),
        (25000,   1/10),
        (37500,   1/5),
        (50000,   1/4),
        (62500,   1/3),
        (125000,  1/2),
        (None,    1/1),   # totalité sans limitation
    ],
}


def assiette_saisissable(salaire: float, accessoires: float = 0,
                         insaisissables: float = 0) -> float:
    """Assiette = salaire + accessoires − insaisissables (Code Art. 219).
    `insaisissables` regroupe : retenues à la source (impôts/cotisations),
    remboursements de frais, prestations sécu, allocations pour charge de famille."""
    return max(0.0, salaire + accessoires - insaisissables)


def quotite_saisissable(assiette: float, bareme: dict = BAREME_SAISIE_1955) -> dict:
    """Calcule la fraction saisissable par application PROGRESSIVE du barème.
    Retourne le montant saisissable, la part insaisissable (versée au salarié),
    et un AVERTISSEMENT si le barème est le défaut 1955 non confirmé."""
    saisissable, prev = 0.0, 0
    detail = []
    for plafond, fraction in bareme["tranches"]:
        hi = plafond if plafond is not None else float("inf")
        if assiette > prev:
            portion = min(assiette, hi) - prev
            part = portion * fraction
            saisissable += part
            detail.append({"tranche": f"{prev}-{plafond if plafond else '+'}",
                           "portion": round(portion), "fraction": round(fraction, 4),
                           "montant": round(part)})
            prev = hi
        else:
            break
    res = {
        "assiette": round(assiette),
        "saisissable": round(saisissable),
        "insaisissable": round(assiette - saisissable),
        "detail": detail,
        "source": bareme["source"],
    }
    if bareme.get("statut") == "DEFAUT_A_CONFIRMER":
        res["AVERTISSEMENT"] = ("Seuils de barème datant de 1955, non revalorisés — "
                                "À CONFIRMER auprès d'un praticien / du JO avant usage réel. "
                                "Ne pas figer comme certains.")
    return res


if __name__ == "__main__":
    print("── Assiette saisissable (salaire 200 000, ITS+CNSS 23 700 insaisissables) ──")
    a = assiette_saisissable(200000, accessoires=0, insaisissables=23700)
    print(f"  assiette = {a:,.0f}".replace(",", " "))
    print("\n── Quotité saisissable (barème 55-972, ⚠️ à confirmer) ──")
    r = quotite_saisissable(a)
    for k, v in r.items():
        if k != "detail":
            print(f"  {k:16} = {v}")
    print("  detail :")
    for d in r["detail"]:
        print(f"    {d}")
