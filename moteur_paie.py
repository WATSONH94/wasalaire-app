"""
Moteur de paie Bénin — PROTOTYPE paramétrable.
Règles = données versionnées (date d'effet). Aucune règle codée en dur.
Fondé sur la base réglementaire vérifiée (dossiers 02-13).

⚠️ Prototype pédagogique : à faire contresigner (DGI/CNSS/expert) avant production.
Points ouverts (paramétrables) : montant prime AMO, seuils saisie 1955,
forfait transport côté CNSS.
"""
from __future__ import annotations
import os, json, hashlib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


# ─────────────────────────────────────────────────────────────
# 0) POLITIQUE D'ARRONDI (P1-05) : franc CFA entier, arrondi au plus proche,
#    0,5 arrondi vers le haut (déterministe, documenté, versionné ci-dessous).
#    Remplace round() (arrondi bancaire implicite) à toutes les frontières.
# ─────────────────────────────────────────────────────────────
POLITIQUE_ARRONDI = "FCFA entier, half-up (0,5 -> sup.)"

def arrondi_fcfa(x) -> int:
    """Arrondit un montant au franc CFA entier, 0,5 vers le haut."""
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

# ─────────────────────────────────────────────────────────────
# 1) PARAMÈTRES RÉGLEMENTAIRES VERSIONNÉS (règles en données)
# ─────────────────────────────────────────────────────────────
PARAMS = [
    # (nom, valeur, date_effet, source)
    ("smig",               52000,  date(2023, 1, 1), "Décret 2022-692"),
    ("taux_pension_sal",   0.036,  date(2024, 1, 1), "CNSS off. / Loi 98-019 Art.24-25"),
    ("taux_pension_emp",   0.064,  date(2024, 1, 1), "CNSS off."),
    ("taux_pf",            0.09,   date(2024, 1, 1), "CNSS off."),
    ("taux_vps",           0.04,   date(2024, 1, 1), "CGI Art.194"),
    ("taux_vps_enseignement", 0.02, date(2024, 1, 1), "CGI Art.194 (enseignement privé)"),
    ("part_souscripteur_amo", 0.80, date(2026, 10, 29), "Décret 2025-672 Art.10"),
    # AMO — tarif ANPS de référence (NON CERTIFIÉ : arrêté Art.17 non publié), versionné et daté.
    ("amo_anps_adulte",   16000,  date(2026, 10, 29), "ANPS (non certifié, QA-01)"),
    ("amo_anps_enfant",    9000,  date(2026, 10, 29), "ANPS (non certifié, QA-01)"),
    # Redevance ORTB versionnée (EC-02) : miroir en code des lignes rate_table 006.
    ("ortb_mois_3",        1000,  date(2025, 1, 1), "CGI Art.125 §2 (ORTB mars)"),
    ("ortb_mois_6",        3000,  date(2025, 1, 1), "CGI Art.125 §2 (ORTB juin)"),
]

# Barème ITS progressif (CGI Art.125) — versionné
BAREME_ITS = {
    "date_effet": date(2025, 1, 1), "source": "CGI 2026 Art.125 (barème inchangé depuis 2025)",
    "tranches": [  # (plafond de tranche, taux) ; None = infini
        (60000,  0.00),
        (150000, 0.10),
        (250000, 0.15),
        (500000, 0.19),
        (None,   0.30),
    ],
}

# Redevance ORTB (CGI Art.125 §2)
ORTB = {3: 1000, 6: 3000}  # mois -> montant ; exonération du 3000 si base <= 1re tranche

# ── AMO : prime de référence du panier de base (ANPS) ────────────
# Tarif NON codé en dur : versionné dans PARAMS (amo_anps_adulte / amo_anps_enfant,
# Décret 2025-672 Art.17 — non certifié, QA-01). La fonction de calcul lit le
# fournisseur de paramètres (Reglement/ReglementDB) : voir prime_amo_mensuelle_anps()
# définie plus bas, après _REGLEMENT_DEFAUT.


