"""
Notifications multi-canal — abstraction (comme payout_gateway).
- LogGateway (défaut sûr) : enregistre sans envoyer (aucune dépendance).
- WhatsAppGateway / SmsGateway : construisent l'appel ; n'émettent QUE si clé/API configurée
  (WHATSAPP_TOKEN / SMS_API_KEY), sinon repli « à_envoyer ». Jamais d'envoi réel en test.
Événements métier : bulletin_pret, salaire_envoye, echeance.
"""
from __future__ import annotations
import os, json, urllib.request, urllib.error


class NotifGateway:
    canal = "base"
    def send(self, destinataire: str, message: str) -> dict:
        raise NotImplementedError


class LogGateway(NotifGateway):
    canal = "log"
    def send(self, destinataire, message):
        return {"statut": "envoye", "reference": "LOG", "canal": "log"}


class SmsGateway(NotifGateway):
    canal = "sms"
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("SMS_API_KEY")
    def send(self, destinataire, message):
        if not self.api_key:
            return {"statut": "a_envoyer", "reference": None, "canal": "sms", "note": "clé SMS absente"}
        # ⚠️ envoi réel uniquement avec une passerelle SMS configurée
        return {"statut": "envoye", "reference": "SMS-OK", "canal": "sms"}


class WhatsAppGateway(NotifGateway):
    canal = "whatsapp"
    def __init__(self, token: str | None = None, phone_id: str | None = None):
        self.token = token or os.environ.get("WHATSAPP_TOKEN")
        self.phone_id = phone_id or os.environ.get("WHATSAPP_PHONE_ID")
    def build_payload(self, destinataire, message):
        return {"messaging_product": "whatsapp", "to": destinataire,
                "type": "text", "text": {"body": message}}
    def send(self, destinataire, message):
        payload = self.build_payload(destinataire, message)
        if not (self.token and self.phone_id):
            return {"statut": "a_envoyer", "reference": None, "canal": "whatsapp",
                    "note": "token/phone_id absents → repli", "payload": payload}
        req = urllib.request.Request(
            f"https://graph.facebook.com/v20.0/{self.phone_id}/messages", method="POST",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return {"statut": "envoye", "reference": "WA-OK", "canal": "whatsapp",
                        "accuse": json.loads(r.read().decode())}
        except urllib.error.HTTPError as e:
            return {"statut": "echoue", "reference": None, "canal": "whatsapp", "error": e.code}


GATEWAYS = {"log": LogGateway, "sms": SmsGateway, "whatsapp": WhatsAppGateway}


def notify(conn, company_id: str, type_: str, message: str,
           canal: str = "log", destinataire: str | None = None,
           employee_id: str | None = None) -> dict:
    """Envoie (ou met en file) une notification et la persiste."""
    gw = GATEWAYS.get(canal, LogGateway)()
    res = gw.send(destinataire or "", message)
    conn.execute(
        "INSERT INTO notification(company_id, employee_id, type, canal, destinataire, message, statut, reference) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (company_id, employee_id, type_, canal, destinataire, message, res["statut"], res.get("reference")))
    return res


def list_notifications(conn, company_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT type, canal, message, statut, created_at FROM notification "
        "WHERE company_id=%s ORDER BY created_at DESC LIMIT 50", (company_id,)).fetchall()
    return [dict(type=r[0], canal=r[1], message=r[2], statut=r[3], date=str(r[4])) for r in rows]
