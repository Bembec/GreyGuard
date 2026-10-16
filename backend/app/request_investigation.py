"""Redacted administrator investigation bundle for controlled tool requests."""
from __future__ import annotations

import re
from typing import Any

from .database import get_tool_request_details


SENSITIVE_KEYS = {"credential", "password", "secret", "token", "api_key", "authorization"}
REDACTED_KEY = "[REDACTED]"
REDACTED_VALUE = "[REDACTED: looks like a secret]"

# Values that look like secrets, whatever their key is called (owner decision, 2026-10-16):
# redacted for every role, and labelled. Recognisable formats only; the explanation card states
# that redaction cannot recognise every secret.
SECRET_VALUE_PATTERNS = [
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),            # JSON Web Token
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}"),                                      # API secret keys
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}"),                 # GitHub tokens
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),                                       # Slack tokens
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),                                          # AWS access key ids
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),                                              # Google API keys
    re.compile(r"\b(?:gga|ggsa|gg)_[A-Za-z0-9_-]{16,}"),                                    # GreyGuard credentials
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"),                                  # bearer tokens
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),                                      # private keys
]


def looks_like_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_VALUE_PATTERNS)


def redact_evidence(value: Any, counter: list[int] | None = None) -> Any:
    """Redact by key name, and by value for anything that looks like a secret. `counter`, when
    given, counts the redactions so the page can say how many were made."""
    counter = counter if counter is not None else [0]
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if any(marker in key.lower() for marker in SENSITIVE_KEYS):
                counter[0] += 1
                redacted[key] = REDACTED_KEY
            else:
                redacted[key] = redact_evidence(item, counter)
        return redacted
    if isinstance(value, list):
        return [redact_evidence(item, counter) for item in value]
    if isinstance(value, str) and looks_like_secret(value):
        counter[0] += 1
        return REDACTED_VALUE
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


def build_request_investigation(request_id: str, *, org_id: str, viewer: dict | None = None) -> dict | None:
    details = get_tool_request_details(request_id, org_id=org_id)
    if details is None:
        return None
    redactions = [0]
    safe = redact_evidence(details, redactions)
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
    from .decision_explanation import build_explanation

    explanation = build_explanation(request_id, org_id=org_id, viewer=viewer or {}, details=details)
    return {
        "request": request,
        # Kept for older clients: now the exact explanation's reason, not a guess from statuses.
        "decision_explanation": explanation["reason"] if explanation else explain_decision(
            request["policy_decision"], request["approval_status"], request["execution_status"]),
        "explanation": explanation,
        "redactions": {"count": redactions[0], "note": "Keys named like secrets, and values that look like secrets, are redacted for every role."},
        "timeline": timeline,
        "redacted_evidence": {
            "payload": safe.get("payload", {}), "result": safe.get("result", {}),
            "approval_events": safe.get("approval_events", []), "execution_events": safe.get("execution_events", []),
        },
        "correlations": {"agent_path": f"/agents/{request['agent_name']}", "request_id": request_id},
    }
