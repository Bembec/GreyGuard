"""Redacted administrator investigation bundle for controlled tool requests."""
from __future__ import annotations

from typing import Any

from .database import get_tool_request_details


SENSITIVE_KEYS = {"credential", "password", "secret", "token", "api_key", "authorization"}


def redact_evidence(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if any(marker in key.lower() for marker in SENSITIVE_KEYS) else redact_evidence(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_evidence(item) for item in value]
    return value


def explain_decision(decision: str, approval: str, execution: str) -> str:
    if decision in {"BLOCK", "REFUSED"}:
        return "GreyGuard prevented execution because the active policy does not permit this action."
    if decision == "ASK" and approval == "PENDING":
        return "The policy requires explicit human approval before this request may execute."
    if approval == "DENIED":
        return "An authorized reviewer denied this request, so execution remained blocked."
    if execution == "SUCCEEDED":
        return "The request satisfied identity, scope, policy and approval controls before contained execution."
    return "The request remains governed by its recorded policy, approval and execution states."


def build_request_investigation(request_id: str) -> dict | None:
    details = get_tool_request_details(request_id)
    if details is None:
        return None
    safe = redact_evidence(details)
    request = {
        key: safe.get(key) for key in (
            "request_id", "agent_name", "timestamp", "updated_at", "action", "target",
            "dry_run", "policy_decision", "approval_status", "execution_status",
            "risk_added", "risk_score", "executed_at",
        )
    }
    timeline = [{"type": "REQUEST", "timestamp": request["timestamp"], "status": "SUBMITTED", "actor": request["agent_name"], "detail": f"Requested {request['action']} for {request['target'] or 'unspecified target'}."}]
    timeline += [{"type": "APPROVAL", "timestamp": event["timestamp"], "status": event["decision"], "actor": event["actor"], "detail": event.get("note") or "No reviewer note."} for event in safe.get("approval_events", [])]
    timeline += [{"type": "EXECUTION", "timestamp": event["timestamp"], "status": event["execution_status"], "actor": "GreyGuard sandbox", "detail": "Controlled execution evidence recorded."} for event in safe.get("execution_events", [])]
    timeline.sort(key=lambda item: item["timestamp"] or "")
    return {
        "request": request,
        "decision_explanation": explain_decision(request["policy_decision"], request["approval_status"], request["execution_status"]),
        "timeline": timeline,
        "redacted_evidence": {
            "payload": safe.get("payload", {}), "result": safe.get("result", {}),
            "approval_events": safe.get("approval_events", []), "execution_events": safe.get("execution_events", []),
        },
        "correlations": {"agent_path": f"/agents/{request['agent_name']}", "request_id": request_id},
    }
