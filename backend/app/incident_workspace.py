"""The investigation workspace for one incident (P7.5 item 5, design approved 2026-10-16).

One read, bounded and scoped:
- **Same visibility as /alerts/{id}.** An incident the caller may not see is the same 404 as a
  missing one (alerts._visibility: the caller's org, plus install-level ones for operators).
- **Everything else is read under the incident's org.** Its request, explanation, agent, timeline
  and related incidents; nothing is fetched by id alone.
- **Read-only.** It never writes: no alert derivation, no seeding.
- **Sections fail on their own.** A section that cannot be built reports its own error, and the
  rest of the workspace still loads.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import db_compat as sqlite3
from . import organizations
from .alerts import get_alert, get_alerts
from .control_graph import _identity, _instant, _runtime, _short
from .database import database_path, get_administrator_audit_events, get_tool_request_details
from .decision_explanation import _role, build_explanation
from .time_range import TimeRange, permitted_lookback_days

logger = logging.getLogger(__name__)

TIMELINE_LIMIT = 200
RELATED_LIMIT = 20
WINDOW_BEFORE = timedelta(hours=24)

STATUS_FLOW = {
    "OPEN": ("ACKNOWLEDGED", "Acknowledge"),
    "ACKNOWLEDGED": ("INVESTIGATING", "Start investigating"),
    "INVESTIGATING": ("RESOLVED", "Resolve"),
}


def _section(name: str, build: Callable[[], Any]) -> Any:
    try:
        return build()
    except Exception:  # one section must never take the whole workspace down
        logger.exception("Incident workspace section %s failed", name)
        return {"error": f"The {name.replace('_', ' ')} could not be loaded. Try again."}


def _rows(sql: str, parameters: tuple) -> list[Any]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(sql, parameters).fetchall()


def incident_events(alert_id: str, alert_org: str | None) -> list[dict[str, Any]]:
    """The incident's full action record. Install-level incidents keep org_id NULL."""
    if alert_org is None:
        rows = _rows("SELECT * FROM incident_events WHERE alert_id = ? AND org_id IS NULL ORDER BY id", (alert_id,))
    else:
        rows = _rows("SELECT * FROM incident_events WHERE alert_id = ? AND org_id = ? ORDER BY id", (alert_id, alert_org))
    return [{**dict(row), "detail": json.loads(row["detail_json"])} for row in rows]


def _window(created_at: str, org_id: str | None, now: datetime) -> TimeRange:
    created = _instant(created_at) or now
    floor = now - timedelta(days=permitted_lookback_days(org_id))
    return TimeRange(max(created - WINDOW_BEFORE, floor).isoformat(), None)


EVENT_TEXT = {
    "STATUS_CHANGED": lambda d: f"Status changed from {d.get('from', '?').lower()} to {d.get('to', '?').lower()}.",
    "ASSIGNED": lambda d: f"Owner set to {d.get('to') or 'nobody'}.",
    "NOTE_ADDED": lambda d: f"Note: {d.get('note', '')}",
    "CONTAINMENT": lambda d: f"Containment: {d.get('summary', d.get('action', ''))}.",
    "EXPORTED": lambda d: "Incident package exported.",
}


