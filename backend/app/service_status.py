"""Public service status, incidents, maintenance notices and measured response times (P3).

- GET /status is public and tenant-free: overall state, component states derived from live checks
  (database, delivery worker, policy distribution signing), open incidents and maintenance.
- Install operators declare incidents (with a severity), post updates and schedule maintenance.
- Response targets are measured, not promised: /status/history reports time to acknowledge and to
  resolve per severity from recorded incidents. No SLA is stated anywhere until measured operation
  supports one.
- A denied security decision is not a service outage. GreyGuard blocking an agent's action is the
  product working; incidents are about the service itself failing.

Incidents and maintenance describe the operated service, so the tables are install-level.
"""
from __future__ import annotations

import json
import os
import statistics
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db_compat as sqlite3
from .database import database_path

SEVERITIES = {
    "SEV1": {"name": "Critical", "meaning": "Enforcement or the control plane is unavailable or making wrong decisions for many customers, or there is a confirmed security breach.",
             "escalation": "Page the on-call engineer and the incident commander at once; status update at least every 30 minutes."},
    "SEV2": {"name": "Major", "meaning": "A core capability (approvals, evidence, delivery, sign-in) is failing or badly degraded for some customers, with no workaround.",
             "escalation": "Page the on-call engineer; status update at least every hour."},
    "SEV3": {"name": "Minor", "meaning": "A non-core capability is degraded, or a core one has a workaround.",
             "escalation": "On-call engineer during business hours; status update when the state changes."},
    "SEV4": {"name": "Low", "meaning": "Cosmetic or single-customer issue with no operational impact.",
             "escalation": "Normal support queue."},
}
NOT_AN_OUTAGE = "A denied or held security decision is GreyGuard working as designed, not a service outage."
COMPONENTS = ("api", "database", "delivery_worker", "policy_distribution")
INCIDENT_STATES = ("INVESTIGATING", "IDENTIFIED", "MONITORING", "RESOLVED")


class StatusError(ValueError):
    """A status-page request that cannot be carried out."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def initialize_service_status() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS status_incidents (
            incident_id TEXT PRIMARY KEY, title TEXT NOT NULL, severity TEXT NOT NULL, components_json TEXT NOT NULL,
            state TEXT NOT NULL, started_at TEXT NOT NULL, acknowledged_at TEXT, resolved_at TEXT,
            created_by TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS status_incident_updates (
            update_id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL, timestamp TEXT NOT NULL,
            state TEXT NOT NULL, message TEXT NOT NULL, author TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS status_maintenance (
            maintenance_id TEXT PRIMARY KEY, title TEXT NOT NULL, components_json TEXT NOT NULL,
            starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, message TEXT NOT NULL, created_by TEXT NOT NULL,
            created_at TEXT NOT NULL, cancelled_at TEXT)""")


def _components(components) -> list[str]:
    chosen = sorted(set(components))
    if not chosen or not set(chosen) <= set(COMPONENTS):
        raise StatusError(f"Components must be some of: {', '.join(COMPONENTS)}.")
    return chosen


def _checks() -> dict[str, str]:
    """Live component state. Reveals nothing about any tenant."""
    from . import outbound_worker
    states = {"api": "OPERATIONAL"}
    try:
        with sqlite3.connect(database_path) as connection:
            connection.execute("SELECT 1").fetchone()
        states["database"] = "OPERATIONAL"
    except Exception:
        states["database"] = "MAJOR_OUTAGE"
    if not outbound_worker._enabled():
        states["delivery_worker"] = "NOT_RUNNING"
    else:
        tick = outbound_worker.LAST_TICK
        stale = tick["at"] is None or datetime.fromisoformat(tick["at"]) < utc_now() - timedelta(
            seconds=3 * outbound_worker._interval_seconds() + 30)
        states["delivery_worker"] = "DEGRADED" if stale or tick["failed"] else "OPERATIONAL"
    states["policy_distribution"] = "OPERATIONAL" if os.getenv("GREYGUARD_DISTRIBUTION_SIGNING_KEY") else "NOT_CONFIGURED"
    return states


def _incident(connection, row) -> dict[str, Any]:
    incident = dict(row)
    incident["components"] = json.loads(incident.pop("components_json"))
    incident["updates"] = [dict(u) for u in connection.execute(
        "SELECT timestamp, state, message FROM status_incident_updates WHERE incident_id = ? ORDER BY update_id DESC",
        (incident["incident_id"],)).fetchall()]
    incident.pop("created_by", None)
    return incident


def public_status() -> dict[str, Any]:
    initialize_service_status()
    components = _checks()
    now = utc_now().isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        incidents = [_incident(connection, row) for row in connection.execute(
            "SELECT * FROM status_incidents WHERE state != 'RESOLVED' ORDER BY started_at DESC").fetchall()]
        maintenance = [{**{k: row[k] for k in ("maintenance_id", "title", "starts_at", "ends_at", "message")},
                        "components": json.loads(row["components_json"]), "in_progress": row["starts_at"] <= now}
                       for row in connection.execute(
                           "SELECT * FROM status_maintenance WHERE cancelled_at IS NULL AND ends_at > ? ORDER BY starts_at", (now,)).fetchall()]
    for incident in incidents:
        impact = "MAJOR_OUTAGE" if incident["severity"] in ("SEV1",) else "DEGRADED"
        for component in incident["components"]:
            if components.get(component) == "OPERATIONAL":
                components[component] = impact
    for window in maintenance:
        if window["in_progress"]:
            for component in window["components"]:
                if components.get(component) == "OPERATIONAL":
                    components[component] = "MAINTENANCE"
    worst = ("MAJOR_OUTAGE", "DEGRADED", "MAINTENANCE")
    overall = next((state for state in worst if state in components.values()), "OPERATIONAL")
    return {"status": overall, "components": components, "incidents": incidents, "maintenance": maintenance,
            "generated_at": now, "note": NOT_AN_OUTAGE}


