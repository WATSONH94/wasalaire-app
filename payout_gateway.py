"""
Passerelle de décaissement — abstraction multi-fournisseur (mobile money).

- **ExportGateway** (défaut sûr) : ne fait AUCUN appel réseau ; l'ordre reste « à envoyer »
  (repli : dépôt/fichier manuel). C'est le défaut tant qu'aucune clé n'est configurée.
- **FedaPayGateway** : construit l'ordre de payout FedaPay (mode `mtn_open` MTN / `moov` Moov)
  et ne l'émet que si une **clé API** est fournie. ⚠️ Mouvement d'argent réel — jamais en test.
- **MockGateway** : statuts simulés déterministes, pour les tours de contrôle (sans réseau).

Chaque `send(item)` reçoit un dict {methode, montant, momo_operateur, momo_numero,
cle_idempotence, nom} et renvoie {statut, reference_operateur, accuse}.
Seul `mobile_money` transite par la passerelle ; virement/espèces/chèque restent manuels.
"""
from __future__ import annotations
import json, os, urllib.request, urllib.error

# Mapping opérateur → mode FedaPay (docs.fedapay.com — Payouts)
FEDAPAY_MODE = {"MTN": "mtn_open", "MOOV": "moov"}
FEDAPAY_BASE = os.environ.get("FEDAPAY_BASE", "https://api.fedapay.com/v1")


class PayoutGateway:
    canal = "base"
    def send(self, item: dict) -> dict:
        raise NotImplementedError


class ExportGateway(PayoutGateway):
    """Défaut sûr : aucun envoi ; l'ordre est produit pour dépôt manuel/fichier."""
    canal = "export"
    def send(self, item: dict) -> dict:
        return {"statut": "a_envoyer", "reference_operateur": None,
                "accuse": {"canal": "export", "note": "ordre à déposer (aucun connecteur actif)"}}


class MockGateway(PayoutGateway):
    """Simule un envoi accepté (tests). Déterministe, sans réseau."""
    canal = "mock"
    def send(self, item: dict) -> dict:
        return {"statut": "envoye",
                "reference_operateur": f"MOCK-{item['cle_idempotence']}",
                "accuse": {"canal": "mock", "mode": FEDAPAY_MODE.get(item.get("momo_operateur"))}}


class FedaPayGateway(PayoutGateway):
    """Connecteur FedaPay Payouts (MTN/Moov Bénin). N'émet un appel que si `api_key`."""
    canal = "fedapay"
    def __init__(self, api_key: str | None = None, base_url: str = FEDAPAY_BASE):
        self.api_key = api_key or os.environ.get("FEDAPAY_SECRET_KEY")
        self.base_url = base_url

    def build_payload(self, item: dict) -> dict:
        """Ordre de payout FedaPay (à ajuster selon la version d'API en vigueur)."""
        mode = FEDAPAY_MODE.get(item.get("momo_operateur"))
        if not mode:
            raise ValueError(f"Opérateur mobile money non supporté : {item.get('momo_operateur')}")
        nom = (item.get("nom") or "Salarie").split()
        return {
            "amount": int(round(item["montant"])),
            "currency": {"iso": "XOF"},
            "mode": mode,
            "customer": {
                "firstname": nom[0],
                "lastname": " ".join(nom[1:]) or nom[0],
                "phone_number": {"number": item["momo_numero"], "country": "bj"},
            },
            "reference": item["cle_idempotence"],   # idempotence côté FedaPay
        }

    def send(self, item: dict) -> dict:
        payload = self.build_payload(item)
        if not self.api_key:
            # Pas de clé → on NE contacte PAS FedaPay ; repli export (aucun mouvement).
            return {"statut": "a_envoyer", "reference_operateur": None,
                    "accuse": {"canal": "fedapay", "note": "clé absente → repli export",
                               "payload": payload}}
        # ⚠️ Mouvement d'argent réel — exécuté uniquement avec une clé de production/sandbox valide.
        req = urllib.request.Request(
            f"{self.base_url}/payouts", method="POST",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode())
            return {"statut": "envoye",
                    "reference_operateur": str(body.get("v1/payout", {}).get("id", "")),
                    "accuse": body}
        except urllib.error.HTTPError as e:
            return {"statut": "echoue", "reference_operateur": None,
                    "accuse": {"error": e.code, "body": e.read().decode(errors="ignore")}}


def default_gateway() -> PayoutGateway:
    """Choisit la passerelle selon l'environnement (FedaPay si clé, sinon export sûr)."""
    if os.environ.get("FEDAPAY_SECRET_KEY"):
        return FedaPayGateway()
    return ExportGateway()
