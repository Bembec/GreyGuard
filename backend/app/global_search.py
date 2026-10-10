"""Permission-aware search across GreyGuard control-plane evidence."""
from __future__ import annotations

import json
from typing import Any

from . import main
from .alerts import get_alerts
from .database import get_administrator_audit_events, get_tool_requests


def _matches(query: str, *values: Any) -> bool:
    searchable = " ".join(
        json.dumps(value, sort_keys=True, default=str) if isinstance(value, (dict, list))
        else str(value or "")
        for value in values
    ).lower()
    return query in searchable


def search_control_plane(query: str, permissions: list[str], limit: int = 30,
                         org_id: str = "org_default") -> dict:
    """Return bounded results only from sources the operator may read."""
    normalized = str(query).strip().lower()
    safe_limit = max(1, min(int(limit), 50))
    if len(normalized) < 2 or "read" not in set(permissions):
        return {"query": query.strip(), "results": [], "count": 0}

    results: list[dict] = []
    owners: dict[str, str] = {}

    def owned(agent_name) -> bool:
        # Agents are org-scoped by identity (tool requests and audit evidence are filtered in SQL).
        # Alerts are not attributed to an org yet (a later P2.2 agent batch).
        name = str(agent_name or "")
        if name not in owners:
            owners[name] = main.agent_org_id(name)
        return owners[name] == org_id

    for name, state in sorted(main.agent_states.items()):
        if not owned(name):
            continue
        try:
            identity = main.get_public_agent_identity(name)
        except KeyError:
            identity = None
        if _matches(normalized, name, state, identity):
            results.append({
                "kind": "AGENT", "id": name, "title": name,
                "summary": f"{state.get('agent_status', 'UNKNOWN')} · risk {state.get('risk_score', 0)}",
                "path": f"/agents/{name}",
            })

    requests = get_tool_requests(limit=200, org_id=org_id)
    for item in requests:
        if not _matches(normalized, item.get("request_id"), item.get("agent_name"), item.get("action"), item.get("target"), item.get("approval_status"), item.get("execution_status")):
            continue
        kind = "APPROVAL" if item.get("approval_status") in {"PENDING", "APPROVED", "DENIED"} else "REQUEST"
        results.append({
            "kind": kind, "id": item.get("request_id"),
            "title": f"{item.get('action', 'Tool request')} · {item.get('agent_name', 'unknown agent')}",
            "summary": f"{item.get('approval_status', 'UNKNOWN')} · {item.get('execution_status', 'NOT_STARTED')}",
            "path": f"/requests/{item.get('request_id')}",
        })

    for alert in get_alerts(limit=200)["alerts"]:
        if _matches(normalized, alert.get("alert_id"), alert.get("title"), alert.get("summary"), alert.get("agent_name"), alert.get("status"), alert.get("severity")):
            results.append({
                "kind": "ALERT", "id": alert.get("alert_id"),
                "title": alert.get("title", "Security alert"),
                "summary": f"{alert.get('severity', 'UNKNOWN')} · {alert.get('status', 'OPEN')}",
                "path": f"/incidents?alert={alert.get('alert_id')}",
            })

    audit = get_administrator_audit_events(limit=200, org_id=org_id)
    audit_events = audit.get("events", audit) if isinstance(audit, dict) else audit
    for event in audit_events:
        if _matches(normalized, event.get("event_id"), event.get("event_type"), event.get("agent_name"), event.get("action"), event.get("outcome"), event.get("summary")):
            results.append({
                "kind": "AUDIT", "id": event.get("event_id"),
                "title": event.get("summary") or event.get("event_type", "Audit evidence"),
                "summary": f"{event.get('outcome', 'RECORDED')} · {event.get('agent_name') or 'System'}",
                "path": f"/audit?event={event.get('event_id')}",
            })

    priority = {"ALERT": 0, "APPROVAL": 1, "AGENT": 2, "REQUEST": 3, "AUDIT": 4}
    results.sort(key=lambda result: (priority.get(result["kind"], 9), result["title"].lower()))
    bounded = results[:safe_limit]
    return {"query": query.strip(), "results": bounded, "count": len(bounded)}
