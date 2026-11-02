"""Incident response targets (SLA), per organization and severity (P7.5 item 5, step 4).

Owner decision 2, 2026-10-16: no defaults. Until an organization sets targets, every incident shows
"No SLA set", and GreyGuard never shows a deadline nobody committed to. The suggested values are
offered only when an administrator first sets targets, and are never applied by themselves.

- **Targets:** for each severity incidents can have (CRITICAL, HIGH), an optional time to
  acknowledge and an optional time to resolve, in minutes. Stored per org in
  `incident_sla_targets`, with who changed them and when.
- **Measured against the current targets.** The state of an incident is computed when it is read,
  from its opening time and its recorded status changes (`incident_events`); nothing is stored per
  incident, so changing a target re-measures open and closed incidents alike, and the page says so.
- **States:** within target; due soon (the last 25% of the target); breached (passed while still
  open); met or missed (completed before or after the deadline). A closed incident with no recorded
  status change (closed before the action record existed) is "not measurable", never guessed.
- **Install-level incidents** belong to no organization, so no organization's targets apply.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from . import database
from . import db_compat as sqlite3
from .control_graph import _instant

SEVERITIES = ("CRITICAL", "HIGH")
PHASES = ("acknowledge", "resolve")
MAX_MINUTES = 365 * 24 * 60
DUE_SOON_FRACTION = 0.25
CLOSED = ("RESOLVED", "DISMISSED")
# Offered when an organization first sets targets (owner decision 2). Never applied automatically.
SUGGESTED = {
    "CRITICAL": {"acknowledge_minutes": 15, "resolve_minutes": 240},
    "HIGH": {"acknowledge_minutes": 60, "resolve_minutes": 1440},
}
BASIS = "Measured against your organization's current targets, from when the incident opened."


def initialize_incident_sla() -> None:
    with sqlite3.connect(database.database_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS incident_sla_targets (
                org_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                acknowledge_minutes INTEGER,
                resolve_minutes INTEGER,
                updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (org_id, severity),
                CHECK (severity IN ('CRITICAL', 'HIGH')),
                CHECK (acknowledge_minutes IS NULL OR acknowledge_minutes BETWEEN 1 AND 525600),
                CHECK (resolve_minutes IS NULL OR resolve_minutes BETWEEN 1 AND 525600),
                CHECK (acknowledge_minutes IS NOT NULL OR resolve_minutes IS NOT NULL)
            )
        """)


