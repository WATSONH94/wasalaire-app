"""
Service de persistance du cycle de paie — câble le MOTEUR TESTÉ sur PostgreSQL.
Ferme l'item ouvert « câbler API↔BD » : le calcul provient de `moteur_paie`
(58/58 tests, aucune règle réimplémentée) ; ce module ne fait que lire les
intrants en base, appeler le moteur, et persister bulletins + lignes + snapshot.

Schéma cible : `16/schema.sql` + `16/schema-v2-deltas.sql` (scope-RLS validée).
La connexion passée en argument doit avoir son périmètre posé (`set_scope`) :
l'isolation multi-tenant est assurée par la BD (RLS), pas par ce code.

Cycle exposé (tranche verticale) :
    open_period → calculate_run → validate_and_close   (+ lecture scope-isolée)
"""
from __future__ import annotations
import os, json, hashlib
from datetime import date

from moteur_paie import (
    Salarie, Rubrique, calcul_bulletin, PARAMS, BAREME_ITS, ORTB,
    prime_amo_mensuelle_anps, rule_set_signature, ReglementDB, arrondi_fcfa,
)
from controles import controler_bulletin, bloquants
from audit import audit

VERSION_MOTEUR = "prototype-0.1 (58/58)"
REGLE_ARRONDI = "round() FCFA entier (dossier 06)"


# ─────────────── Périmètre (scope-RLS) ───────────────
def set_scope(conn, company_ids: list[str]) -> None:
    """Pose app.authorized_companies pour la session → la RLS filtre tout accès."""
    arr = "{" + ",".join(str(c) for c in company_ids) + "}"
    conn.execute("SELECT set_config('app.authorized_companies', %s, false)", (arr,))


# ─────────────── Étapes du cycle ───────────────
class WorkflowError(Exception):
    """Transition de cycle de paie interdite (machine d'états)."""


# Colonnes de politique autorisées (anti-injection : jamais d'entrée utilisateur ici).
_POLICY_CHAMPS = {"four_eyes_calcul_validation", "four_eyes_validation_paiement"}

def four_eyes_policy(conn, company_id: str, champ: str) -> bool:
    """Politique de séparation des tâches CHOISIE PAR L'ABONNÉ (workspace), via son
    administrateur (table `governance_policy`). Défaut = DÉSACTIVÉ (cible TPE
    mono-opérateur) tant que l'admin ne l'a pas explicitement activé."""
    if champ not in _POLICY_CHAMPS:
        raise ValueError(f"Champ de politique inconnu : {champ}")
    row = conn.execute(
        f"SELECT gp.{champ} FROM company c "
        "LEFT JOIN governance_policy gp ON gp.workspace_id = c.workspace_id "
        "WHERE c.id = %s", (company_id,)).fetchone()
    return False if (row is None or row[0] is None) else bool(row[0])


def open_period(conn, company_id: str, mois: int, annee: int, actor: str | None = None) -> str:
    """Ouvre (ou récupère) une période. NE réouvre JAMAIS une période clôturée (P0-01).
    Idempotent pour une période déjà ouverte/calculée : renvoie son identifiant sans
    rétrograder son statut."""
    row = conn.execute(
        "SELECT id, statut FROM payroll_period WHERE company_id=%s AND annee=%s AND mois=%s",
        (company_id, annee, mois),
    ).fetchone()
    if row:
        pid, statut = row
        if statut == "cloturee":
            raise WorkflowError(
                f"Période {mois:02d}/{annee} clôturée : réouverture interdite (rectificatif requis).")
        return pid
    pid = conn.execute(
        "INSERT INTO payroll_period(company_id, mois, annee) VALUES (%s,%s,%s) RETURNING id",
        (company_id, mois, annee),
    ).fetchone()[0]
    audit(conn, "period.open", "payroll_period", company_id, actor,
          apres={"period_id": str(pid), "mois": mois, "annee": annee})
    return pid


# ─────────────────────────────────────────────────────────────
# CATALOGUE STANDARD DE RUBRIQUES — assiettes issues des règles VALIDÉES
# (13-BASE-REGLES-METIER/regles-metier.md). Permet à un utilisateur NON EXPERT
# d'obtenir une paie EXACTE : il choisit une rubrique, les bonnes assiettes
# CNSS/ITS/VPS sont appliquées automatiquement. Aucune règle inventée.
#   code : (libellé, soumis_cnss, soumis_its, soumis_vps, nature)
#   nature : 'gain' (ajouté au brut) | 'retenue_brut' (réduit le brut, ex. absence)
#            | 'retenue_net' (prélevée après net, ex. avance/acompte)
STANDARD_RUBRIQUES: dict[str, tuple[str, bool, bool, bool, str]] = {
    "prime":               ("Prime / gratification",       True,  True,  True,  "gain"),
    "gratification":       ("Gratification",               True,  True,  True,  "gain"),
    "avantage_nature":     ("Avantage en nature",          True,  True,  True,  "gain"),   # CGI Art.123
    "indemnite_transport": ("Indemnité de transport",      False, True,  True,  "gain"),   # hors CNSS (Loi 98-019 Art.22), soumis ITS (CGI Art.122)
    "heures_sup":          ("Heures supplémentaires",      True,  True,  True,  "gain"),   # montant calculé (RG-HS-001)
    "prime_anciennete":    ("Prime d'ancienneté",          True,  True,  True,  "gain"),   # conventionnel (RG-ANCIENNETE-001)
    "absence":             ("Absence non rémunérée",       True,  True,  True,  "retenue_brut"),  # réduit le brut (RG, ST-05)
    "avance":              ("Avance / acompte",            False, False, False, "retenue_net"),   # prélevée sur le net (RG-AVANCE)
}


def _rubriques_for(conn, company_id, employee_id, period_id) -> tuple[list[Rubrique], float]:
    """Construit les rubriques du salarié : salaire de base (contrat) + variables.
    Les assiettes proviennent (1) du paramétrage société `pay_element`, sinon (2) du
    catalogue standard validé STANDARD_RUBRIQUES, sinon (3) 3 assiettes par défaut.
    Retourne (rubriques_gains, total_retenues_net)."""
    base = conn.execute(
        "SELECT salaire_base FROM contract "
        "WHERE employee_id=%s AND statut='actif' ORDER BY date_debut DESC LIMIT 1",
        (employee_id,),
    ).fetchone()
    rub = [Rubrique("Salaire de base", float(base[0]))]
    retenue_net = 0.0
    for typ, montant in conn.execute(
        "SELECT type, montant FROM variable "
        "WHERE employee_id=%s AND period_id=%s AND montant IS NOT NULL",
        (employee_id, period_id),
    ).fetchall():
        m = float(montant)
        pe = conn.execute(
            "SELECT soumis_cnss, soumis_its, soumis_vps FROM pay_element "
            "WHERE company_id=%s AND code=%s", (company_id, typ),
        ).fetchone()
        if pe:
            rub.append(Rubrique(typ, m, bool(pe[0]), bool(pe[1]), bool(pe[2])))
        elif typ in STANDARD_RUBRIQUES:
            libelle, c, i, v, nature = STANDARD_RUBRIQUES[typ]
            if nature == "retenue_net":
                retenue_net += abs(m)
            elif nature == "retenue_brut":
                rub.append(Rubrique(libelle, -abs(m), c, i, v))   # réduit le brut et les assiettes
            else:
                rub.append(Rubrique(libelle, m, c, i, v))
        else:  # rubrique libre inconnue : soumise aux 3 assiettes par défaut (prudent)
            rub.append(Rubrique(typ, m))
    return rub, retenue_net


