"""
Générateur de bulletin de paie PDF (Bénin.
Branché sur moteur_paie.calcul_bulletin ; rend un bulletin lisible respectant
les mentions du Code du travail (Art. 224) : identité employeur/salarié, période,
emploi, brut, retenues (CNSS, ITS, AMO), net à payer, et volet patronal.

Les 3 assiettes distinctes (CNSS / ITS / VPS) sont affichées séparément, comme
dans le moteur. À compléter par l'arrêté « contexture du bulletin » une fois publié.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date

from moteur_paie import Salarie, Rubrique, calcul_bulletin

from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer, Image)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    _REPORTLAB = True
except ImportError:
    _REPORTLAB = False

# Charte graphique WaSalaire v1.1
WA_INDIGO = "#1E2A78"
WA_TEAL   = "#2EC4B6"
WA_INK    = "#0F172A"
WA_SAND   = "#F4D7B0"
WA_BG     = "#F8FAFC"
_LOGO = Path(__file__).parent / "assets" / "logo_couleur.png"

MOIS_FR = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]


def _f(n) -> str:
    """Format monétaire FCFA : espace comme séparateur de milliers."""
    return f"{round(n):,}".replace(",", " ")


@dataclass
class Employeur:
    raison_sociale: str
    ifu: str = ""              # Identifiant Fiscal Unique
    num_cnss: str = ""
    adresse: str = ""


@dataclass
class InfosSalarie:
    nom: str
    emploi: str = ""
    categorie: str = ""
    num_cnss: str = ""
    date_embauche: date | None = None


def generer_bulletin_pdf(
    employeur: Employeur,
    infos: InfosSalarie,
    sal: Salarie,
    rubriques: list[Rubrique],
    periode: date,
    chemin_pdf: str,
) -> dict:
    """Calcule et rend le bulletin en PDF. Retourne le détail du calcul + chemin."""
    b = calcul_bulletin(sal, rubriques, periode)
    if not _REPORTLAB:
        return {**b, "fichier": None, "erreur": "reportlab absent"}

    styles = getSampleStyleSheet()
    titre = ParagraphStyle("t", parent=styles["Title"], fontSize=15, spaceAfter=2,
                           textColor=colors.HexColor(WA_INDIGO), alignment=2)
    petit = ParagraphStyle("s", parent=styles["Normal"], fontSize=8,
                           textColor=colors.HexColor("#64748b"))
    h = ParagraphStyle("h", parent=styles["Normal"], fontSize=9, leading=12)

    doc = SimpleDocTemplate(chemin_pdf, pagesize=A4,
                            topMargin=13*mm, bottomMargin=15*mm,
                            leftMargin=15*mm, rightMargin=15*mm)
    el = []
    # En-tête : logo WaSalaire + titre bulletin
    logo_cell = (Image(str(_LOGO), width=48*mm, height=48*mm*0.26)
                 if _LOGO.exists() else Paragraph("<b>WaSalaire</b>", titre))
    entete = Table([[logo_cell,
                     Paragraph(f"BULLETIN DE PAIE<br/>"
                               f"<font size=9 color='#64748b'>Période : "
                               f"{MOIS_FR[periode.month]} {periode.year}</font>", titre)]],
                   colWidths=[90*mm, 90*mm])
    entete.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    el.append(entete)
    el.append(Spacer(1, 2*mm))
    el.append(Table([[""]], colWidths=[180*mm], rowHeights=[1.4],
                    style=[("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(WA_TEAL))]))
    el.append(Spacer(1, 5*mm))

    # Bloc employeur / salarié
    bloc = Table([
        [Paragraph(f"<b>Employeur</b><br/>{employeur.raison_sociale}<br/>"
                   f"IFU : {employeur.ifu or 'n/c'} · CNSS : {employeur.num_cnss or 'n/c'}<br/>"
                   f"{employeur.adresse}", h),
         Paragraph(f"<b>Salarié</b><br/>{infos.nom}<br/>"
                   f"Emploi : {infos.emploi or 'n/c'} · Catégorie : {infos.categorie or sal.categorie}<br/>"
                   f"N° CNSS : {infos.num_cnss or 'n/c'}"
                   + (f" · Embauché le {infos.date_embauche.strftime('%d/%m/%Y')}"
                      if infos.date_embauche else ""), h)],
    ], colWidths=[90*mm, 90*mm])
    bloc.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#BFBFBF")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BFBFBF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    el.append(bloc)
    el.append(Spacer(1, 5*mm))

    # Rubriques de gains + marqueurs d'assiette
    def marque(flag): return "Oui" if flag else "Non"
    data = [["Rubrique", "Montant", "CNSS", "ITS", "VPS"]]
    for r in rubriques:
        data.append([r.libelle, _f(r.montant), marque(r.soumis_cnss),
                     marque(r.soumis_its), marque(r.soumis_vps)])
    data.append(["SALAIRE BRUT", _f(b["brut"]), "", "", ""])
    t = Table(data, colWidths=[80*mm, 40*mm, 20*mm, 20*mm, 20*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(WA_INDIGO)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E7E9F4")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (2, 1), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    el.append(t)
    el.append(Spacer(1, 4*mm))

    # Assiettes + retenues salariales
    ret = [
        ["Base", "Montant", "Taux", "Retenue salarié"],
        ["Assiette CNSS", _f(b["assiette_cnss"]), "3,6 %", _f(b["cnss_sal"])],
        ["Base ITS (brute)", _f(b["base_its"]), "barème", _f(b["its"])],
    ]
    if b["amo_sal"]:
        ret.append(["AMO (part salarié)", "", "≤ 20 %", _f(b["amo_sal"])])
    ret.append(["", "", "NET À PAYER", _f(b["net"])])
    tr = Table(ret, colWidths=[70*mm, 40*mm, 30*mm, 40*mm])
    tr.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(WA_INDIGO)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E7FAF7")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    el.append(tr)
    el.append(Spacer(1, 4*mm))

    # Volet patronal
    pat = [
        ["Charges patronales", "Montant"],
        ["CNSS patronale (PF 9 % + pension 6,4 % + AT/MP)", _f(b["cnss_pat"])],
        ["VPS", _f(b["vps"])],
    ]
    if b["amo_pat"]:
        pat.append(["AMO (part employeur ≥ 80 %)", _f(b["amo_pat"])])
    pat.append(["COÛT TOTAL EMPLOYEUR", _f(b["cout_employeur"])])
    tp = Table(pat, colWidths=[140*mm, 40*mm])
    tp.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(WA_INK)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FBF1E1")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BFBFBF")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    el.append(tp)
    el.append(Spacer(1, 6*mm))
    el.append(Paragraph(
        "Assiettes distinctes (CNSS, ITS, VPS). Base ITS brute (CGI Art. 122-124). "
        "Mentions selon Code du travail Art. 224.", petit))

    doc.build(el)
    return {**b, "fichier": chemin_pdf, "format": "pdf"}


if __name__ == "__main__":
    emp = Employeur("SARL DEMO BÉNIN", ifu="3201900000000",
                    num_cnss="EMP-4021", adresse="Cotonou, Littoral")
    infos = InfosSalarie("DOSSOU Awa", emploi="Comptable", categorie="cadre",
                         num_cnss="BJ-001234", date_embauche=date(2020, 3, 1))
    sal = Salarie("DOSSOU Awa", categorie="cadre", at_mp=0.02)
    rubriques = [
        Rubrique("Salaire de base", 150000),
        Rubrique("Prime d'ancienneté", 20000),
        Rubrique("Indemnité de transport", 15000, soumis_cnss=False),  # ITS oui, CNSS non
    ]
    res = generer_bulletin_pdf(emp, infos, sal, rubriques, date(2026, 1, 1),
                               "bulletin_demo.pdf")
    print("Bulletin PDF généré :")
    for k in ("brut", "assiette_cnss", "base_its", "cnss_sal", "its",
              "net", "cout_employeur", "fichier"):
        print(f"  {k:15} = {res[k]}")
