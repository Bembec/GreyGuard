"""Curated administrator investigation views for one GreyGuard agent."""
from __future__ import annotations

from . import main
from .database import get_administrator_audit_events, get_tool_requests


def build_agent_investigation(agent_name: str, evidence_limit: int = 100, *, org_id: str) -> dict:
    normalized = main.normalize_agent_name(agent_name)
    state = main.get_agent_state(normalized)
    try:
        identity = main.get_public_agent_identity(normalized)
    except KeyError:
        identity = None

    evidence = get_administrator_audit_events(
        agent_name=normalized, limit=max(1, min(int(evidence_limit), 200)), org_id=org_id
    )["events"]
    risk_history = [
        {
            "event_id": event["event_id"], "timestamp": event["timestamp"],
            "action": event["action"], "outcome": event["outcome"],
            "severity": event["severity"],
            "risk_added": event.get("details", {}).get("risk_added", 0),
            "risk_score": event.get("details", {}).get("risk_score", 0),
            "risk_level": event.get("details", {}).get("risk_level", "LOW"),
        }
        for event in evidence if event["event_type"] == "POLICY"
    ]
    authentication = [
        {
            "event_id": event["event_id"], "timestamp": event["timestamp"],
            "action": event["action"], "outcome": event["outcome"],
            "severity": event["severity"], "summary": event["summary"],
        }
        for event in evidence if event["event_type"] == "AUTHENTICATION"
    ]
    requests = [
        {
            "request_id": item["request_id"], "timestamp": item["timestamp"],
            "action": item["action"], "target": item["target"],
            "policy_decision": item["policy_decision"],
            "approval_status": item["approval_status"],
            "execution_status": item["execution_status"],
            "risk_added": item["risk_added"], "risk_score": item["risk_score"],
            "path": f"/requests/{item['request_id']}",
        }
        for item in get_tool_requests(agent_name=normalized, limit=200, org_id=org_id)
    ]
    return {
        "agent": {
            "agent_name": normalized,
            "agent_status": state["agent_status"],
            "risk_score": state["risk_score"],
            "risk_level": main.get_risk_level(state["risk_score"]),
            "blocked_attempts": state["blocked_attempts"],
            "identity": identity,
        },
        "risk_history": risk_history,
        "authentication_history": authentication,
        "requests": requests,
        "summary": {
            "risk_events": len(risk_history),
            "authentication_events": len(authentication),
            "requests": len(requests),
            "denied_requests": sum(item["policy_decision"] in {"BLOCK", "REFUSED"} for item in requests),
        },
    }