def calculate_run(conn, company_id: str, period_id: str, periode: date,
                  version_regles: str = "2026", actor: str | None = None) -> tuple[str, int]:
    """Calcule et persiste un bulletin par salarié actif. Retourne (run_id, n).
    Vérifie l'état de la période (ouverte/calculée), sa société, et supersède le
    run actif précédent (un seul run actif par période, N3)."""
    per = conn.execute(
        "SELECT statut, company_id FROM payroll_period WHERE id=%s", (period_id,)
    ).fetchone()
    if not per:
        raise WorkflowError("Période introuvable (ou hors périmètre).")
    if str(per[1]) != str(company_id):
        raise WorkflowError("Période et société incohérentes (P0-06).")
    if per[0] not in ("ouverte", "calculee"):
        raise WorkflowError(f"Calcul impossible : période au statut '{per[0]}'.")

    comp = conn.execute(
        "SELECT taux_atmp, regime_vps FROM company WHERE id=%s", (company_id,)
    ).fetchone()
    at_mp, regime_vps = float(comp[0]), comp[1]

    # Jeu de règles EXÉCUTABLE unique, identifié/hashé par date de paie (P1-02).
    sig = rule_set_signature(periode)
    version_regles = sig["version"]

    # EC-01 : le moteur lit les paramètres VERSIONNÉS EN BASE (rate_table/tax_bracket),
    # pas les constantes Python. Repli automatique sur le registre code pour un code
    # absent (ex. taux_vps_enseignement, amo_anps_*). La base devient la source de vérité.
    rg = ReglementDB(conn)

    # Un seul run actif par période : les précédents deviennent inactifs (superseded).
    conn.execute("UPDATE payroll_run SET actif=false WHERE period_id=%s AND actif", (period_id,))
    run_id = conn.execute(
        "INSERT INTO payroll_run(company_id, period_id, version_regles, calcule_par) "
        "VALUES (%s,%s,%s,%s) RETURNING id", (company_id, period_id, version_regles, actor),
    ).fetchone()[0]

    employees = conn.execute(
        "SELECT e.id, e.nom, COALESCE(p.categorie,'employe') "
        "FROM employee e JOIN contract c ON c.employee_id=e.id AND c.statut='actif' "
        "LEFT JOIN position p ON p.id=c.position_id "
        "WHERE e.company_id=%s AND e.deleted_at IS NULL", (company_id,),
    ).fetchall()

    n = 0
    for emp_id, nom, categorie in employees:
        rub, retenue_net = _rubriques_for(conn, company_id, emp_id, period_id)
        # Prime AMO de référence, calculée depuis les ayants droit à charge
        # (salarié + conjoint(s) = adultes ; enfants). N'est RETENUE que si l'AMO
        # est officiellement activée (date d'effet renseignée) - sinon amo=0.
        deps = dict(conn.execute(
            "SELECT type, count(*) FROM dependent WHERE employee_id=%s AND a_charge "
            "GROUP BY type", (emp_id,)).fetchall())
        prime_amo = prime_amo_mensuelle_anps(
            nb_adultes=1 + int(deps.get("conjoint", 0)),
            nb_enfants=int(deps.get("enfant", 0)))
        sal = Salarie(nom=nom, categorie=categorie, at_mp=at_mp, regime_vps=regime_vps,
                      prime_amo_mensuelle=prime_amo)
        b = calcul_bulletin(sal, rub, periode, reglement=rg)
        # Retenue nette (avance/acompte) : prélevée APRÈS le net fiscal/social.
        # Le net fiscal (b["net"], base des déclarations) est préservé ; seul le
        # NET À PAYER est réduit (RG-AVANCE, retenue hors assiettes).
        b["retenue_net"] = arrondi_fcfa(retenue_net)
        b["net_a_payer"] = b["net"] - b["retenue_net"]
        # Détail des lignes (transparence du bulletin : le non-expert vérifie sa paie).
        # L'ITS stocké inclut la redevance ORTB ; on les SÉPARE à l'affichage pour
        # que le non-expert comprenne la variation de l'ITS selon le mois (mars/juin).
        ortb = b.get("ortb", 0)
        its_pur = b["its"] - ortb
        b["lignes"] = {
            "gains": [{"libelle": r.libelle, "montant": r.montant} for r in rub],
            "retenues": (
                [{"libelle": "CNSS (part salariale, 3,6%)", "montant": b["cnss_sal"]},
                 {"libelle": "Impôt sur Traitements & Salaires (ITS)", "montant": its_pur}]
                + ([{"libelle": "Redevance ORTB", "montant": ortb}] if ortb else [])
                + ([{"libelle": "AMO (part salariale)", "montant": b["amo_sal"]}] if b["amo_sal"] else [])
                + ([{"libelle": "Avance / acompte", "montant": b["retenue_net"]}] if b["retenue_net"] else [])
            ),
        }

        payslip_id = conn.execute(
            "INSERT INTO payslip(company_id, run_id, employee_id, brut, base_cnss, "
            "base_its, total_retenues, net_a_payer, cout_employeur, resultat) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (company_id, run_id, emp_id, b["brut"], b["assiette_cnss"], b["base_its"],
             b["cnss_sal"] + b["its"] + b["amo_sal"] + b["retenue_net"], b["net_a_payer"],
             b["cout_employeur"], json.dumps(b)),
        ).fetchone()[0]

        for r in rub:  # lignes de gains
            conn.execute(
                "INSERT INTO payslip_line(company_id, payslip_id, base, montant, sens) "
                "VALUES (%s,%s,%s,%s,'gain')", (company_id, payslip_id, r.montant, r.montant))
        conn.execute(  # retenue CNSS
            "INSERT INTO payslip_line(company_id, payslip_id, base, taux, montant, sens) "
            "VALUES (%s,%s,%s,0.036,%s,'retenue')",
            (company_id, payslip_id, b["assiette_cnss"], b["cnss_sal"]))
        conn.execute(  # retenue ITS
            "INSERT INTO payslip_line(company_id, payslip_id, base, montant, sens) "
            "VALUES (%s,%s,%s,%s,'retenue')",
            (company_id, payslip_id, b["base_its"], b["its"]))

        # Snapshot de reproductibilité légale (intrants + règles figés + hash)
        entrees = {"nom": nom, "periode": periode.isoformat(), "at_mp": at_mp,
                   "regime_vps": regime_vps,
                   "rubriques": [r.__dict__ for r in rub]}
        bundle = {"PARAMS": [(nm, v, de.isoformat(), s) for (nm, v, de, s) in PARAMS],
                  "BAREME_ITS": {"date_effet": BAREME_ITS["date_effet"].isoformat(),
                                 "tranches": BAREME_ITS["tranches"]},
                  "ORTB": ORTB}
        payload = json.dumps({"e": entrees, "b": bundle, "r": b}, sort_keys=True, default=str)
        h = hashlib.sha256(payload.encode()).hexdigest()
        conn.execute(
            "INSERT INTO calc_snapshot(company_id, payslip_id, entrees_figees, "
            "bundle_regles, version_moteur, regle_arrondi, hash) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (company_id, payslip_id, json.dumps(entrees, default=str),
             json.dumps(bundle, default=str), VERSION_MOTEUR, REGLE_ARRONDI, h))
        n += 1
    conn.execute("UPDATE payroll_period SET statut='calculee' WHERE id=%s AND statut='ouverte'",
                 (period_id,))
    audit(conn, "run.calculate", "payroll_run", company_id, actor,
          apres={"run_id": str(run_id), "bulletins": n, "periode": periode.isoformat()})
    return run_id, n