def param(nom: str, d: date):
    """Sélectionne la version d'un paramètre en vigueur à la date d."""
    candidats = [(de, v) for (n, v, de, _) in PARAMS if n == nom and de <= d]
    if not candidats:
        raise ValueError(f"Paramètre {nom} non défini à {d}")
    return max(candidats)[1]


# ── AMO : DATE D'EFFET NON FIGÉE (P0-05) ─────────────────────────
# Le Décret 2025-672 (Art.23) fixe l'exigibilité à 12 mois APRÈS publication au
# Journal officiel ; cette date de publication n'est PAS établie (champ JO vide sur
# textes.justice.bj au 01/10/2026). On NE code donc AUCUNE date par défaut : l'AMO
# reste INACTIVE tant qu'un responsable habilité n'a pas renseigné la date d'effet
# (instrument officiel en main), via WASALAIRE_AMO_DATE_EFFET=YYYY-MM-DD.
def amo_date_effet() -> date | None:
    v = os.environ.get("WASALAIRE_AMO_DATE_EFFET", "").strip()
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None

def amo_active(periode: date) -> bool:
    d = amo_date_effet()
    return d is not None and periode >= d


def rule_set_signature(periode: date) -> dict:
    """Jeu de règles EXÉCUTABLE unique, identifié et hashé pour une date de paie.
    Permet à chaque run de répondre : quel rule set, quelle version, quelle date
    d'effet, quel hash (reproductibilité légale, P1-02)."""
    bundle = {
        "params": sorted(
            [(n, v, de.isoformat()) for (n, v, de, _s) in PARAMS if de <= periode]),
        "bareme_its": {"date_effet": BAREME_ITS["date_effet"].isoformat(),
                       "tranches": BAREME_ITS["tranches"]},
        "ortb": ORTB,
        "arrondi": POLITIQUE_ARRONDI,
        "amo_date_effet": amo_date_effet().isoformat() if amo_date_effet() else None,
    }
    payload = json.dumps(bundle, sort_keys=True, default=str)
    h = hashlib.sha256(payload.encode()).hexdigest()
    annee = periode.year
    return {"rule_set": "benin-paie", "version": f"{annee}.{h[:8]}",
            "date_paie": periode.isoformat(), "hash": h}


# ─────────────────────────────────────────────────────────────
# 1bis) FOURNISSEUR DE PARAMÈTRES (EC-01) — source unique injectable
#   Reglement         : lit le registre EN CODE (défaut, rétro-compatible, hors ligne).
#   ReglementDB(conn) : lit la BASE versionnée (rate_table/tax_bracket) = source de
#                       vérité en production ; repli sur le code pour un code absent.
#   Le moteur ne « connaît » plus de valeur en dur : il interroge le fournisseur.
# ─────────────────────────────────────────────────────────────
class Reglement:
    """Fournisseur par défaut : registre en code (PARAMS / BAREME_ITS / ORTB)."""
    def taux(self, nom: str, d: date):
        return param(nom, d)

    def bareme_its_tranches(self, d: date):
        return BAREME_ITS["tranches"]

    def ortb(self, d: date) -> dict:
        return ORTB


