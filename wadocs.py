"""
WaDocs — moteur de documents : fusion de champs {{Entité.champ}} + filtres (| money),
création de modèles et génération de documents (persistés + hash).
Le rendu texte est réel ; l'export DOCX/PDF et la signature électronique = étape ultérieure.
"""
from __future__ import annotations
import re, hashlib, json
from storage import store_bytes


def _fmt_money(v) -> str:
    try:
        return f"{int(round(float(v))):,}".replace(",", " ") + " F"
    except Exception:
        return str(v)


def merge(contenu: str, context: dict) -> str:
    """Remplace {{Chemin.pointe}} et {{Chemin | money}} par les valeurs du contexte.
    context = dict imbriqué, ex. {'Salarié': {'nom': 'KOFFI Alain'}, 'Contrat': {'salaire': 200000}}."""
    def resolve(path: str):
        cur = context
        for part in path.strip().split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur

    def repl(m):
        expr = m.group(1).strip()
        filt = None
        if "|" in expr:
            expr, filt = [x.strip() for x in expr.split("|", 1)]
        val = resolve(expr)
        if val is None:
            return f"[{expr} ?]"           # champ manquant visible, jamais silencieux
        if filt == "money":
            return _fmt_money(val)
        return str(val)

    return re.sub(r"\{\{(.+?)\}\}", repl, contenu)


# Modèle par défaut (contrat de travail) — champs de fusion réels
CONTRAT_TEMPLATE = """CONTRAT DE TRAVAIL

Entre {{Entreprise.raison_sociale}} (IFU {{Entreprise.ifu}})
et {{Salarié.nom}}, engagé(e) en qualité de {{Contrat.poste}}
à compter du {{Contrat.date_debut}}.

Rémunération mensuelle de base : {{Contrat.salaire | money}}.
Type de contrat : {{Contrat.type}}.
"""


CATEGORIES = ("embauche", "vie_salarie", "paie", "depart", "declarations", "courrier")


def create_template(conn, company_id, name, category, contenu) -> str:
    if category not in CATEGORIES:
        raise ValueError(f"category ∈ {CATEGORIES}")
    return str(conn.execute(
        "INSERT INTO document_template(company_id, name, category, contenu) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (company_id, name, category, contenu)).fetchone()[0])


def list_templates(conn, company_id) -> list[dict]:
    """Modèles de la société (le contrat par défaut est fourni par le code, hors table)."""
    rows = conn.execute(
        "SELECT id, name, category, contenu FROM document_template "
        "WHERE company_id=%s ORDER BY name", (company_id,)).fetchall()
    return [dict(id=str(r[0]), name=r[1], category=r[2], contenu=r[3]) for r in rows]


def get_template(conn, template_id, company_id):
    """(name, contenu) d'un modèle de la société, sinon None."""
    row = conn.execute(
        "SELECT name, contenu FROM document_template WHERE id=%s AND company_id=%s",
        (template_id, company_id)).fetchone()
    return (row[0], row[1]) if row else None


def generate_document(conn, company_id, titre, contenu_modele, context,
                      employee_id=None, template_id=None) -> dict:
    rendu = merge(contenu_modele, context)
    h = hashlib.sha256(rendu.encode()).hexdigest()
    doc_id = conn.execute(
        "INSERT INTO document(company_id, employee_id, template_id, titre, contenu, hash) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (company_id, employee_id, template_id, titre, rendu, h)).fetchone()[0]
    # A-06 : persiste l'artefact sur le stockage objet/volume (hors FS éphémère du
    # conteneur) et enregistre son URI. Le stockage ne doit JAMAIS faire échouer la
    # génération : en cas d'indisponibilité, le contenu reste disponible en base.
    storage_uri = None
    try:
        storage_uri = store_bytes(f"documents/{company_id}/{doc_id}.txt",
                                  rendu.encode("utf-8"), "text/plain; charset=utf-8")
        conn.execute("UPDATE document SET storage_uri=%s WHERE id=%s", (storage_uri, doc_id))
    except Exception:
        storage_uri = None
    return {"document_id": str(doc_id), "titre": titre, "contenu": rendu, "hash": h,
            "storage_uri": storage_uri}


def list_documents(conn, company_id) -> list[dict]:
    rows = conn.execute(
        "SELECT titre, statut, created_at FROM document WHERE company_id=%s "
        "ORDER BY created_at DESC LIMIT 100", (company_id,)).fetchall()
    return [dict(titre=r[0], statut=r[1], date=str(r[2])) for r in rows]