def validate_and_close(conn, period_id: str, run_id: str, actor: str | None = None,
                       override_reason: str | None = None) -> None:
    """Valide puis clôture, sous garanties (P0-01, P0-02, P0-06) :
      - le run doit appartenir à la période ET à la même société, et être actif ;
      - la période doit être ouverte/calculée ;
      - les contrôles sont recalculés dans la transaction ; une anomalie bloquante
        empêche la clôture, sauf dérogation motivée (tracée en audit).
    """
    info = conn.execute(
        "SELECT r.company_id, r.period_id, r.actif, pp.company_id, pp.statut "
        "FROM payroll_run r JOIN payroll_period pp ON pp.id=%s WHERE r.id=%s",
        (period_id, run_id)).fetchone()
    if not info:
        raise WorkflowError("Run ou période introuvable (ou hors périmètre).")
    run_company, run_period, run_actif, per_company, per_statut = info
    if str(run_period) != str(period_id):
        raise WorkflowError("Le run n'appartient pas à cette période (P0-06).")
    if str(run_company) != str(per_company):
        raise WorkflowError("Run et période de sociétés différentes (P0-06).")
    if not run_actif:
        raise WorkflowError("Run inactif (superseded) : recalcul requis avant clôture.")
    if per_statut == "cloturee":
        raise WorkflowError("Période déjà clôturée.")

    # Séparation des tâches 4 yeux (INV-10), selon la politique de l'abonné : l'auteur
    # du CALCUL du run ne peut pas en être le VALIDATEUR/clôtureur. La dérogation motivée
    # (override_reason) reste tracée en audit. Mode opérateur unique : l'abonné peut
    # désactiver la politique (governance_policy) ; appels sans acteur = non concernés.
    if actor and not override_reason and four_eyes_policy(conn, run_company,
                                                          "four_eyes_calcul_validation"):
        calc = conn.execute(
            "SELECT calcule_par FROM payroll_run WHERE id=%s", (run_id,)).fetchone()
        if calc and calc[0] is not None and str(calc[0]) == str(actor):
            raise WorkflowError(
                "Séparation des tâches (4 yeux) : l'auteur du calcul de la paie ne peut "
                "pas la valider/clôturer. Un second utilisateur est requis.")

    # Contrôles bloquants dans la transaction de clôture (P0-02).
    anomalies = run_controls(conn, run_id)
    blocs = bloquants(anomalies)
    if blocs and not override_reason:
        codes = ", ".join(sorted({a["code"] for a in blocs}))
        raise WorkflowError(f"Clôture refusée : {len(blocs)} anomalie(s) bloquante(s) [{codes}].")

    conn.execute("UPDATE payslip SET verrouille=true WHERE run_id=%s", (run_id,))
    conn.execute("UPDATE payroll_period SET statut='cloturee', cloture_par=%s WHERE id=%s",
                 (actor, period_id))
    audit(conn, "period.close", "payroll_period", run_company, actor,
          avant={"statut": per_statut},
          apres={"statut": "cloturee", "run_id": str(run_id),
                 "override": override_reason, "bloquants_ignores": len(blocs) if override_reason else 0})


def list_payslips(conn, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT e.nom, p.brut, p.base_its, p.net_a_payer, p.cout_employeur, p.verrouille, "
        "       e.id, e.matricule, p.resultat "
        "FROM payslip p JOIN employee e ON e.id=p.employee_id WHERE p.run_id=%s "
        "ORDER BY e.nom", (run_id,)).fetchall()
    return [dict(nom=r[0], brut=float(r[1]), base_its=float(r[2]),
                 net=float(r[3]), cout_employeur=float(r[4]), verrouille=r[5],
                 employee_id=str(r[6]), matricule=r[7], detail=r[8]) for r in rows]


# ─────────────── Campagne de paie (multi-société) ───────────────
def create_campaign(conn, org_node_id: str, mois: int, annee: int) -> str:
    return str(conn.execute(
        "INSERT INTO payroll_campaign(org_node_id, mois, annee) VALUES (%s,%s,%s) "
        "ON CONFLICT (org_node_id, annee, mois) DO UPDATE SET statut='en_cours' RETURNING id",
        (org_node_id, mois, annee)).fetchone()[0])

def attach_run_to_campaign(conn, run_id: str, campaign_id: str) -> None:
    conn.execute("UPDATE payroll_run SET campaign_id=%s WHERE id=%s", (campaign_id, run_id))

def campaign_status(conn, campaign_id: str) -> dict:
    """Avancement consolidé : par société (run), nombre de bulletins, net total."""
    rows = conn.execute(
        "SELECT c.raison_sociale, pp.statut, count(p.id), COALESCE(SUM(p.net_a_payer),0) "
        "FROM payroll_run r JOIN company c ON c.id=r.company_id "
        "JOIN payroll_period pp ON pp.id=r.period_id "
        "LEFT JOIN payslip p ON p.run_id=r.id "
        "WHERE r.campaign_id=%s GROUP BY c.raison_sociale, pp.statut ORDER BY c.raison_sociale",
        (campaign_id,)).fetchall()
    societes = [dict(societe=r[0], statut=r[1], bulletins=r[2], net=float(r[3])) for r in rows]
    return {"campaign_id": campaign_id, "societes": societes,
            "total_net": sum(s["net"] for s in societes),
            "total_bulletins": sum(s["bulletins"] for s in societes)}


def payroll_overview(conn, mois: int, annee: int) -> dict:
    """Vue multi-société de l'avancement de la paie pour un mois donné : pour CHAQUE
    société du périmètre (RLS), le statut de la période + nombre de bulletins + net.
    Ne dépend pas du rattachement à une campagne (agrège directement par période)."""
    rows = conn.execute(
        "SELECT c.id, c.raison_sociale, pp.statut, "
        "  COALESCE((SELECT count(*) FROM payslip p JOIN payroll_run r ON r.id=p.run_id "
        "            WHERE r.period_id=pp.id AND p.resultat IS NOT NULL),0) AS nb, "
        "  COALESCE((SELECT SUM(p.net_a_payer) FROM payslip p JOIN payroll_run r ON r.id=p.run_id "
        "            WHERE r.period_id=pp.id AND p.resultat IS NOT NULL),0) AS net "
        "FROM company c "
        "LEFT JOIN payroll_period pp ON pp.company_id=c.id AND pp.mois=%s AND pp.annee=%s "
        "WHERE c.workspace_id IS NOT NULL "
        "ORDER BY c.raison_sociale", (mois, annee)).fetchall()
    societes = [dict(company_id=str(r[0]), raison_sociale=r[1], statut=(r[2] or "aucune"),
                     bulletins=int(r[3] or 0), net=float(r[4] or 0)) for r in rows]
    traitees = sum(1 for s in societes if s["statut"] not in ("aucune", "ouverte"))
    return {"mois": int(mois), "annee": int(annee), "societes": societes,
            "nb_societes": len(societes), "nb_traitees": traitees,
            "total_net": sum(s["net"] for s in societes),
            "total_bulletins": sum(s["bulletins"] for s in societes)}