class ReglementDB(Reglement):
    """Lit les paramètres datés dans la base (source unique de vérité, D3/INV-03/05).
    `conn` = connexion psycopg ouverte (RLS/SET ROLE gérés par l'appelant).
    Repli sur le registre en code si un code n'est pas (encore) présent en base
    (ex. taux_vps_enseignement, amo_anps_*)."""
    def __init__(self, conn):
        self.conn = conn

    def taux(self, nom: str, d: date):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT valeur FROM rate_table WHERE code=%s AND date_effet<=%s "
                "ORDER BY date_effet DESC LIMIT 1", (nom, d))
            row = cur.fetchone()
        return param(nom, d) if row is None else float(row[0])

    def bareme_its_tranches(self, d: date):
        with self.conn.cursor() as cur:
            cur.execute("SELECT max(date_effet) FROM tax_bracket "
                        "WHERE table_code='ITS' AND date_effet<=%s", (d,))
            (de,) = cur.fetchone()
            if de is None:
                return BAREME_ITS["tranches"]
            cur.execute(
                "SELECT tranche_max, taux FROM tax_bracket "
                "WHERE table_code='ITS' AND date_effet=%s ORDER BY tranche_min", (de,))
            rows = cur.fetchall()
        return [(None if tmax is None else float(tmax), float(taux)) for (tmax, taux) in rows]

    def ortb(self, d: date) -> dict:
        # ORTB versionné en base (EC-02) : codes rate_table `ortb_mois_3` / `ortb_mois_6`.
        # Repli sur le registre code si la table n'est pas (encore) amorcée.
        out: dict[int, int] = {}
        with self.conn.cursor() as cur:
            for mois, code in ((3, "ortb_mois_3"), (6, "ortb_mois_6")):
                cur.execute(
                    "SELECT valeur FROM rate_table WHERE code=%s AND date_effet<=%s "
                    "ORDER BY date_effet DESC LIMIT 1", (code, d))
                row = cur.fetchone()
                if row is not None:
                    out[mois] = int(row[0])
        return out or ORTB


_REGLEMENT_DEFAUT = Reglement()


def prime_amo_mensuelle_anps(nb_adultes: int = 1, nb_enfants: int = 0,
                             periode: date | None = None,
                             reglement: "Reglement | None" = None) -> int:
    """Prime AMO mensuelle de RÉFÉRENCE (tarif ANPS) = (prime annuelle) / 12.
    Tarif lu dans le registre versionné via le fournisseur (EC-01) : `amo_anps_adulte`
    et `amo_anps_enfant` (NON certifiés, QA-01 ; arrêté Art.17 non publié).
    ⚠️ Périodicité de retenue exacte = arrêté Finances (Décret Art.20), non publié :
    le mensuel (annuel÷12) est le défaut technique (cohérent avec le réf. ~1340/mois).
    nb_enfants plafonné à 4 (Décret Art.8). Un assureur privé peut fixer une autre
    prime (Art.18) → passer directement `Salarie.prime_amo_mensuelle`."""
    rg = reglement or _REGLEMENT_DEFAUT
    d = periode or date.today()

    def tarif(nom):
        # Tarif de référence : si pas encore « en vigueur » à d (effet futur),
        # on retombe sur la version de référence la plus ancienne (code).
        try:
            return rg.taux(nom, d)
        except ValueError:
            versions = [(de, v) for (n, v, de, _s) in PARAMS if n == nom]
            if not versions:
                raise
            return min(versions)[1]

    nb_enfants = min(max(nb_enfants, 0), 4)
    annuel = nb_adultes * tarif("amo_anps_adulte") + nb_enfants * tarif("amo_anps_enfant")
    return arrondi_fcfa(annuel / 12)


# ─────────────────────────────────────────────────────────────
# 2) MODÈLE
# ─────────────────────────────────────────────────────────────
@dataclass
class Rubrique:
    """Élément de paie. Les 3 assiettes sont indépendantes (cf. dossier 06)."""
    libelle: str
    montant: float
    soumis_cnss: bool = True
    soumis_its: bool = True
    soumis_vps: bool = True  # VPS = base ITS (Art.193)


@dataclass
class Salarie:
    nom: str
    categorie: str = "employe"      # employe | cadre | ouvrier_horaire
    at_mp: float = 0.02             # taux AT/MP notifié par la CNSS (1-4%)
    regime_vps: str = "normal"      # normal | enseignement
    prime_amo_mensuelle: float = 0.0  # part prime AMO (par contrat/assureur)
    its_base_deduit_cnss: bool = False  # FALSE = conforme CGI (base brute)


# ─────────────────────────────────────────────────────────────
# 3) MOTEUR
# ─────────────────────────────────────────────────────────────
def bareme_its(base: float, tranches=None) -> int:
    """ITS progressif par tranches (CGI Art.125).
    `tranches` : liste (plafond, taux) ; défaut = barème en code (rétro-compatible)."""
    if tranches is None:
        tranches = BAREME_ITS["tranches"]
    taxe, prev = 0.0, 0
    for plafond, taux in tranches:
        hi = plafond if plafond is not None else float("inf")
        if base > prev:
            taxe += (min(base, hi) - prev) * taux
            prev = hi
        else:
            break
    return arrondi_fcfa(taxe)


