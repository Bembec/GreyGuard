"""Decision explainability (P7.5 item 6, design approved 2026-10-16).

One explanation per tool request, built from its exact decision record when there is one, and
otherwise labelled inferred. Every sentence here is fixed text chosen by rule type and outcome:
nothing is generated, and there is no confidence score, because decisions are deterministic.

"Why is this unavailable?" reasons are built only from the viewer's own role and permissions. They
never name another record, person or org, and never reveal withheld content.
"""
from __future__ import annotations

from typing import Any

from . import decision_provenance
from .control_graph import _inferred_version, _policy_versions, _short
from .database import get_tool_request_details

REASONS = {
    ("PERMISSION", "ALLOW"): "Allowed because policy {version} allows {action} for this agent.",
    ("PERMISSION", "ASK"): "Held for human approval because policy {version} requires a reviewer for {action}.",
    ("PERMISSION", "BLOCK"): "Blocked because policy {version} does not allow {action}.",
    ("DEFAULT_RULE", "BLOCK"): "Blocked because {action} is not listed in policy {version}, and anything not listed is blocked.",
    ("EMERGENCY_CONTROL", "REFUSED"): "Refused because an emergency control was on: {rule}.",
    ("AGENT_STATE", "REFUSED"): "Refused because the agent was suspended when it asked.",
}

INFERRED_REASONS = {
    "ALLOW": "Allowed. This request predates exact decision records, so the rule that matched was not recorded.",
    "ASK": "Held for human approval. This request predates exact decision records, so the rule that matched was not recorded.",
    "BLOCK": "Blocked. This request predates exact decision records, so the rule that matched was not recorded.",
    "REFUSED": "Refused. This request predates exact decision records; an emergency control or a suspension refuses requests before policy is consulted.",
}

AUTHENTICATION = {
    "AGENT_KEY": "The agent authenticated with its agent key.",
    "CLIENT_CERTIFICATE": "The agent authenticated with a client certificate verified at the gateway.",
    "NOT_RECORDED": "Not recorded: this decision was not made through an authenticated API call (for example the CLI).",
    None: "Not recorded: this request predates authentication being recorded with decisions.",
}

LIMITATIONS = {
    "prompt": "GreyGuard sees the tool request an agent makes, not the prompt or reasoning that led to it.",
    "inferred": "The policy version is inferred from publication times. A staged rollout, or a publication at the same moment, can make it wrong.",
    "redaction": "Values that look like secrets are redacted from evidence; redaction cannot recognise every secret format.",
    "policy_changed": "The stored policy version has changed since this decision. The decision record keeps what actually decided.",
    "unsupported": "This tool is not executed by GreyGuard's gateway, so there is no execution evidence for it.",
}


def _has(viewer: dict[str, Any], permission: str) -> bool:
    return permission in set(viewer.get("permissions") or [])


def _role(viewer: dict[str, Any]) -> str:
    return str(viewer.get("role") or "your role").replace("_", " ").title().replace("Platform Admin", "Platform Administrator")


def next_step(record_type: str | None, outcome: str, approval: str, execution: str, viewer: dict[str, Any]) -> dict[str, Any]:
    """The deterministic recommended next step, with where to take it and whether the viewer can."""
    if outcome == "ASK" and approval == "PENDING":
        if _has(viewer, "approval:manage"):
            return {"text": "Review it in Approvals.", "path": "/approvals", "available": True}
        return {"text": "Waiting for a reviewer with approval rights.", "path": None, "available": False,
                "unavailable_reason": f"Your role, {_role(viewer)}, can view approvals but not decide them."}
    if outcome == "BLOCK" and record_type == "DEFAULT_RULE":
        return {"text": "This action is not in the policy. Add it explicitly if it should be allowed or asked.", "path": "/policies",
                "available": _has(viewer, "approval:manage")}
    if outcome == "BLOCK":
        return {"text": "If this action is legitimate for this agent, propose a policy change in Policies.", "path": "/policies",
                "available": _has(viewer, "approval:manage")}
    if outcome == "REFUSED" and record_type == "EMERGENCY_CONTROL":
        return {"text": "An emergency control is on. It stays on until someone with policy rights turns it off.", "path": "/policies",
                "available": _has(viewer, "approval:manage")}
    if outcome == "REFUSED":
        return {"text": "Investigate the agent, then reset it from its page if it is safe.", "path": None,
                "available": _has(viewer, "identity:manage")}
    if approval == "DENIED":
        return {"text": "A reviewer denied it. No action is needed unless the denial was a mistake.", "path": None, "available": True}
    if execution in ("FAILED",):
        return {"text": "The policy allowed it; the tool failed. See the execution result below.", "path": None, "available": True}
    return {"text": "No action needed.", "path": None, "available": True}