# ─────────────── Reporting (agrégats réels depuis la BD) ───────────────
def reporting_summary(conn, company_id: str) -> dict:
    rows = conn.execute(
        "SELECT resultat FROM payslip WHERE company_id=%s AND resultat IS NOT NULL", (company_id,)).fetchall()
    agg = {k: 0 for k in ("brut", "cnss_pat", "vps", "amo_pat", "net")}
    for (r,) in rows:
        agg["brut"] += r.get("brut", 0) or 0
        agg["cnss_pat"] += r.get("cnss_pat", 0) or 0
        agg["vps"] += r.get("vps", 0) or 0
        agg["amo_pat"] += r.get("amo_pat", 0) or 0
        agg["net"] += r.get("net", 0) or 0
    charges_pat = agg["cnss_pat"] + agg["vps"] + agg["amo_pat"]
    effectif = conn.execute(
        "SELECT count(*) FROM employee WHERE company_id=%s AND deleted_at IS NULL", (company_id,)).fetchone()[0]
    # coûts par service (département)
    parserv = conn.execute(
        "SELECT COALESCE(d.nom,'(non affecté)'), COALESCE(SUM(ct.salaire_base),0) "
        "FROM contract ct LEFT JOIN department d ON d.id=ct.department_id "
        "WHERE ct.company_id=%s AND ct.statut='actif' GROUP BY d.nom", (company_id,)).fetchall()
    return {
        "masse_brute": round(agg["brut"]),
        "charges_patronales": round(charges_pat),
        "cout_employeur": round(agg["brut"] + charges_pat),
        "net_total": round(agg["net"]),
        "effectif": effectif,
        "couts_par_service": [dict(service=r[0], montant=float(r[1])) for r in parserv],
    }


# ─────────────── Sociétés visibles (scope-RLS) ───────────────
def list_companies(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, raison_sociale, ifu, num_employeur_cnss "
        "FROM company ORDER BY raison_sociale").fetchall()
    return [dict(id=str(r[0]), nom=r[1], ifu=r[2], num_employeur_cnss=r[3]) for r in rows]


# ─────────────── Employés (liste) ───────────────
def list_employees(conn, company_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT e.id, e.nom, e.matricule, e.methode_paiement, "
        " (SELECT c.salaire_base FROM contract c WHERE c.employee_id=e.id "
        "  AND c.statut='actif' ORDER BY c.date_debut DESC LIMIT 1) "
        "FROM employee e WHERE e.company_id=%s AND e.deleted_at IS NULL ORDER BY e.nom",
        (company_id,)).fetchall()
    return [dict(id=str(r[0]), nom=r[1], matricule=r[2], methode=str(r[3]),
                 salaire_base=float(r[4] or 0)) for r in rows]