def open_incident(title: str, severity: str, components, message: str, actor: str) -> dict[str, Any]:
    if severity not in SEVERITIES:
        raise StatusError("Severity must be SEV1 to SEV4.")
    if len(str(title).strip()) < 5 or len(str(message).strip()) < 5:
        raise StatusError("An incident needs a title and a first update.")
    chosen = _components(components)
    initialize_service_status()
    incident_id = "inc_" + uuid.uuid4().hex[:16]
    now = utc_now().isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO status_incidents (incident_id, title, severity, components_json, state, started_at, created_by) VALUES (?, ?, ?, ?, 'INVESTIGATING', ?, ?)",
            (incident_id, title.strip(), severity, json.dumps(chosen), now, actor))
        connection.execute("INSERT INTO status_incident_updates (incident_id, timestamp, state, message, author) VALUES (?, ?, 'INVESTIGATING', ?, ?)",
                           (incident_id, now, message.strip(), actor))
    return get_incident(incident_id)


def update_incident(incident_id: str, state: str, message: str, actor: str) -> dict[str, Any]:
    if state not in INCIDENT_STATES:
        raise StatusError("State must be INVESTIGATING, IDENTIFIED, MONITORING or RESOLVED.")
    if len(str(message).strip()) < 5:
        raise StatusError("An update needs a message.")
    initialize_service_status()
    now = utc_now().isoformat()
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT state FROM status_incidents WHERE incident_id = ?", (incident_id,)).fetchone()
        if row is None:
            raise KeyError("Incident not found.")
        if row[0] == "RESOLVED":
            raise StatusError("This incident is resolved; open a new one.")
        # Acknowledged = the first move past INVESTIGATING; that is what time-to-acknowledge measures.
        connection.execute(
            """UPDATE status_incidents SET state = ?,
            acknowledged_at = COALESCE(acknowledged_at, CASE WHEN ? != 'INVESTIGATING' THEN ? END),
            resolved_at = CASE WHEN ? = 'RESOLVED' THEN ? ELSE resolved_at END WHERE incident_id = ?""",
            (state, state, now, state, now, incident_id))
        connection.execute("INSERT INTO status_incident_updates (incident_id, timestamp, state, message, author) VALUES (?, ?, ?, ?, ?)",
                           (incident_id, now, state, message.strip(), actor))
    return get_incident(incident_id)


def get_incident(incident_id: str) -> dict[str, Any]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM status_incidents WHERE incident_id = ?", (incident_id,)).fetchone()
        if row is None:
            raise KeyError("Incident not found.")
        return _incident(connection, row)


def schedule_maintenance(title: str, components, starts_at: str, ends_at: str, message: str, actor: str) -> dict[str, Any]:
    chosen = _components(components)
    try:
        start, end = datetime.fromisoformat(starts_at), datetime.fromisoformat(ends_at)
    except ValueError as error:
        raise StatusError("Maintenance times must be ISO 8601 with a timezone.") from error
    if start.tzinfo is None or end.tzinfo is None or not start < end <= start + timedelta(hours=12):
        raise StatusError("A maintenance window must have a timezone, end after it starts and last at most 12 hours.")
    if len(str(title).strip()) < 5:
        raise StatusError("Maintenance needs a title.")
    initialize_service_status()
    maintenance_id = "mnt_" + uuid.uuid4().hex[:16]
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO status_maintenance (maintenance_id, title, components_json, starts_at, ends_at, message, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (maintenance_id, title.strip(), json.dumps(chosen), start.astimezone(timezone.utc).isoformat(),
             end.astimezone(timezone.utc).isoformat(), str(message).strip(), actor, utc_now().isoformat()))
    return {"maintenance_id": maintenance_id, "title": title.strip(), "components": chosen,
            "starts_at": start.astimezone(timezone.utc).isoformat(), "ends_at": end.astimezone(timezone.utc).isoformat()}


def history(days: int = 90) -> dict[str, Any]:
    """Resolved incidents and the measured response times they add up to, per severity."""
    initialize_service_status()
    since = (utc_now() - timedelta(days=days)).isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM status_incidents WHERE started_at >= ? ORDER BY started_at DESC", (since,)).fetchall()
        incidents = [_incident(connection, row) for row in rows]
    minutes = lambda a, b: (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 60
    measured = {}
    for severity in SEVERITIES:
        chosen = [i for i in incidents if i["severity"] == severity]
        ack = [minutes(i["started_at"], i["acknowledged_at"]) for i in chosen if i["acknowledged_at"]]
        res = [minutes(i["started_at"], i["resolved_at"]) for i in chosen if i["resolved_at"]]
        measured[severity] = {
            "incidents": len(chosen),
            "median_minutes_to_acknowledge": round(statistics.median(ack), 1) if ack else None,
            "median_minutes_to_resolve": round(statistics.median(res), 1) if res else None,
        }
    return {"days": days, "incidents": incidents, "measured_response": measured,
            "note": "Measured from recorded incidents. These are observations, not a service-level commitment."}
