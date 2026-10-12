"""
Journal d'AUDIT MÉTIER (distinct des logs techniques) - P1-01.
Chaque mutation sensible écrit dans `audit_log` : acteur, action, entité,
société, valeur avant/après. La table est append-only (trigger en base :
UPDATE/DELETE interdits). Ce module ne fait qu'insérer.
"""
from __future__ import annotations
import json
from typing import Any


def audit(conn, action: str, entite: str, company_id: str | None,
          actor: str | None = None, avant: Any = None, apres: Any = None,
          ip: str | None = None) -> None:
    """Enregistre un évènement d'audit. Ne lève jamais sur sérialisation :
    l'audit ne doit pas faire échouer la transaction métier pour une valeur non JSON."""
    def _j(v):
        if v is None:
            return None
        return json.dumps(v, default=str, sort_keys=True)
    conn.execute(
        "INSERT INTO audit_log(company_id, user_id, action, entite, avant, apres, ip) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (company_id, actor, action, entite, _j(avant), _j(apres), ip),
    )