# ─────────────── Variables du mois ───────────────
def add_variable(conn, company_id: str, employee_id: str, period_id: str,
                 type_: str, montant: float, actor: str | None = None,
                 source_ref: str | None = None) -> str:
    """Ajoute une variable. Avec `source_ref` (ex. 'import:fichier#ligne'), l'opération
    est IDEMPOTENTE (MQ-05) : rejouer le même import ne duplique pas la ligne ; l'id
    existant est renvoyé sans réinsertion ni nouvel audit."""
    if source_ref is not None:
        row = conn.execute(
            "INSERT INTO variable(company_id, employee_id, period_id, type, montant, source_ref) "
            "VALUES (%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (company_id, period_id, employee_id, type, source_ref) "
            "WHERE source_ref IS NOT NULL DO NOTHING "
            "RETURNING id",
            (company_id, employee_id, period_id, type_, montant, source_ref)).fetchone()
        if row is None:  # déjà importée : on renvoie l'id existant (no-op)
            return str(conn.execute(
                "SELECT id FROM variable WHERE company_id=%s AND period_id=%s "
                "AND employee_id=%s AND type=%s AND source_ref=%s",
                (company_id, period_id, employee_id, type_, source_ref)).fetchone()[0])
        audit(conn, "variable.add", "variable", company_id, actor,
              apres={"employee_id": str(employee_id), "type": type_, "montant": montant,
                     "source_ref": source_ref})
        return str(row[0])
    vid = conn.execute(
        "INSERT INTO variable(company_id, employee_id, period_id, type, montant) "
        "VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (company_id, employee_id, period_id, type_, montant)).fetchone()[0]
    audit(conn, "variable.add", "variable", company_id, actor,
          apres={"employee_id": str(employee_id), "type": type_, "montant": montant})
    return str(vid)


def import_variables(conn, company_id: str, period_id: str, lignes: list[dict],
                     actor: str | None = None) -> dict:
    """Import REJOUABLE de variables du mois (MQ-05). Chaque ligne =
    {employee_id, type, montant, source_ref}. Les lignes déjà importées (même
    source_ref) sont ignorées sans doublon. Retourne {inserees, ignorees, total}.
    Câble l'écran W44 (import fichier salariés/variables)."""
    inserees = ignorees = 0
    for l in lignes:
        src = l.get("source_ref")
        if not src:
            raise ValueError("import_variables exige un 'source_ref' par ligne (dédup).")
        avant = conn.execute(
            "SELECT 1 FROM variable WHERE company_id=%s AND period_id=%s AND employee_id=%s "
            "AND type=%s AND source_ref=%s",
            (company_id, period_id, l["employee_id"], l["type"], src)).fetchone()
        add_variable(conn, company_id, l["employee_id"], period_id, l["type"],
                     l["montant"], actor=actor, source_ref=src)
        if avant:
            ignorees += 1
        else:
            inserees += 1
    audit(conn, "variable.import", "variable", company_id, actor,
          apres={"inserees": inserees, "ignorees": ignorees, "total": len(lignes)})
    return {"inserees": inserees, "ignorees": ignorees, "total": len(lignes)}


# ─────────────── Gouvernance : matrice de droits configurable par l'abonné ───────────────
# Le code ne porte que le DÉFAUT (deny-by-default, cf. api_v2.PERMISSIONS). L'administrateur
# désigné par l'abonné peut surcharger action x rôle (table permission_override), par workspace.
_ADMIN_FLOOR_ACTIONS = {"permissions.manage", "governance.manage"}

def effective_allowed_roles(conn, action: str, workspaces, default_roles) -> set[str]:
    """Rôles effectivement autorisés pour `action`, = défaut du code surchargé par les
    overrides de l'abonné (workspace). Deny-by-default préservé (part du défaut).
    Garde-fou anti-lockout : l'admin garde toujours la gestion des droits/gouvernance."""
    allow = set(default_roles)
    ws = [str(w) for w in (workspaces or [])]
    if ws:
        rows = conn.execute(
            "SELECT role_code, allowed FROM permission_override "
            "WHERE action=%s AND workspace_id = ANY(%s)", (action, ws)).fetchall()
        for role_code, allowed in rows:
            if allowed:
                allow.add(role_code)
            else:
                allow.discard(role_code)
    if action in _ADMIN_FLOOR_ACTIONS:
        allow.add("admin")
    return allow

def set_permission_override(conn, workspace_id: str, action: str, role_code: str,
                            allowed: bool, actor: str | None = None) -> None:
    """Pose/menace une surcharge de droit pour l'abonné. Anti-lockout : interdit de
    retirer à `admin` la gestion des droits/gouvernance."""
    if action in _ADMIN_FLOOR_ACTIONS and role_code == "admin" and not allowed:
        raise WorkflowError("Anti-verrouillage : impossible de retirer à l'admin la "
                            "gestion des droits.")
    conn.execute(
        "INSERT INTO permission_override(workspace_id, action, role_code, allowed, updated_by) "
        "VALUES (%s,%s,%s,%s,%s) "
        "ON CONFLICT (workspace_id, action, role_code) "
        "DO UPDATE SET allowed=EXCLUDED.allowed, updated_by=EXCLUDED.updated_by, updated_at=now()",
        (workspace_id, action, role_code, allowed, actor))
    audit(conn, "permissions.set", "permission_override", None, actor,
          apres={"workspace_id": str(workspace_id), "action": action,
                 "role_code": role_code, "allowed": allowed})

def list_permission_overrides(conn, workspace_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT action, role_code, allowed FROM permission_override "
        "WHERE workspace_id=%s ORDER BY action, role_code", (workspace_id,)).fetchall()
    return [dict(action=r[0], role_code=r[1], allowed=r[2]) for r in rows]

def get_governance_policy(conn, workspace_id: str) -> dict:
    row = conn.execute(
        "SELECT four_eyes_calcul_validation, four_eyes_validation_paiement "
        "FROM governance_policy WHERE workspace_id=%s", (workspace_id,)).fetchone()
    # défaut = 4-eyes désactivé tant que l'admin n'a pas enregistré de politique
    if row is None:
        return {"four_eyes_calcul_validation": False, "four_eyes_validation_paiement": False}
    return {"four_eyes_calcul_validation": bool(row[0]),
            "four_eyes_validation_paiement": bool(row[1])}

def set_governance_policy(conn, workspace_id: str, champ: str, valeur: bool,
                          actor: str | None = None) -> None:
    if champ not in _POLICY_CHAMPS:
        raise ValueError(f"Champ de politique inconnu : {champ}")
    conn.execute(
        f"INSERT INTO governance_policy(workspace_id, {champ}, updated_by) VALUES (%s,%s,%s) "
        f"ON CONFLICT (workspace_id) DO UPDATE SET {champ}=EXCLUDED.{champ}, "
        "updated_by=EXCLUDED.updated_by, updated_at=now()",
        (workspace_id, valeur, actor))
    audit(conn, "governance.set", "governance_policy", None, actor,
          apres={"workspace_id": str(workspace_id), champ: valeur})


# ─────────────── Contrôles d'anomalies (RG-CTRL-001) sur run persisté ───────────────
def run_controls(conn, run_id: str) -> list[dict]:
    per = conn.execute(
        "SELECT pp.mois, pp.annee FROM payroll_run r JOIN payroll_period pp ON pp.id=r.period_id "
        "WHERE r.id=%s", (run_id,)).fetchone()
    periode = date(per[1], per[0], 1)
    rows = conn.execute(
        "SELECT e.nom, p.resultat, "
        " (SELECT c.salaire_base FROM contract c WHERE c.employee_id=p.employee_id "
        "  AND c.statut='actif' ORDER BY c.date_debut DESC LIMIT 1) "
        "FROM payslip p JOIN employee e ON e.id=p.employee_id WHERE p.run_id=%s", (run_id,)).fetchall()
    anomalies: list[dict] = []
    for nom, resultat, base in rows:
        if resultat is None:
            continue
        anomalies += controler_bulletin(resultat, float(base or 0), periode, employe=nom)

    # P1-06 : rubrique VRAIMENT libre (ni pay_element société, ni catalogue standard
    # validé) -> assiettes par défaut -> avertissement de validation (visibilité, pas de
    # blocage silencieux). Les codes du catalogue STANDARD_RUBRIQUES ont des assiettes
    # juridiquement fondées : ils ne déclenchent PAS cet avertissement (sinon le non-expert
    # croit à tort que sa paie est douteuse, ex. indemnité de transport).
    free = conn.execute(
        "SELECT DISTINCT v.type FROM variable v JOIN payroll_run r ON r.id=%s "
        "LEFT JOIN pay_element pe ON pe.company_id=v.company_id AND pe.code=v.type "
        "WHERE v.period_id=r.period_id AND pe.id IS NULL", (run_id,)).fetchall()
    for (typ,) in free:
        if typ in STANDARD_RUBRIQUES:
            continue  # assiettes validées par le catalogue -> pas d'avertissement
        anomalies.append({"gravite": "avertissement", "code": "CTRL-RUBRIQUE-LIBRE",
                          "message": f"Rubrique « {typ} » non référencée (assiettes par défaut) : à valider.",
                          "regle": "RG-CTRL-001", "source": "référentiel rubriques", "employe": None})

    anomalies.sort(key=lambda a: 0 if a["gravite"] == "bloquant" else 1)
    return anomalies


# ─────────────── Déclarations (agrégats depuis les bulletins persistés) ───────────────
def declaration_aggregate(conn, run_id: str) -> dict:
    rows = conn.execute(
        "SELECT resultat FROM payslip WHERE run_id=%s AND resultat IS NOT NULL", (run_id,)).fetchall()
    agg = {k: 0 for k in ("its", "cnss_sal", "cnss_pat", "vps", "amo_sal",
                          "amo_pat", "base_its", "assiette_cnss", "net")}
    for (r,) in rows:
        for k in agg:
            agg[k] += r.get(k, 0) or 0
    agg = {k: round(v) for k, v in agg.items()}
    return {
        "bulletins": len(rows),
        "its_vps": {"its_total": agg["its"], "vps_total": agg["vps"], "base_its_total": agg["base_its"]},
        "cnss": {"salariale": agg["cnss_sal"], "patronale": agg["cnss_pat"], "assiette": agg["assiette_cnss"]},
        "amo": {"salariale": agg["amo_sal"], "patronale": agg["amo_pat"]},
        "net_total": agg["net"],
    }


def pay_registers(conn, run_id: str) -> dict:
    """Assemble les registres légaux — livre de paie, bordereau CNSS (liste nominative),
    bordereau DGI (ITS/VPS) — À PARTIR des bulletins déjà calculés et persistés.
    AUCUNE recomputation : on relit le `resultat` du moteur validé (exactitude garantie).
    Lève WorkflowError si le run est introuvable (ou hors périmètre RLS)."""
    meta = conn.execute(
        "SELECT pp.mois, pp.annee, pp.statut, c.raison_sociale, c.ifu, c.num_employeur_cnss "
        "FROM payroll_run r JOIN payroll_period pp ON pp.id=r.period_id "
        "JOIN company c ON c.id=r.company_id WHERE r.id=%s", (run_id,)).fetchone()
    if not meta:
        raise WorkflowError("Run introuvable (ou hors périmètre).")
    mois, annee, statut, raison, ifu, num_cnss_emp = meta
    rows = conn.execute(
        "SELECT e.matricule, e.nom, e.num_cnss, p.resultat "
        "FROM payslip p JOIN employee e ON e.id=p.employee_id "
        "WHERE p.run_id=%s AND p.resultat IS NOT NULL ORDER BY e.nom", (run_id,)).fetchall()

    cols = ("brut", "assiette_cnss", "cnss_sal", "cnss_pat", "base_its",
            "its", "vps", "ortb", "net_a_payer", "cout_employeur")
    tot = {k: 0 for k in cols}
    livre, cnss_lignes, dgi_lignes = [], [], []
    for mat, nom, ncnss, res in rows:
        res = res or {}
        d = {k: round(res.get(k, 0) or 0) for k in cols}
        for k in cols:
            tot[k] += d[k]
        livre.append({"matricule": mat, "nom": nom, **d})
        cnss_lignes.append({"num_cnss": ncnss or "", "nom": nom, "assiette": d["assiette_cnss"],
                            "part_sal": d["cnss_sal"], "part_pat": d["cnss_pat"]})
        dgi_lignes.append({"matricule": mat, "nom": nom, "base_its": d["base_its"],
                           "its": d["its"], "vps": d["vps"]})
    tot = {k: round(v) for k, v in tot.items()}
    return {
        "periode": {"mois": int(mois), "annee": int(annee), "statut": statut},
        "societe": {"raison_sociale": raison, "ifu": ifu, "num_employeur_cnss": num_cnss_emp},
        "effectif": len(rows),
        "livre_paie": {"lignes": livre, "totaux": tot},
        "bordereau_cnss": {"lignes": cnss_lignes, "assiette_totale": tot["assiette_cnss"],
                           "total_sal": tot["cnss_sal"], "total_pat": tot["cnss_pat"],
                           "total": tot["cnss_sal"] + tot["cnss_pat"]},
        "bordereau_dgi": {"lignes": dgi_lignes, "base_its_totale": tot["base_its"],
                          "its_total": tot["its"], "vps_total": tot["vps"],
                          "total_a_reverser": tot["its"] + tot["vps"]},
    }


def payroll_accounting_reconciliation(conn, run_id: str) -> dict:
    """Rapprochement paie ↔ comptabilité : confronte l'agrégat de paie (bulletins) au
    journal SYSCOHADA (écriture consolidée). Les deux dérivent des mêmes bulletins ; tout
    écart signale une incohérence. Nécessite un run CLÔTURÉ (l'écriture est alors générée)."""
    company_id, mois, annee = _run_cloture_info(conn, run_id)
    agg = declaration_aggregate(conn, run_id)
    brut = float(conn.execute(
        "SELECT COALESCE(SUM((resultat->>'brut')::numeric),0) FROM payslip "
        "WHERE run_id=%s AND resultat IS NOT NULL", (run_id,)).fetchone()[0])
    acc = persist_accounting(conn, run_id, actor=None)   # idempotent : renvoie l'existante
    deb, cre = {}, {}
    for l in acc["lignes"]:
        deb[l["compte"]] = deb.get(l["compte"], 0) + float(l["debit"] or 0)
        cre[l["compte"]] = cre.get(l["compte"], 0) + float(l["credit"] or 0)

    its = agg["its_vps"]["its_total"]; vps = agg["its_vps"]["vps_total"]
    cnss_sal = agg["cnss"]["salariale"]; cnss_pat = agg["cnss"]["patronale"]; net = agg["net_total"]
    points = [
        ("Rémunérations brutes (66)", brut, deb.get("6611", 0)),
        ("Charges patronales CNSS (664)", cnss_pat, deb.get("6641", 0)),
        ("Versement patronal VPS (641)", vps, deb.get("641", 0)),
        ("CNSS à reverser (431)", cnss_sal + cnss_pat, cre.get("431", 0)),
        ("ITS à reverser (447)", its, cre.get("4472", 0)),
        ("VPS à reverser (442)", vps, cre.get("4421", 0)),
        ("Net à payer au personnel (422)", net, cre.get("422", 0)),
    ]
    lignes = [dict(libelle=lib, paie=round(p), compta=round(c), ecart=round(p - c),
                   ok=(round(p - c) == 0)) for lib, p, c in points]
    equilibre = round(acc["total_debit"]) == round(acc["total_credit"])
    return {
        "periode": {"mois": mois, "annee": annee},
        "lignes": lignes,
        "total_debit": round(acc["total_debit"]), "total_credit": round(acc["total_credit"]),
        "equilibre": equilibre,
        "ecarts": sum(1 for l in lignes if not l["ok"]) + (0 if equilibre else 1),
        "concordant": all(l["ok"] for l in lignes) and equilibre,
    }


def payment_register(conn, run_id: str) -> dict:
    """Registre de paiement des salaires (Code du Travail Bénin, art. 224-226) :
    preuve des paiements effectués par salarié (net payé, méthode, date, statut, référence).
    Lu depuis les ordres de décaissement (payout). Vide tant qu'aucun décaissement n'a eu lieu."""
    meta = conn.execute(
        "SELECT pp.mois, pp.annee, pp.statut, c.raison_sociale, c.ifu, c.num_employeur_cnss "
        "FROM payroll_run r JOIN payroll_period pp ON pp.id=r.period_id "
        "JOIN company c ON c.id=r.company_id WHERE r.id=%s", (run_id,)).fetchone()
    if not meta:
        raise WorkflowError("Run introuvable (ou hors périmètre).")
    mois, annee, statut, raison, ifu, num_cnss_emp = meta
    rows = conn.execute(
        "SELECT e.matricule, e.nom, e.num_cnss, i.montant, i.methode, i.statut, "
        "       i.reference_operateur, b.created_at "
        "FROM payout_item i JOIN payout_batch b ON b.id=i.batch_id "
        "JOIN employee e ON e.id=i.employee_id "
        "WHERE b.run_id=%s ORDER BY e.nom", (run_id,)).fetchall()
    lignes = [dict(matricule=r[0], nom=r[1], num_cnss=r[2] or "", net_paye=float(r[3]),
                   methode=str(r[4]), statut=r[5], reference=r[6] or "",
                   date_paiement=str(r[7])[:10]) for r in rows]
    return {
        "periode": {"mois": int(mois), "annee": int(annee), "statut": statut},
        "societe": {"raison_sociale": raison, "ifu": ifu, "num_employeur_cnss": num_cnss_emp},
        "nb_paiements": len(lignes),
        "total_paye": round(sum(l["net_paye"] for l in lignes)),
        "lignes": lignes,
    }


def provisions(conn, company_id: str) -> dict:
    """Provisions sociales INDICATIVES par salarié actif :
    - Provision congés payés = (jours acquis non pris sur l'année) × (salaire journalier, 1/30e).
      Acquis = droit_conges_annuels (Art. 152/158) ; pris = congés annuels validés de l'année.
    - Engagement IFC (indemnité de fin de carrière) = indemnité de départ à la retraite À DATE
      (CCGT Art. 57, min 3 mois). Montant dû si le salarié partait aujourd'hui (non actualisé).
    ⚠️ Estimation de gestion, NON certifiée (une provision IFC actuarielle actualisée relève
    d'un actuaire). À faire valider par un expert-comptable avant inscription au bilan."""
    from datetime import date as _date
    from conges_maternite import droit_conges_annuels, indemnite_depart_retraite
    today = _date.today(); an = today.year
    rows = conn.execute(
        "SELECT e.id, e.matricule, e.nom, c.date_debut, c.salaire_base "
        "FROM employee e JOIN contract c ON c.employee_id=e.id AND c.statut='actif' "
        "WHERE e.company_id=%s AND e.deleted_at IS NULL ORDER BY e.nom", (company_id,)).fetchall()
    lignes = []
    for eid, mat, nom, dd, sal in rows:
        sal = float(sal or 0)
        anc_ans = max(0.0, (today - dd).days / 365.25) if dd else 0.0
        mois_service = max(0, (today.year - dd.year) * 12 + today.month - dd.month) if dd else 0
        acquis = droit_conges_annuels(mois_service=min(mois_service, 12),
                                      anciennete_ans=int(anc_ans))["jours_acquis"]
        pris = float(conn.execute(
            "SELECT COALESCE(SUM(jours),0) FROM leave_request WHERE employee_id=%s "
            "AND type='conge_annuel' AND statut='valide' AND EXTRACT(YEAR FROM date_debut)=%s",
            (eid, an)).fetchone()[0])
        solde_j = max(0.0, acquis - pris)
        prov_conges = round(solde_j * sal / 30)
        ifc = indemnite_depart_retraite(sal, anc_ans)["montant"] if anc_ans > 0 else 0
        lignes.append(dict(matricule=mat, nom=nom, anciennete_ans=round(anc_ans, 1),
                           jours_cp=round(solde_j, 1), provision_conges=prov_conges,
                           engagement_ifc=ifc))
    return {
        "annee": an, "effectif": len(lignes), "lignes": lignes,
        "total_provision_conges": sum(l["provision_conges"] for l in lignes),
        "total_engagement_ifc": sum(l["engagement_ifc"] for l in lignes),
    }


def _run_cloture_info(conn, run_id: str):
    """(company_id, mois, annee) si le run existe et sa période est clôturée, sinon lève."""
    info = conn.execute(
        "SELECT r.company_id, pp.statut, pp.mois, pp.annee FROM payroll_run r "
        "JOIN payroll_period pp ON pp.id=r.period_id WHERE r.id=%s", (run_id,)).fetchone()
    if not info:
        raise WorkflowError("Run introuvable (ou hors périmètre).")
    if info[1] != "cloturee":
        raise WorkflowError("Opération réservée à un run clôturé.")
    return str(info[0]), int(info[2]), int(info[3])


def persist_declaration(conn, run_id: str, actor: str | None = None) -> list[dict]:
    """Persiste les déclarations (ITS, VPS, CNSS, AMO) d'un run CLÔTURÉ, avec échéances
    indicatives et statut 'preparee'. Idempotent (une seule série par run).
    ⚠️ Le dépôt/accusé officiel DGI/CNSS reste une VALIDATION EXTERNE (fichier non homologué)."""
    company_id, mois, annee = _run_cloture_info(conn, run_id)
    # Verrou transactionnel par run : sérialise les persistances concurrentes (idempotence sûre).
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"decl:{run_id}",))
    existing = conn.execute(
        "SELECT id, type, montant, echeance, statut FROM declaration WHERE run_id=%s ORDER BY type",
        (run_id,)).fetchall()
    if existing:
        return [dict(id=str(r[0]), type=r[1], montant=float(r[2] or 0),
                     echeance=r[3].isoformat() if r[3] else None, statut=r[4]) for r in existing]
    agg = declaration_aggregate(conn, run_id)
    periode = date(annee, mois, 1)
    mois_suiv = date(annee + (1 if mois == 12 else 0), 1 if mois == 12 else mois + 1, 1)
    ech_fisc = mois_suiv.replace(day=10)   # ITS/VPS : le 10 du mois suivant (indicatif)
    ech_cnss = mois_suiv.replace(day=15)   # CNSS : J+15 (indicatif, à confirmer)
    lignes = [("ITS", agg["its_vps"]["its_total"], ech_fisc),
              ("VPS", agg["its_vps"]["vps_total"], ech_fisc),
              ("CNSS", agg["cnss"]["salariale"] + agg["cnss"]["patronale"], ech_cnss),
              ("AMO", agg["amo"]["salariale"] + agg["amo"]["patronale"], ech_cnss)]
    out = []
    for typ, montant, ech in lignes:
        did = conn.execute(
            "INSERT INTO declaration(company_id, run_id, type, periode, echeance, montant, statut) "
            "VALUES (%s,%s,%s,%s,%s,%s,'preparee') RETURNING id",
            (company_id, run_id, typ, periode, ech, montant)).fetchone()[0]
        out.append(dict(id=str(did), type=typ, montant=montant, echeance=ech.isoformat(),
                        statut="preparee"))
    audit(conn, "declaration.persist", "declaration", company_id, actor,
          apres={"run_id": str(run_id), "lignes": len(out)})
    return out