def _timeline(alert: dict[str, Any], org_id: str | None, window: TimeRange,
              sla_breaches: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    entries: list[dict[str, Any]] = [{
        "type": "INCIDENT_OPENED", "timestamp": alert["created_at"], "actor": "GreyGuard",
        "text": f"Incident opened: {alert['title']}.", "path": None, "trigger": True,
    }]
    # Computed against the org's current targets, at the moment each deadline passed.
    for breach in sla_breaches or []:
        entries.append({"type": "SLA_BREACH", "timestamp": breach["deadline"], "actor": "GreyGuard",
                        "text": breach["text"], "path": None})
    request_id = alert.get("request_id")
    if request_id and org_id is not None:
        details = get_tool_request_details(request_id, org_id=org_id)
        if details:
            entries.append({"type": "REQUEST", "timestamp": details["timestamp"], "actor": details["agent_name"],
                            "text": f"Requested {details['action']}{' on ' + _short(details.get('target')) if details.get('target') else ''}; decided {details['policy_decision']}.",
                            "path": f"/requests/{request_id}", "trigger": True})
            for event in details.get("approval_events", []):
                entries.append({"type": "APPROVAL", "timestamp": event["timestamp"], "actor": event["actor"],
                                "text": f"Approval decision: {event['decision'].lower()}.", "path": f"/requests/{request_id}"})
            for event in details.get("execution_events", []):
                entries.append({"type": "EXECUTION", "timestamp": event["timestamp"], "actor": "GreyGuard sandbox",
                                "text": f"Execution finished: {event['execution_status'].lower()}.", "path": f"/requests/{request_id}"})
    agent = alert.get("agent_name")
    evidence_truncated = False
    if agent and org_id is not None:
        found = get_administrator_audit_events(agent_name=agent, limit=200, org_id=org_id, time_range=window)
        # The evidence query caps each source before filtering by agent, so in a busy org some of
        # this agent's decisions can fall outside it: say so rather than look complete.
        evidence_truncated = bool(found.get("truncated"))
        for event in found["events"]:
            # The timeline's agent filter is a substring match; only this agent's own evidence counts.
            if event.get("agent_name") != agent:
                continue
            if event["event_type"] == "POLICY":
                entries.append({"type": "DECISION", "timestamp": event["timestamp"], "actor": event["agent_name"],
                                "text": f"{event['action']}: {event['outcome']}.", "path": None})
            elif event["event_type"] == "AUTHENTICATION" and event["severity"] != "INFO":
                entries.append({"type": "AUTHENTICATION", "timestamp": event["timestamp"], "actor": event["agent_name"],
                                "text": f"Authentication {event['outcome'].lower().replace('_', ' ')}.", "path": None})
    for event in incident_events(alert["alert_id"], alert.get("org_id")):
        entries.append({"type": event["event_type"], "timestamp": event["timestamp"], "actor": event["actor"],
                        "text": EVENT_TEXT.get(event["event_type"], lambda d: event["event_type"])(event["detail"]), "path": None,
                        "action_record": True})
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    entries.sort(key=lambda entry: _instant(entry["timestamp"]) or epoch, reverse=True)
    return {"entries": entries[:TIMELINE_LIMIT], "truncated": len(entries) > TIMELINE_LIMIT or evidence_truncated,
            "window": window.as_dict()}


def _agent(alert: dict[str, Any], org_id: str | None) -> dict[str, Any] | None:
    agent = alert.get("agent_name")
    if not agent:
        return None
    if org_id is None:
        return {"agent_name": agent, "known": False, "note": "Install-level: this name belongs to no organization."}
    identity = _identity(agent, org_id)
    runtime = _runtime(agent, org_id)
    return {"agent_name": agent, "known": identity is not None, "status": runtime["agent_status"], "risk_score": runtime["risk_score"],
            "credential_status": identity["credential_status"] if identity else None, "scopes": identity["scopes"] if identity else [],
            "path": f"/agents/{agent}", "graph_path": f"/agents/{agent}?tab=relationships"}


def _related(alert: dict[str, Any], org_id: str | None, include_install_level: bool, caller_org: str) -> list[dict[str, Any]]:
    agent = alert.get("agent_name")
    if not agent:
        return []
    found = get_alerts(agent_name=agent, limit=RELATED_LIMIT + 1, sync_existing=False, org_id=caller_org,
                       include_install_level=include_install_level)["alerts"]
    return [{"alert_id": item["alert_id"], "title": item["title"], "severity": item["severity"], "status": item["status"],
             "created_at": item["created_at"], "path": f"/incidents/{item['alert_id']}"}
            for item in found if item["alert_id"] != alert["alert_id"]][:RELATED_LIMIT]


def _integrity(explanation: dict[str, Any] | None) -> dict[str, Any]:
    rows = _rows("SELECT checked_at, valid FROM audit_integrity_checks ORDER BY checked_at DESC LIMIT 1", ())
    return {
        "decision_record_intact": explanation["integrity"]["record_intact"] if explanation else None,
        "policy_unchanged": explanation["integrity"]["policy_unchanged"] if explanation else None,
        "basis": explanation["basis"] if explanation else None,
        "audit_chain": {"last_verified_at": rows[0]["checked_at"], "valid": bool(rows[0]["valid"])} if rows else None,
    }


def _owner(alert: dict[str, Any], org_id: str | None, viewer: dict[str, Any]) -> dict[str, Any]:
    """The owner: a member of the incident's org. A free-text owner from before is "legacy".
    Candidates are listed only for people who may assign, and only from the incident's own org."""
    members = [member for member in organizations.list_members(org_id) if member["status"] == "ACTIVE"] if org_id else []
    by_email = {member["email"]: member for member in members}
    name = alert.get("assigned_to")
    kind = None if not name else "member" if name in by_email else "free_text"
    owner = {"name": by_email[name]["display_name"] if kind == "member" else name, "email": name if kind == "member" else None, "kind": kind}
    if _has(viewer, "incident:manage"):
        owner["candidates"] = [{"email": member["email"], "display_name": member["display_name"]} for member in members]
    return owner


def _has(viewer: dict[str, Any], permission: str) -> bool:
    return permission in set(viewer.get("permissions") or [])


def actions_for(alert: dict[str, Any], viewer: dict[str, Any]) -> dict[str, Any]:
    """What the viewer may do here, each unavailable one with a reason from their own role only."""
    manage = _has(viewer, "incident:manage")
    reason = None if manage else f"Your role, {_role(viewer)}, can view incidents but not change them."
    step = STATUS_FLOW.get(alert["status"])
    primary = {"id": f"status:{step[0]}", "label": step[1], "to_status": step[0], "requires_note": step[0] == "RESOLVED",
               "available": manage, "unavailable_reason": reason} if step else None
    others = [
        {"id": "note", "label": "Add a note", "available": manage, "unavailable_reason": reason},
    ]
    if alert["status"] not in ("RESOLVED", "DISMISSED"):
        others.append({"id": "status:DISMISSED", "label": "Dismiss", "to_status": "DISMISSED", "requires_note": True,
                       "available": manage, "unavailable_reason": reason})
    others.extend(containment_actions(alert, viewer))
    others.append({"id": "export", "label": "Export the incident package", "available": True, "unavailable_reason": None})
    others.append({"id": "verify_chain", "label": "Verify the audit chain", "available": bool(viewer.get("install_operator")),
                   "unavailable_reason": None if viewer.get("install_operator") else "Only an install operator can verify the install-wide audit chain."})
    return {"primary": primary, "others": others}


def _sla(alert: dict[str, Any], org_id: str | None, now: datetime) -> dict[str, Any]:
    from . import incident_sla

    if org_id is None:
        return incident_sla.evaluate(alert, {}, [], now)
    targets = incident_sla.get_targets(org_id)["targets"]
    changes = incident_sla.status_changes([alert["alert_id"]], org_id).get(alert["alert_id"], []) if targets else []
    return incident_sla.evaluate(alert, targets, changes, now)


def build_workspace(alert_id: str, *, caller_org: str, include_install_level: bool, viewer: dict[str, Any],
                    now: datetime | None = None) -> dict[str, Any] | None:
    alert = get_alert(alert_id, org_id=caller_org, include_install_level=include_install_level)
    if alert is None:
        return None
    now = now or datetime.now(timezone.utc)
    org_id = alert.get("org_id")  # the incident's own org; None for an install-level incident
    window = _window(alert["created_at"], org_id, now)
    explanation = _section("explanation", lambda: build_explanation(alert["request_id"], org_id=org_id, viewer=viewer)
                           if alert.get("request_id") and org_id is not None else None)
    explanation_ok = explanation if isinstance(explanation, dict) and "error" not in explanation else None
    sla = _section("SLA", lambda: _sla(alert, org_id, now))
    breaches = sla.get("breaches", []) if isinstance(sla, dict) else []
    return {
        "incident": {
            "alert_id": alert["alert_id"], "title": alert["title"], "summary": alert["summary"], "severity": alert["severity"],
            "status": alert["status"], "created_at": alert["created_at"], "updated_at": alert["updated_at"],
            "event_type": alert["event_type"], "agent_name": alert.get("agent_name"), "request_id": alert.get("request_id"),
            "resolution_note": alert.get("resolution_note"), "install_level": org_id is None,
        },
        "owner": _owner(alert, org_id, viewer),
        "sla": sla,
        "explanation": explanation,
        "timeline": _section("timeline", lambda: _timeline(alert, org_id, window, breaches)),
        "agent": _section("agent", lambda: _agent(alert, org_id)),
        "related": _section("related incidents", lambda: _related(alert, org_id, include_install_level, caller_org)),
        "integrity": _section("integrity", lambda: _integrity(explanation_ok)),
        "notes": alert.get("notes", []),
        "actions": actions_for(alert, viewer),
        "why_you_see_this": ("You see this because you are an install operator and this incident belongs to no organization."
                             if org_id is None else "You see this because your role can read your organization's incidents."),
        "generated_at": now.isoformat(),
    }


# --- Containment from the incident (step 3; owner decision 1, 2026-10-16) -------------------------
#
# Each action applies the same guard as its own route, plus incident:manage (acting from an incident
# is an incident change; the permission layer requires it for /incidents/{id}/actions):
#   revoke_credential   identity:manage            (as POST /agents/{name}/credential/revoke)
#   disable_agent       Platform Administrator     (as PUT /policy-emergency-controls)
#   disable_tool        Platform Administrator     (as PUT /policy-emergency-controls)
#   terminate_isolation Platform Administrator     (as POST /execution-isolation/emergency-terminate)
# Every action needs a typed confirmation and a reason, acts only on the incident's own agent or
# tool in the incident's own org, and is appended to the incident's action record.

CONTAINMENT = {
    "revoke_credential": {"label": "Revoke the agent's credential", "needs": "permission:identity:manage"},
    "disable_agent": {"label": "Emergency-disable the agent", "needs": "role:PLATFORM_ADMIN"},
    "disable_tool": {"label": "Emergency-disable the tool", "needs": "role:PLATFORM_ADMIN"},
    "terminate_isolation": {"label": "Stop running isolated executions", "needs": "role:PLATFORM_ADMIN"},
}
MIN_REASON = 5


class ActionRefused(ValueError):
    """The request is malformed or not applicable (400)."""


class ActionForbidden(PermissionError):
    """The viewer may not take this action (403)."""


def _allowed(viewer: dict[str, Any], needs: str) -> bool:
    kind, _, value = needs.partition(":")
    return _has(viewer, value) if kind == "permission" else viewer.get("role") == value


def _target(action: str, alert: dict[str, Any]) -> str | None:
    """What the action acts on, and what the person must type to confirm it."""
    if action in ("revoke_credential", "disable_agent"):
        return alert.get("agent_name")
    if action == "disable_tool":
        return alert.get("action")
    return "TERMINATE"


def containment_actions(alert: dict[str, Any], viewer: dict[str, Any]) -> list[dict[str, Any]]:
    from . import main

    actions = []
    for action, spec in CONTAINMENT.items():
        target = _target(action, alert)
        reason = None
        if alert.get("org_id") is None:
            reason = "Containment is not available for install-level incidents: they belong to no organization."
        elif action != "terminate_isolation" and not target:
            reason = "This incident names no agent or tool to act on."
        elif action == "disable_tool" and target not in main.permissions:
            reason = "This incident's action is not a tool GreyGuard controls."
        elif not _has(viewer, "incident:manage") or not _allowed(viewer, spec["needs"]):
            needs = "identity management rights" if spec["needs"].startswith("permission") else "the Platform Administrator role"
            reason = f"Your role, {_role(viewer)}, cannot do this: it needs {needs}."
        actions.append({"id": action, "label": spec["label"], "target": target, "confirm_text": target,
                        "available": reason is None, "unavailable_reason": reason})
    return actions


def run_containment(alert_id: str, action: str, reason: str, confirm: str, *, caller_org: str, include_install_level: bool,
                    viewer: dict[str, Any]) -> dict[str, Any]:
    from . import execution_isolation, main
    from .alerts import record_incident_event
    from .policy_control import get_emergency_controls, update_emergency_controls

    if action not in CONTAINMENT:
        raise ActionRefused("Unknown containment action.")
    alert = get_alert(alert_id, org_id=caller_org, include_install_level=include_install_level)
    if alert is None:
        raise KeyError("Incident not found.")
    available = next(item for item in containment_actions(alert, viewer) if item["id"] == action)
    if not available["available"]:
        # The same answer whether the reason is the role or the incident: nothing else leaks.
        if available["unavailable_reason"].startswith("Your role"):
            raise ActionForbidden(available["unavailable_reason"])
        raise ActionRefused(available["unavailable_reason"])
    if len((reason or "").strip()) < MIN_REASON:
        raise ActionRefused("Give a reason of at least five characters; it goes into the action record.")
    target = available["target"]
    if (confirm or "").strip() != target:
        raise ActionRefused(f"Type {target} exactly to confirm.")
    org_id = alert["org_id"]
    if action in ("revoke_credential", "disable_agent") and main.agent_org_id(main.normalize_agent_name(target)) != org_id:
        raise KeyError("Incident not found.")  # never act across orgs, and never say why
    actor = viewer.get("email") or viewer.get("admin_id")

    if action == "revoke_credential":
        main.revoke_agent_credential(target, actor=viewer.get("admin_id") or actor, org_id=org_id)
        summary = f"revoked the credential of {target}"
    elif action in ("disable_agent", "disable_tool"):
        controls = get_emergency_controls(org_id=org_id)
        agents, tools = list(controls["disabled_agents"]), list(controls["disabled_tools"])
        (agents if action == "disable_agent" else tools).append(target)
        update_emergency_controls(controls["global_deny"], sorted(set(agents)), sorted(set(tools)),
                                  controls["disabled_integrations"], viewer.get("admin_id") or actor, org_id=org_id)
        summary = f"emergency-disabled the {'agent' if action == 'disable_agent' else 'tool'} {target}"
    else:
        result = execution_isolation.emergency_terminate(viewer.get("admin_id") or actor, org_id)
        summary = f"stopped running isolated executions ({result.get('terminated', 0) if isinstance(result, dict) else 0} stopped)"

    with sqlite3.connect(database_path) as connection:
        record_incident_event(connection, alert_id, org_id, actor, "CONTAINMENT",
                              {"action": action, "target": target, "reason": reason.strip(), "summary": summary})
    return {"action": action, "target": target, "summary": summary, "recorded": True}


# --- The incident package (step 3; owner decision 4: auditors may export, every export recorded) ----

def build_package(alert_id: str, *, caller_org: str, include_install_level: bool, viewer: dict[str, Any]) -> dict[str, Any] | None:
    import hashlib

    from .alerts import record_incident_event
    from .decision_provenance import canonical, get_decision_records

    view = build_workspace(alert_id, caller_org=caller_org, include_install_level=include_install_level, viewer=viewer)
    if view is None:
        return None
    # The incident's own org: None for an install-level incident (visible only to operators).
    alert_org = None if view["incident"]["install_level"] else caller_org
    request_id = view["incident"]["request_id"]
    records = get_decision_records([request_id], org_id=alert_org) if request_id and alert_org else {}
    parts = {
        "incident": view["incident"],
        "owner": {key: value for key, value in view["owner"].items() if key != "candidates"},
        "explanation": view["explanation"],
        "timeline": view["timeline"],
        "decision_records": list(records.values()),
        "action_record": incident_events(alert_id, alert_org),
        "notes": view["notes"],
        "integrity": view["integrity"],
        "sla": view["sla"],
    }
    manifest = {name: hashlib.sha256(canonical(part).encode()).hexdigest() for name, part in parts.items()}
    exported_by = viewer.get("email") or viewer.get("admin_id")
    exported_at = datetime.now(timezone.utc).isoformat()
    package = {
        "format": "greyguard.incident-package/1",
        "exported_at": exported_at,
        "exported_by": exported_by,
        "parts": parts,
        "manifest": {"algorithm": "sha256", "parts": manifest,
                     "package": hashlib.sha256(canonical(manifest).encode()).hexdigest()},
        "note": "Redacted evidence only. Verify a part by hashing its canonical JSON (sorted keys, no spaces).",
    }
    with sqlite3.connect(database_path) as connection:
        record_incident_event(connection, alert_id, alert_org, exported_by, "EXPORTED",
                              {"package_sha256": package["manifest"]["package"]})
    return package