def calcul_bulletin(sal: Salarie, rubriques: list[Rubrique], periode: date,
                    reglement: "Reglement | None" = None) -> dict:
    """Calcule un bulletin. `reglement` = fournisseur de paramètres (EC-01) :
    None → registre en code (défaut, rétro-compatible) ; ReglementDB → lit la base
    versionnée (rate_table/tax_bracket) = source unique en production."""
    rg = reglement or _REGLEMENT_DEFAUT
    brut = sum(r.montant for r in rubriques)
    assiette_cnss = sum(r.montant for r in rubriques if r.soumis_cnss)
    brut_imposable = sum(r.montant for r in rubriques if r.soumis_its)
    base_vps = sum(r.montant for r in rubriques if r.soumis_vps)

    # CNSS salarié (3,6 %, pas de plafond)
    cnss_sal = arrondi_fcfa(assiette_cnss * rg.taux("taux_pension_sal", periode))

    # Base ITS : brute (conforme CGI) ou Brut-CNSS (pratique désactivée par défaut)
    base_its = brut_imposable - (cnss_sal if sal.its_base_deduit_cnss else 0)
    tranches = rg.bareme_its_tranches(periode)
    its = bareme_its(base_its, tranches)
    # Redevance ORTB (perçue AVEC l'ITS certains mois). On la cumule dans `its`
    # (totaux/déclarations inchangés) MAIS on l'expose séparément (`ortb`) pour la
    # transparence du bulletin : le non-expert voit pourquoi l'ITS varie selon le mois.
    montant_ortb = 0
    ortb = rg.ortb(periode)
    if periode.month in ortb:
        montant_ortb = ortb[periode.month]
        if periode.month == 6 and base_its <= tranches[0][0]:
            montant_ortb = 0  # exonération du 3000 si <= 1re tranche
        its += montant_ortb

    # AMO : appliquée UNIQUEMENT si la date d'effet est officiellement renseignée
    # (amo_active) et qu'une prime est connue. Par défaut inactive (P0-05).
    amo_sal = amo_pat = 0
    if amo_active(periode) and sal.prime_amo_mensuelle > 0:
        part = rg.taux("part_souscripteur_amo", periode)
        amo_pat = arrondi_fcfa(sal.prime_amo_mensuelle * part)
        amo_sal = arrondi_fcfa(sal.prime_amo_mensuelle * (1 - part))

    net = brut - cnss_sal - its - amo_sal

    # Charges patronales
    taux_vps = (rg.taux("taux_vps_enseignement", periode)
                if sal.regime_vps == "enseignement" else rg.taux("taux_vps", periode))
    cnss_pat = arrondi_fcfa(assiette_cnss * (rg.taux("taux_pf", periode)
                     + rg.taux("taux_pension_emp", periode) + sal.at_mp))
    vps = arrondi_fcfa(base_vps * taux_vps)
    cout_employeur = brut + cnss_pat + vps + amo_pat

    return {
        "brut": brut, "assiette_cnss": assiette_cnss, "base_its": base_its,
        "cnss_sal": cnss_sal, "its": its, "ortb": montant_ortb, "amo_sal": amo_sal,
        "net": net, "cnss_pat": cnss_pat, "vps": vps, "amo_pat": amo_pat,
        "cout_employeur": cout_employeur,
    }


def controle_smig(sal_base_temps_plein: float, periode: date) -> bool:
    return sal_base_temps_plein >= param("smig", periode)


if __name__ == "__main__":
    p = date(2026, 1, 1)
    s = Salarie("Démo", at_mp=0.02)
    r = [Rubrique("Salaire de base", 200000)]
    b = calcul_bulletin(s, r, p)
    print("Bulletin démo (brut 200 000) :")
    for k, v in b.items():
        print(f"  {k:15} = {v:>10,}".replace(",", " "))