def persist_accounting(conn, run_id: str, actor: str | None = None) -> dict:
    """Persiste l'écriture comptable consolidée (SYSCOHADA) d'un run CLÔTURÉ.
    Débit = crédit garanti par construction. Idempotent (une seule écriture par run)."""
    company_id, mois, annee = _run_cloture_info(conn, run_id)
    # Verrou transactionnel par run : sérialise les persistances concurrentes (double POST
    # React StrictMode, double-clic, retry) → pas de double écriture. Libéré en fin de transaction.
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"acc:{run_id}",))
    existing = conn.execute(
        "SELECT compte, libelle, debit, credit FROM accounting_entry WHERE run_id=%s ORDER BY id",
        (run_id,)).fetchall()
    if existing:
        lignes = [dict(compte=r[0], libelle=r[1], debit=float(r[2] or 0), credit=float(r[3] or 0))
                  for r in existing]
        return {"run_id": str(run_id), "lignes": lignes,
                "total_debit": round(sum(l["debit"] for l in lignes)),
                "total_credit": round(sum(l["credit"] for l in lignes)), "deja_persiste": True}
    agg = declaration_aggregate(conn, run_id)
    brut = agg["its_vps"]["base_its_total"]  # base ITS = brut imposable ; brut réel via résultat
    # Recalcule le brut total depuis les bulletins (base_its peut différer du brut).
    brut = conn.execute(
        "SELECT COALESCE(SUM((resultat->>'brut')::numeric),0) FROM payslip "
        "WHERE run_id=%s AND resultat IS NOT NULL", (run_id,)).fetchone()[0]
    c = agg["cnss"]; its = agg["its_vps"]["its_total"]; vps = agg["its_vps"]["vps_total"]
    a = agg["amo"]; net = agg["net_total"]
    ecr = date(annee, mois, 28)
    # Écriture consolidée (équilibrée : débit cout_employeur = crédit dettes + net).
    lignes = [
        ("6611", "Rémunérations brutes", brut, 0),
        ("6641", "Charges sociales patronales (CNSS)", c["patronale"], 0),
        ("641",  "Versement patronal sur salaires (VPS)", vps, 0),
        ("6641", "Charge patronale AMO", a["patronale"], 0),
        ("431",  "CNSS à reverser (sal + pat)", 0, c["salariale"] + c["patronale"]),
        ("4472", "ITS à reverser (État)", 0, its),
        ("4421", "VPS à reverser (État)", 0, vps),
        ("4332", "AMO à reverser (assureur)", 0, a["salariale"] + a["patronale"]),
        ("422",  "Personnel, rémunérations dues (net)", 0, net),
    ]
    for compte, lib, deb, cred in lignes:
        conn.execute(
            "INSERT INTO accounting_entry(company_id, run_id, journal, compte, libelle, "
            "debit, credit, date_ecriture) VALUES (%s,%s,'PAIE',%s,%s,%s,%s,%s)",
            (company_id, run_id, compte, lib, deb, cred, ecr))
    td = round(sum(l[2] for l in lignes)); tc = round(sum(l[3] for l in lignes))
    audit(conn, "accounting.persist", "accounting_entry", company_id, actor,
          apres={"run_id": str(run_id), "total_debit": td, "total_credit": tc})
    return {"run_id": str(run_id),
            "lignes": [dict(compte=l[0], libelle=l[1], debit=l[2], credit=l[3]) for l in lignes],
            "total_debit": td, "total_credit": tc, "equilibree": td == tc}


