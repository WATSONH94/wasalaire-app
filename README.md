# Prototype — Moteur de paie (exécutable)

Prototype **fonctionnel** du moteur de calcul, qui matérialise la base réglementaire (dossiers 02-13) et se **valide sur les scénarios de test** (dossier 22).

## Contenu
- `moteur_paie.py` — le moteur **paramétrable** : règles = **données versionnées** (taux, barème ITS, ORTB, AMO) avec `date_effet`. Gère les **3 assiettes distinctes** (CNSS / ITS / VPS), la base ITS brute (conforme CGI), l'AMO (à partir du 29/10/2026), la redevance ORTB, le contrôle SMIG.
- `conges_maternite.py` — **congés payés** (acquisition Art. 158, majoration ancienneté/enfants, plafond 30 j), **allocation de congé** (Art. 165, exclusions primes de rendement/frais), **congé maternité** (14 sem., maintien 100 % + remboursement CNSS 50 %), **indemnités de rupture** (licenciement CCGT Art. 36 : 30/35/40 ; départ retraite Art. 57 : min 3 mois).
- `export_cnss.py` — **générateur de la liste nominative CNSS** (.xlsx, colonnes A-M + ligne récapitulative), destiné à `carriere@cnss.bj`, avec **contrôle de cohérence** (Σ bruts = masse récap). Dégradation en CSV si openpyxl absent.
- `bulletin.py` — **bulletin de paie PDF** (reportlab) branché sur le moteur : blocs employeur/salarié, gains + marqueurs d'assiette, retenues salariales, net à payer, volet patronal, coût employeur.
- `comptabilite.py` — **générateur d'écritures SYSCOHADA** (AUDCIF 2017) : transforme un bulletin en écriture de journal **équilibrée** (a) brut+retenues, (b) charges patronales, (c) paiement ; **provision congés** de clôture (4281/4382) ; comptes officiels (6611/6641/641/4311/4313/4318/4472/4421/422/521) ; **export CSV** vers logiciel comptable tiers.
- `declaration_fiscale.py` — **déclaration fiscale ITS/VPS** (CGI Art. 129/195) : récapitulatif par salarié + agrégats, **échéance le 10 du mois suivant**, montant à reverser DGI, **export CSV** vers e-services.
- `remunerations_speciales.py` — **heures supplémentaires** (Art. 147 : 12/35/50/50/100 %, base horaire ÷173,33), **prorata** entrée/sortie (défaut ÷30), **ITS sur rémunérations exceptionnelles** (Art. 126 : salaire moyen 12 mois + abattement 25 % IFC/départ).
- `saisies.py` — **saisie-arrêt/cession** : assiette (Art. 219), barème progressif des quotités (Décret 55-972) — ⚠️ **seuils 1955 marqués « à confirmer », jamais figés** ; procédure = AUPSRVE 2023.
- `comptabilite.provision_ifc` — **provision IFC** (unités de crédit projetées, compte 196) ; hypothèses actuarielles = **paramètres de politique**, non inventées.
- `solde_tout_compte.py` — **intégrateur de rupture** (workflow 3) : assemble prorata + congés non pris + indemnité de rupture + fiscalité Art. 126 en un solde de tout compte de bout en bout.
- `api_demo.py` — **API REST runnable** (FastAPI) exposant le moteur testé : `/v1/payroll/calculate`, `/v1/declarations/its-vps`, `/v1/rupture/solde-tout-compte`, `/v1/regulatory/rates` ; multi-tenant `X-Company-Id` obligatoire ; sert aussi le frontend à `/`. **Ne réimplémente aucune règle** (appelle les modules validés). Smoke test intégré 6/6.
- `frontend_demo.html` — **interface mobile-first** aux couleurs **WaSalaire** (charte v1.1 : logo, indigo/teal, Plus Jakarta Sans, favicon) qui appelle l'API et affiche le bulletin avec les 3 assiettes. Servie par l'API à `http://127.0.0.1:8000/` (même origine → `fetch` OK). Boucle complète `MOTEUR → API → INTERFACE` validée en direct (net 164 630 pour l'exemple des 3 assiettes).
- `assets/` — logos WaSalaire (blanc/couleur), favicon, app icon (issus de la charte), servis par l'API à `/assets`. Le **bulletin PDF** porte aussi l'identité WaSalaire (logo, en-têtes indigo, net teal).
- `test_scenarios.py` — recette du moteur : exécute les scénarios ST-xx et **vérifie les résultats attendus**.
- `test_modules.py` — recette des modules (congés, maternité, rupture, CNSS, bulletin, compta, déclaration fiscale, provisions, HS, prorata, Art. 126, saisies, IFC, solde de tout compte) : **47 assertions**, chacune ancrée sur un article/compte.

## Lancer
```bash
python test_scenarios.py     # recette moteur (11 OK)
python test_modules.py       # recette modules (40 OK)
python moteur_paie.py        # bulletin de démonstration (console)
python conges_maternite.py   # démo congés/maternité/rupture
python export_cnss.py        # génère liste_nominative_cnss_demo.xlsx
python bulletin.py           # génère bulletin_demo.pdf
python comptabilite.py       # écritures SYSCOHADA + provision congés + CSV
python declaration_fiscale.py # déclaration ITS/VPS + declaration_its_vps_demo.csv
python remunerations_speciales.py # HS, prorata, Art. 126
python saisies.py            # quotité saisissable (⚠️ seuils 1955 à confirmer)
python solde_tout_compte.py  # solde de tout compte (intégration rupture)
python api_demo.py           # smoke test API (6/6, sans serveur)
uvicorn api_demo:app --reload # lance l'API → http://127.0.0.1:8000/docs
                              #   · interface : http://127.0.0.1:8000/
                              #   · (si le port 8000 est pris : --port 8078)
```
(Python 3.10+, dépendances `reportlab` + `openpyxl` + `fastapi`/`uvicorn` pour l'API. Console Windows : `set PYTHONIOENCODING=utf-8` pour l'affichage accentué — sans effet sur les calculs.)

## Résultat de recette (dernière exécution)
**11 scénarios / 11 OK / 0 écart** :
| Scénario | brut | CNSS sal | ITS | NET | coût employeur |
|---|--:|--:|--:|--:|--:|
| ST-01 SMIG | 52 000 | 1 872 | 0 | **50 128** | 63 128 |
| ST-02 élevé | 1 000 000 | 36 000 | 221 500 | **742 500** | 1 214 000 |
| ST-03 primes+transport (3 assiettes) | 200 000 | 6 480 | 16 500 | **177 020** | 239 320 |
| ST-04 heures sup (8h@12%+2h@35%) | 184 990 | 6 660 | 14 248 | **164 082** | 224 578 |
| ST-05 absence non rémunérée | 172 727 | 6 218 | 12 409 | **154 100** | — |
| ST-13 avantages en nature | 490 000 | 17 640 | 69 600 | **402 760** | 594 860 |
| ST-17 versioning (sept. avant AMO) | 200 000 | 7 200 | 16 500 | **176 300** | 242 800 |
| ST-14 cadre | 600 000 | 21 600 | 101 500 | **476 900** | 728 400 |
| ST-15 non-cadre | 90 000 | 3 240 | 3 000 | **83 760** | 109 260 |
| ST-19 ORTB (juin) | 200 000 | 7 200 | 19 500 | **173 300** | 242 800 |
| ST-20 AMO (nov. 2026) | 200 000 | 7 200 | 16 500 | **175 467** | 246 133 |

→ **Le moteur reproduit exactement les résultats attendus** : la base réglementaire est cohérente **et implémentable**.

**Recette des modules** — `python test_modules.py` : **40 OK / 0 écart** (congés 26/30/28 j ; allocation congé 200 000 / 190 000 ; maternité 14 sem. + remb. CNSS 50 % ; licenciement 510 000 / 810 000 ; retraite min 3 mois = 600 000 ; export CNSS masse 434 990 ; bulletin PDF 3 assiettes ; **compta : écritures équilibrées reproduisant l'exemple du dossier 09** ; déclaration ITS/VPS 112 750 / 30 600 échéance le 10 ; provision congés 236 800 ; **HS 11 660 = ST-04** ; prorata 100 000 ; **Art. 126 ITS exceptionnel 47 438** avec abattement 25 % ; saisie avec avertissement seuils 1955 ; provision IFC équilibrée, droits 50 %).

**Recette totale : 58/58 (11 scénarios + 47 modules), 0 écart.** (dont solde de tout compte : brut 926 666, ITS Art.126 65 931, net 860 735 ; démission sans indemnité de licenciement ; ST-17 versioning : AMO absente en septembre, présente en novembre).

## Correspondance règles ↔ code
| Règle (dossier 13) | Implémentation |
|---|---|
| RG-CNSS-001/002 | `assiette_cnss × taux` (pension/PF/AT-MP) |
| RG-ITS-001/002/003 | `bareme_its(base_its)` + ORTB ; base brute (`its_base_deduit_cnss=False`) |
| RG-VPS-001 | `base_vps × taux_vps` (4 %/2 %) |
| RG-AMO-001 | `prime × part` (≥80 %/≤20 %) à partir du 29/10/2026 |
| 3 assiettes | flags `soumis_cnss/its/vps` par `Rubrique` (ST-03 : transport hors CNSS) |
| Versioning | `PARAMS` datés + `param(nom, date)` |
| RG-CONGE-001 (Art. 158/165) | `droit_conges_annuels` + `allocation_conge` |
| RG-MATERNITE-001 (Art. 170) | `conge_maternite` (100 % + remb. CNSS 50 %) |
| RG-RUPT-002 (CCGT Art. 36/57) | `indemnite_licenciement` / `indemnite_depart_retraite` |
| Déclaration sociale | `export_cnss.generer_liste_nominative` (colonnes A-M) |
| Déclaration fiscale (Art. 129/195) | `declaration_fiscale.declaration_its_vps` |
| Écritures + provision congés | `comptabilite.ecriture_paie` / `provision_conges` |
| Bulletin (Art. 224) | `bulletin.generer_bulletin_pdf` |
| RG-HS-001 (Art. 147) | `remunerations_speciales.heures_supplementaires` |
| RG-PRORATA-001 | `remunerations_speciales.prorata` |
| Art. 126 (exceptionnel) | `remunerations_speciales.its_remuneration_exceptionnelle` |
| Saisies (Art. 219 + 55-972) | `saisies.quotite_saisissable` (seuils à confirmer) |
| IFC (SYSCOHADA Ch.21) | `comptabilite.provision_ifc` (compte 196) |
| Solde de tout compte (workflow 3) | `solde_tout_compte.solde_tout_compte` |

## Limites (prototype)
- Reste au niveau applicatif (hors calcul) : écrans, workflow d'états, persistance, API, dépôt e-services réel.
- Paramètres **à confirmer** avant production : montant prime AMO, **seuils saisie 1955**, forfait transport côté CNSS, base ITS (contresignature DGI), articulation exacte Art. 126 (doctrine DGI).
- ⚠️ **Prototype pédagogique** — ne pas utiliser en production sans validation experte.