def _with_reason(step: dict[str, Any], viewer: dict[str, Any]) -> dict[str, Any]:
    """Every unavailable step says why, from the viewer's own role only."""
    if not step["available"] and "unavailable_reason" not in step:
        step["unavailable_reason"] = f"Your role, {_role(viewer)}, can view this but cannot take this step."
    return step


def build_explanation(request_id: str, *, org_id: str, viewer: dict[str, Any],
                      details: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The explanation card for one request in the viewer's org, or None (the caller answers 404).

    `details`, when the caller already read them (org-scoped), saves reading the request twice."""
    details = details if details is not None else get_tool_request_details(request_id, org_id=org_id)
    if details is None:
        return None
    record = decision_provenance.get_decision_records([request_id], org_id=org_id).get(request_id)
    outcome = details["policy_decision"]
    approval = details["approval_status"]
    execution = details["execution_status"]
    action = details["action"]
    limitations = ["prompt", "redaction"]
    versions = _policy_versions(org_id)

    if record:
        version = versions.get(record["policy_version_id"]) if record["policy_version_id"] else None
        version_label = f"v{record['policy_version_number']}" if record["policy_version_number"] is not None else "the built-in defaults"
        template = REASONS.get((record["rule_type"], record["outcome"]),
                               "Decided {outcome} by {rule}.")
        reason = template.format(version=version_label, action=action, rule=record["rule_name"], outcome=record["outcome"])
        policy_matches = (version is not None and decision_provenance.policy_fingerprint(version) == record["policy_fingerprint"]) \
            if record["policy_version_id"] else None
        if policy_matches is False:
            limitations.append("policy_changed")
        policy = {
            "basis": "recorded",
            "version_id": record["policy_version_id"],
            "version_number": record["policy_version_number"],
            "source": record["policy_source"],
            "published_at": version.get("published_at") if version else None,
            "unchanged_since_decision": policy_matches,
        }
        rule = {"id": record["matched_rule_id"], "name": record["rule_name"], "type": record["rule_type"], "snapshot": record["rule_snapshot"]}
        authentication = record.get("authentication_method")
        integrity = {"record_intact": decision_provenance.record_intact(record), "policy_unchanged": policy_matches}
        record_type = record["rule_type"]
    else:
        inferred = _inferred_version(versions, details["timestamp"])
        reason = INFERRED_REASONS.get(outcome, f"Decided {outcome}. This request predates exact decision records.")
        limitations.append("inferred")
        policy = {
            "basis": "inferred",
            "version_id": inferred["policy_id"] if inferred else None,
            "version_number": inferred["version_number"] if inferred else None,
            "source": None,
            "published_at": inferred.get("published_at") if inferred else None,
            "unchanged_since_decision": None,
        }
        rule = None
        authentication = None
        integrity = {"record_intact": None, "policy_unchanged": None}
        record_type = None

    from .tool_gateway import get_supported_tools
    if action not in get_supported_tools():
        limitations.append("unsupported")

    approvals = [
        {"decision": event["decision"], "actor": event["actor"], "timestamp": event["timestamp"]}
        for event in details.get("approval_events", [])
    ]
    if outcome == "ASK":
        approval_path = {"required": True, "status": approval, "reviews": approvals}
    else:
        approval_path = {"required": False, "status": approval, "reviews": approvals,
                         "summary": "No approval needed: the decision did not ask for one."}

    return {
        "request_id": request_id,
        "decision": outcome,
        "basis": "recorded" if record else "inferred",
        "reason": reason,
        "policy": policy,
        "matched_rule": rule,
        "authentication": {"method": authentication, "summary": AUTHENTICATION.get(authentication, AUTHENTICATION[None])},
        "requested": {"action": action, "target": _short(details.get("target")), "dry_run": bool(details.get("dry_run")),
                      "agent_name": details["agent_name"], "decided_at": details["timestamp"]},
        "approval_path": approval_path,
        "next_step": _with_reason(next_step(record_type, outcome, approval, execution, viewer), viewer),
        "limitations": [{"id": key, "text": LIMITATIONS[key]} for key in limitations],
        "integrity": integrity,
        "why_you_see_this": "You see this because your role can read your organization's evidence.",
    }
