"""Tour de contrôle : passerelle de décaissement (sans réseau, sans mouvement réel)."""
from __future__ import annotations
import sys, os
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
os.environ.pop("FEDAPAY_SECRET_KEY", None)  # s'assurer qu'aucune clé n'est active
from payout_gateway import ExportGateway, MockGateway, FedaPayGateway, default_gateway

item = {"methode": "mobile_money", "montant": 200720, "momo_operateur": "MTN",
        "momo_numero": "+22990000001", "nom": "KOFFI Alain", "cle_idempotence": "run:emp"}
ok = 0
def check(label, cond):
    global ok; ok += 1 if cond else 0
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

# Export (défaut sûr) : aucun envoi
e = ExportGateway().send(item)
check("export → statut 'a_envoyer', pas de référence", e["statut"] == "a_envoyer" and e["reference_operateur"] is None)

# Mock : envoi simulé accepté
m = MockGateway().send(item)
check("mock → statut 'envoye' + référence MOCK-", m["statut"] == "envoye" and m["reference_operateur"].startswith("MOCK-"))

# FedaPay : construction de l'ordre (mode mtn_open, XOF, téléphone)
fp = FedaPayGateway(api_key=None)
p = fp.build_payload(item)
check("fedapay payload : mode=mtn_open", p["mode"] == "mtn_open")
check("fedapay payload : XOF + montant entier", p["currency"]["iso"] == "XOF" and p["amount"] == 200720)
check("fedapay payload : téléphone bj", p["customer"]["phone_number"]["number"] == "+22990000001")
check("fedapay Moov → mode moov", FedaPayGateway().build_payload({**item, "momo_operateur": "MOOV"})["mode"] == "moov")

# FedaPay sans clé → repli export (AUCUN appel réseau, aucun mouvement)
s = fp.send(item)
check("fedapay sans clé → repli 'a_envoyer' (pas d'appel réseau)", s["statut"] == "a_envoyer")

# default_gateway sans env → Export
check("default_gateway sans clé → ExportGateway", default_gateway().canal == "export")

print(f"\nPasserelle de décaissement : {ok}/8 PASS")
if ok != 8:
    raise SystemExit(1)