# ─────────────── Décaissement multi-méthode (RG D7) ───────────────
def create_payout(conn, company_id: str, run_id: str, gateway=None,
                  actor: str | None = None) -> dict:
    """Crée le lot de décaissement et route chaque salarié selon sa méthode.
    Garde-fous (P0-04, P0-06) : la société doit être celle du run, le run doit être
    actif et sa période CLÔTURÉE ; un seul lot par run (idempotent).
    `mobile_money` transite par la passerelle (FedaPay si clé, sinon export sûr) ;
    virement/espèces/chèque restent « à envoyer » (traitement manuel/fichier)."""
    info = conn.execute(
        "SELECT r.company_id, r.actif, pp.statut "
        "FROM payroll_run r JOIN payroll_period pp ON pp.id=r.period_id WHERE r.id=%s",
        (run_id,)).fetchone()
    if not info:
        raise WorkflowError("Run introuvable (ou hors périmètre).")
    if str(info[0]) != str(company_id):
        raise WorkflowError("Société et run incohérents pour le décaissement (P0-06).")
    if not info[1]:
        raise WorkflowError("Run inactif (superseded) : décaissement interdit.")
    if info[2] != "cloturee":
        raise WorkflowError("Décaissement interdit avant clôture de la période (P0-04).")

    # Séparation des tâches (4 yeux) : le valideur de la clôture ne peut pas aussi
    # décaisser. Pilotée par la politique de l'abonné (governance_policy, défaut ACTIVÉ,
    # réglable par l'admin) OU forcée via WASALAIRE_FOUR_EYES=1 (rétro-compat/tests).
    _four_eyes_paiement = (os.environ.get("WASALAIRE_FOUR_EYES", "0") == "1"
                           or four_eyes_policy(conn, company_id, "four_eyes_validation_paiement"))
    if actor and _four_eyes_paiement:
        closer = conn.execute(
            "SELECT pp.cloture_par FROM payroll_run r JOIN payroll_period pp ON pp.id=r.period_id "
            "WHERE r.id=%s", (run_id,)).fetchone()
        if closer and closer[0] is not None and str(closer[0]) == str(actor):
            raise WorkflowError("Séparation des tâches (4 yeux) : le valideur de la clôture "
                                "ne peut pas décaisser. Un second utilisateur est requis.")

    from payout_gateway import default_gateway
    gw = gateway or default_gateway()
    # Un seul lot par run : si déjà présent, on le réutilise (idempotence P0-04).
    batch_id = conn.execute(
        "INSERT INTO payout_batch(company_id, run_id) VALUES (%s,%s) "
        "ON CONFLICT (run_id) DO UPDATE SET company_id=payout_batch.company_id RETURNING id",
        (company_id, run_id)).fetchone()[0]
    rows = conn.execute(
        "SELECT p.employee_id, e.methode_paiement, e.momo_operateur, e.momo_numero, e.nom, p.resultat "
        "FROM payslip p JOIN employee e ON e.id=p.employee_id WHERE p.run_id=%s", (run_id,)).fetchall()
    summary: dict[str, dict] = {}
    for emp_id, methode, momo_op, momo_num, nom, resultat in rows:
        # On décaisse le NET À PAYER (après avance/acompte), pas le net fiscal : sinon
        # on verserait l'avance en trop ET on ne la récupérerait jamais (double perte).
        r_ = resultat or {}
        montant = arrondi_fcfa(r_.get("net_a_payer", r_.get("net", 0)))
        cle = f"{run_id}:{emp_id}"
        # 1) Outbox : l'intention de paiement est écrite AVANT tout appel externe.
        conn.execute(
            "INSERT INTO payout_item(company_id, batch_id, employee_id, methode, montant, "
            "cle_idempotence, statut) VALUES (%s,%s,%s,%s,%s,%s,'a_envoyer') "
            "ON CONFLICT (cle_idempotence) DO NOTHING",
            (company_id, batch_id, emp_id, methode, montant, cle))
        item_id, cur_statut = conn.execute(
            "SELECT id, statut FROM payout_item WHERE cle_idempotence=%s", (cle,)).fetchone()
        # 2) Émission SEULEMENT si mobile money ET pas déjà émis : une reprise après
        #    incident ne ré-émet pas un ordre déjà envoyé/confirmé (anti double paiement).
        if str(methode) == "mobile_money" and cur_statut == "a_envoyer":
            res = gw.send({"methode": "mobile_money", "montant": montant,
                           "momo_operateur": momo_op, "momo_numero": momo_num,
                           "nom": nom, "cle_idempotence": cle})
            conn.execute(
                "UPDATE payout_item SET statut=%s, reference_operateur=%s, accuse=%s WHERE id=%s",
                (res["statut"], res["reference_operateur"],
                 json.dumps(res.get("accuse")) if res.get("accuse") is not None else None, item_id))
        s = summary.setdefault(str(methode), {"n": 0, "montant": 0})
        s["n"] += 1
        s["montant"] += montant
    audit(conn, "payout.create", "payout_batch", company_id, actor,
          apres={"batch_id": str(batch_id), "run_id": str(run_id), "par_methode": summary})
    return {"batch_id": str(batch_id), "passerelle": gw.canal, "par_methode": summary}


def list_payout(conn, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT e.nom, i.methode, i.montant, i.statut FROM payout_item i "
        "JOIN payout_batch b ON b.id=i.batch_id JOIN employee e ON e.id=i.employee_id "
        "WHERE b.run_id=%s ORDER BY e.nom", (run_id,)).fetchall()
    return [dict(nom=r[0], methode=str(r[1]), montant=float(r[2]), statut=r[3]) for r in rows]
