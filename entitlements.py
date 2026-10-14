"""
Entitlements — limites & quotas par plan d'abonnement (migration 009 : plan.limites jsonb).

Résout le plan de l'abonné (workspace) d'une société et vérifie les quotas (ex. nombre de
salariés) avant une création. Les limites sont des données (jsonb), jamais codées en dur.
"""
from __future__ import annotations


class QuotaError(Exception):
    """Quota du plan atteint — l'action est refusée (proposer un plan supérieur)."""


def plan_limits_for_company(conn, company_id: str) -> dict:
    row = conn.execute(
        "SELECT p.limites FROM company c "
        "JOIN subscription s ON s.workspace_id = c.workspace_id "
        "JOIN plan p ON p.id = s.plan_id WHERE c.id = %s", (company_id,)).fetchone()
    return row[0] if (row and row[0]) else {}


def _workspace_of_company(conn, company_id: str):
    r = conn.execute("SELECT workspace_id FROM company WHERE id=%s", (company_id,)).fetchone()
    return r[0] if r else None


def active_employee_count(conn, workspace_id) -> int:
    r = conn.execute(
        "SELECT count(*) FROM employee e JOIN company c ON c.id = e.company_id "
        "WHERE c.workspace_id = %s AND e.deleted_at IS NULL", (workspace_id,)).fetchone()
    return int(r[0]) if r else 0


def check_can_add_employee(conn, company_id: str) -> None:
    """Lève QuotaError si le plan de l'abonné interdit un salarié de plus."""
    limits = plan_limits_for_company(conn, company_id)
    max_sal = limits.get("max_salaries")
    if max_sal is None:
        return
    ws = _workspace_of_company(conn, company_id)
    if ws is None:
        return
    if active_employee_count(conn, ws) >= int(max_sal):
        raise QuotaError(
            f"Quota du plan atteint : {int(max_sal)} salariés maximum. "
            "Passez à un plan supérieur pour en ajouter davantage.")


def feature_enabled(conn, company_id: str, feature: str) -> bool:
    """True si la fonctionnalité est incluse dans le plan (ex. 'exports', 'declarations')."""
    limits = plan_limits_for_company(conn, company_id)
    if limits.get("all_features"):
        return True
    return bool(limits.get(feature, False))