def get_targets(org_id: str) -> dict[str, Any]:
    """The org's targets. `suggestions` only while nothing is set."""
    initialize_incident_sla()
    with sqlite3.connect(database.database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM incident_sla_targets WHERE org_id = ? ORDER BY severity", (org_id,)).fetchall()
    targets = {row["severity"]: {"acknowledge_minutes": row["acknowledge_minutes"], "resolve_minutes": row["resolve_minutes"]}
               for row in rows if row["severity"] in SEVERITIES}
    latest = max(rows, key=lambda row: row["updated_at"], default=None)
    return {
        "org_id": org_id,
        "configured": bool(targets),
        "severities": list(SEVERITIES),
        "targets": targets,
        "updated_by": latest["updated_by"] if latest else None,
        "updated_at": latest["updated_at"] if latest else None,
        "suggestions": None if targets else SUGGESTED,
        "basis": BASIS,
    }


def _minutes(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a whole number of minutes.")
    if not 1 <= value <= MAX_MINUTES:
        raise ValueError(f"{label} must be between 1 minute and 365 days.")
    return value


def set_targets(org_id: str, targets: dict[str, Any], actor: str) -> dict[str, Any]:
    """Replace the org's targets. A severity left out, or with neither time, has no target; an
    empty set returns the org to "No SLA set"."""
    unknown = set(targets) - set(SEVERITIES)
    if unknown:
        raise ValueError(f"Incidents have no severity {sorted(unknown)[0]}; use CRITICAL or HIGH.")
    clean: dict[str, tuple[int | None, int | None]] = {}
    for severity in SEVERITIES:
        target = targets.get(severity) or {}
        if not isinstance(target, dict) or set(target) - {"acknowledge_minutes", "resolve_minutes"}:
            raise ValueError(f"{severity}: give acknowledge_minutes and resolve_minutes only.")
        acknowledge = _minutes(target.get("acknowledge_minutes"), f"{severity.title()} time to acknowledge")
        resolve = _minutes(target.get("resolve_minutes"), f"{severity.title()} time to resolve")
        if acknowledge is not None and resolve is not None and resolve < acknowledge:
            raise ValueError(f"{severity.title()}: the time to resolve cannot be shorter than the time to acknowledge.")
        if acknowledge is not None or resolve is not None:
            clean[severity] = (acknowledge, resolve)
    initialize_incident_sla()
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(database.database_path) as connection:
        connection.execute("DELETE FROM incident_sla_targets WHERE org_id = ?", (org_id,))
        for severity, (acknowledge, resolve) in clean.items():
            connection.execute(
                "INSERT INTO incident_sla_targets (org_id, severity, acknowledge_minutes, resolve_minutes, updated_by, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)", (org_id, severity, acknowledge, resolve, actor, now))
    return get_targets(org_id)


def status_changes(alert_ids: list[str], org_id: str) -> dict[str, list[dict[str, Any]]]:
    """Recorded status changes for these incidents of one org, oldest first, in one query."""
    if not alert_ids:
        return {}
    marks = ",".join("?" for _ in alert_ids)
    with sqlite3.connect(database.database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"SELECT alert_id, timestamp, detail_json FROM incident_events WHERE org_id = ? AND event_type = 'STATUS_CHANGED'"  # nosec B608  # placeholders only
            f" AND alert_id IN ({marks}) ORDER BY id", (org_id, *alert_ids)).fetchall()
    found: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        found.setdefault(row["alert_id"], []).append({"timestamp": row["timestamp"], **json.loads(row["detail_json"])})
    return found


def _completed(alert: dict[str, Any], changes: list[dict[str, Any]]) -> dict[str, tuple[datetime | None, bool]]:
    """For each phase: when it was completed (from the action record), and whether it was completed
    with no recorded change (before the action record existed), which makes it not measurable."""
    closed = None
    if alert["status"] in CLOSED:
        closing = [change for change in changes if change.get("to") in CLOSED]
        closed = _instant(closing[-1]["timestamp"]) if closing else None
    # Leaving OPEN acknowledges it (closing straight from OPEN is such a change). A close recorded
    # after an unrecorded acknowledgement does not stand in for it: that would be a guess.
    acknowledged = next((_instant(change["timestamp"]) for change in changes if change.get("from") == "OPEN"), None)
    return {
        "acknowledge": (acknowledged, alert["status"] != "OPEN" and acknowledged is None),
        "resolve": (closed, alert["status"] in CLOSED and closed is None),
    }


def _duration(minutes: int) -> str:
    if minutes % 1440 == 0:
        days = minutes // 1440
        return f"{days} day{'s' if days != 1 else ''}"
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


RANK = {"breached": 0, "due_soon": 1, "within": 2, "missed": 3, "not_measurable": 4, "met": 5}
TEXT = {
    "breached": "{phase} target breached ({duration})",
    "due_soon": "{phase} due soon ({duration} target)",
    "within": "{phase} within target ({duration})",
    "missed": "{phase} target missed ({duration})",
    "met": "{phase} target met ({duration})",
    "not_measurable": "{phase} not measurable: closed before changes were recorded",
}


def evaluate(alert: dict[str, Any], org_targets: dict[str, Any], changes: list[dict[str, Any]],
             now: datetime | None = None) -> dict[str, Any]:
    """The SLA state of one incident against its org's current targets."""
    if alert.get("org_id") is None:
        return {"configured": False, "state": None, "text": "No SLA set", "phases": [], "breaches": [],
                "basis": "Install-level incidents belong to no organization, so no targets apply."}
    target = org_targets.get(alert["severity"])
    if not target:
        text = "No SLA set" if not org_targets else f"No SLA set for {alert['severity'].lower()} incidents"
        return {"configured": False, "state": None, "text": text, "phases": [], "breaches": [], "basis": None}
    now = now or datetime.now(timezone.utc)
    opened = _instant(alert["created_at"]) or now
    completed = _completed(alert, changes)
    phases = []
    for phase in PHASES:
        minutes = target.get(f"{phase}_minutes")
        if minutes is None:
            continue
        done, unrecorded = completed[phase]
        deadline = opened + timedelta(minutes=minutes)
        if done is not None:
            state = "met" if done <= deadline else "missed"
        elif unrecorded:
            state = "not_measurable"
        else:
            remaining = (deadline - now).total_seconds()
            state = "breached" if remaining < 0 else "due_soon" if remaining <= minutes * 60 * DUE_SOON_FRACTION else "within"
        phases.append({"phase": phase, "target_minutes": minutes, "deadline": deadline.isoformat(), "state": state,
                       "completed_at": done.isoformat() if done else None,
                       "text": TEXT[state].format(phase=phase.title(), duration=_duration(minutes))})
    worst = min(phases, key=lambda item: RANK[item["state"]])
    breaches = [{"phase": item["phase"], "deadline": item["deadline"],
                 "text": f"SLA breached: not {'acknowledged' if item['phase'] == 'acknowledge' else 'resolved'} within {_duration(item['target_minutes'])}."}
                for item in phases if item["state"] in ("breached", "missed")]
    return {"configured": True, "state": worst["state"], "text": worst["text"], "deadline": worst["deadline"],
            "phases": phases, "breaches": breaches, "basis": BASIS}


def evaluate_many(alerts: list[dict[str, Any]], org_id: str | None, now: datetime | None = None) -> dict[str, dict[str, Any]]:
    """SLA state for a list of incidents of one caller's org: one targets read, one events read."""
    targets = get_targets(org_id)["targets"] if org_id else {}
    own = [alert["alert_id"] for alert in alerts if alert.get("org_id") == org_id and org_id]
    changes = status_changes(own, org_id) if targets and own else {}
    return {alert["alert_id"]: evaluate(alert, targets if alert.get("org_id") == org_id else {}, changes.get(alert["alert_id"], []), now)
            for alert in alerts}
