"""
API de démonstration (FastAPI) — expose le moteur de paie TESTÉ en HTTP.
Matérialise `15-ARCHITECTURE-TECHNIQUE/api-design.md` en code exécutable.

⚠️ SKELETON pédagogique : pas de persistance (in-memory), auth simplifiée
(en-tête X-Company-Id simulé), aucune donnée réelle. Le calcul provient des
modules validés (58/58 tests) — l'API ne réimplémente aucune règle.

Lancer :  uvicorn api_demo:app --reload
Docs   :  http://127.0.0.1:8000/docs
Tester :  python api_demo.py   (smoke test via TestClient, sans serveur)
"""
from __future__ import annotations
from datetime import date
from typing import Literal

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from moteur_paie import Salarie, Rubrique, calcul_bulletin, param, PARAMS
from declaration_fiscale import declaration_its_vps
from solde_tout_compte import solde_tout_compte, TYPES_RUPTURE

app = FastAPI(
    title="API Paie Bénin (démo)",
    version="0.1.0",
    description="Expose le moteur de paie vérifié. Prototype — non contractuel.",
)

# CORS ouvert pour la démo frontend locale (⚠️ à restreindre en production).
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ─────────────── Schémas d'entrée/sortie (Pydantic) ───────────────
class RubriqueIn(BaseModel):
    libelle: str
    montant: float
    soumis_cnss: bool = True
    soumis_its: bool = True
    soumis_vps: bool = True


class BulletinIn(BaseModel):
    nom: str
    categorie: Literal["employe", "cadre", "ouvrier_horaire"] = "employe"
    at_mp: float = Field(0.02, ge=0.01, le=0.04)
    regime_vps: Literal["normal", "enseignement"] = "normal"
    prime_amo_mensuelle: float = 0.0
    periode: date
    rubriques: list[RubriqueIn]


class RuptureIn(BaseModel):
    type_rupture: str
    salaire_mensuel: float
    salaire_moyen_12m: float
    anciennete_ans: float
    jours_travailles_dernier_mois: int = 30
    jours_conges_acquis_non_pris: int = 0
    salaires_12m_pour_conges: float = 0
    preavis_indemnite: float = 0


def _company(x_company_id: str | None) -> str:
    """Simule l'exigence multi-tenant : X-Company-Id obligatoire (RLS)."""
    if not x_company_id:
        raise HTTPException(status_code=400, detail="En-tête X-Company-Id requis (multi-tenant).")
    return x_company_id


# ─────────────── Endpoints ───────────────
_assets = Path(__file__).parent / "assets"
if _assets.exists():
    app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")


@app.get("/", include_in_schema=False)
def frontend():
    """Sert le frontend de démo (même origine → fetch autorisé)."""
    html = Path(__file__).parent / "frontend_demo.html"
    if html.exists():
        return FileResponse(html)
    raise HTTPException(status_code=404, detail="frontend_demo.html introuvable")


@app.get("/health")
def health():
    return {"status": "ok", "moteur": "58/58 tests"}


@app.get("/v1/regulatory/rates")
def rates(at: date, x_company_id: str | None = Header(default=None)):
    _company(x_company_id)
    codes = {"taux_pension_sal", "taux_pension_emp", "taux_pf", "taux_vps"}
    return {"at": at, "rates": {c: param(c, at) for c in codes},
            "source": "PARAMS versionnés (moteur_paie)"}


@app.post("/v1/payroll/calculate")
def calculate(body: BulletinIn, x_company_id: str | None = Header(default=None)):
    _company(x_company_id)
    sal = Salarie(nom=body.nom, categorie=body.categorie, at_mp=body.at_mp,
                  regime_vps=body.regime_vps, prime_amo_mensuelle=body.prime_amo_mensuelle)
    rub = [Rubrique(**r.model_dump()) for r in body.rubriques]
    res = calcul_bulletin(sal, rub, body.periode)
    return {"company_id": x_company_id, "periode": body.periode, "bulletin": res}


@app.post("/v1/declarations/its-vps")
def declaration(body: list[BulletinIn], x_company_id: str | None = Header(default=None)):
    _company(x_company_id)
    if not body:
        raise HTTPException(status_code=422, detail="Liste de salariés vide.")
    periode = body[0].periode
    sals = []
    for i, b in enumerate(body, 1):
        sal = Salarie(nom=b.nom, categorie=b.categorie, at_mp=b.at_mp,
                      regime_vps=b.regime_vps, prime_amo_mensuelle=b.prime_amo_mensuelle)
        rub = [Rubrique(**r.model_dump()) for r in b.rubriques]
        sals.append((sal, rub, f"M{i:03d}", b.nom))
    decl = declaration_its_vps(sals, periode)
    decl.pop("lignes", None)  # allègement réponse démo
    return decl


@app.post("/v1/rupture/solde-tout-compte")
def rupture(body: RuptureIn, x_company_id: str | None = Header(default=None)):
    _company(x_company_id)
    if body.type_rupture not in TYPES_RUPTURE:
        raise HTTPException(status_code=422,
                            detail=f"type_rupture ∈ {sorted(TYPES_RUPTURE)}")
    res = solde_tout_compte(**body.model_dump())
    res.pop("detail_fiscal", None)
    return res


# ─────────────── Smoke test (sans serveur) ───────────────
if __name__ == "__main__":
    from fastapi.testclient import TestClient
    c = TestClient(app)
    H = {"X-Company-Id": "demo-001"}
    ok = 0

    r = c.get("/health"); assert r.status_code == 200; ok += 1
    r = c.get("/v1/regulatory/rates", params={"at": "2026-01-01"}, headers=H)
    assert r.json()["rates"]["taux_pension_sal"] == 0.036; ok += 1
    # multi-tenant : sans en-tête → 400
    r = c.get("/v1/regulatory/rates", params={"at": "2026-01-01"})
    assert r.status_code == 400; ok += 1
    # calcul ST-03 via API
    r = c.post("/v1/payroll/calculate", headers=H, json={
        "nom": "A", "at_mp": 0.02, "periode": "2026-01-01",
        "rubriques": [{"libelle": "Base", "montant": 150000},
                      {"libelle": "Prime", "montant": 30000},
                      {"libelle": "Transport", "montant": 20000, "soumis_cnss": False}]})
    b = r.json()["bulletin"]
    assert b["net"] == 177020 and b["assiette_cnss"] == 180000, b; ok += 1
    # déclaration ITS/VPS
    r = c.post("/v1/declarations/its-vps", headers=H, json=[
        {"nom": "A", "periode": "2026-01-01",
         "rubriques": [{"libelle": "Base", "montant": 600000}]}])
    assert r.json()["total_its"] == 101500; ok += 1
    # solde de tout compte
    r = c.post("/v1/rupture/solde-tout-compte", headers=H, json={
        "type_rupture": "licenciement", "salaire_mensuel": 200000,
        "salaire_moyen_12m": 200000, "anciennete_ans": 8,
        "jours_travailles_dernier_mois": 20, "jours_conges_acquis_non_pris": 10,
        "salaires_12m_pour_conges": 2400000, "preavis_indemnite": 200000})
    assert r.json()["net_estime"] == 860735, r.json(); ok += 1

    print(f"API smoke test : {ok}/6 OK — endpoints branchés sur le moteur testé.")
