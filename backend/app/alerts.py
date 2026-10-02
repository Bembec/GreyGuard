"""Persistent defensive alert management for GreyGuard."""

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from .database import database_path


VALID_STATUSES = {
    "OPEN", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "DISMISSED",
}
VALID_SEVERITIES = {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"}


def current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def initialize_alert_database() -> None:
    """Create alert and investigation-note tables."""
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS security_alerts (
                alert_id TEXT PRIMARY KEY,
                source_event_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                agent_name TEXT,
                request_id TEXT,
                event_type TEXT NOT NULL,
                action TEXT,
                outcome TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                assigned_to TEXT,
                resolution_note TEXT,
                evidence_json TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS alert_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                note TEXT NOT NULL,
                FOREIGN KEY (alert_id) REFERENCES security_alerts(alert_id)
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_status "
            "ON security_alerts(status)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_severity "
            "ON security_alerts(severity)"
        )


def _alert_title(event: dict[str, Any]) -> str:
    agent = event.get("agent_name") or "Unknown agent"
    outcome = event.get("outcome") or "security event"
    return f"{outcome} detected for {agent}"


def sync_alerts_from_events(events: list[dict[str, Any]] | None = None) -> int:
    """Create deduplicated alerts from high and critical evidence."""
    initialize_alert_database()
    if events is None:
        from .database import get_administrator_audit_events
        response = get_administrator_audit_events(limit=500)
        events = response["events"]

    created = 0
    with sqlite3.connect(database_path) as connection:
        for event in events:
            severity = str(event.get("severity", "INFO")).upper()
            event_id = str(event.get("event_id", "")).strip()
            if severity not in {"HIGH", "CRITICAL"} or not event_id:
                continue
            timestamp = str(event.get("timestamp") or current_timestamp())
            cursor = connection.execute("""
                INSERT OR IGNORE INTO security_alerts (
                    alert_id, source_event_id, created_at, updated_at,
                    agent_name, request_id, event_type, action, outcome,
                    severity, status, title, summary, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?)
            """, (
                str(uuid.uuid4()), event_id, timestamp, timestamp,
                event.get("agent_name"), event.get("request_id"),
                str(event.get("event_type", "UNKNOWN")), event.get("action"),
                str(event.get("outcome", "UNKNOWN")), severity,
                _alert_title(event), str(event.get("summary", "Security evidence recorded.")),
                json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=str),
            ))
            created += int(cursor.rowcount > 0)
    return created


def _notes(connection: sqlite3.Connection, alert_id: str) -> list[dict[str, Any]]:
    rows = connection.execute("""
        SELECT id, alert_id, timestamp, actor, note
        FROM alert_notes WHERE alert_id = ? ORDER BY id DESC
    """, (alert_id,)).fetchall()
    return [dict(row) for row in rows]


def _serialize(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    try:
        data["evidence"] = json.loads(data.pop("evidence_json"))
    except (json.JSONDecodeError, TypeError):
        data["evidence"] = {"error": "Stored evidence could not be decoded."}
        data.pop("evidence_json", None)
    data["notes"] = _notes(connection, data["alert_id"])
    return data


def get_alerts(
    status: str | None = None,
    severity: str | None = None,
    agent_name: str | None = None,
    limit: int = 100,
    sync_existing: bool = True,
) -> dict[str, Any]:
    """Return filtered alerts newest first."""
    if sync_existing:
        sync_alerts_from_events()
    clauses: list[str] = []
    parameters: list[Any] = []
    if status:
        clauses.append("status = ?")
        parameters.append(status.strip().upper())
    if severity:
        clauses.append("severity = ?")
        parameters.append(severity.strip().upper())
    if agent_name:
        clauses.append("agent_name = ?")
        parameters.append(agent_name.strip())
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    safe_limit = max(1, min(int(limit), 500))
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM security_alerts" + where + " ORDER BY created_at DESC LIMIT ?",
            (*parameters, safe_limit),
        ).fetchall()
        alerts = [_serialize(connection, row) for row in rows]
    return {
        "alerts": alerts,
        "count": len(alerts),
        "filters": {"status": status, "severity": severity, "agent_name": agent_name, "limit": safe_limit},
    }


def get_alert(alert_id: str) -> dict[str, Any] | None:
    initialize_alert_database()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM security_alerts WHERE alert_id = ?", (alert_id,)
        ).fetchone()
        return None if row is None else _serialize(connection, row)


def update_alert(
    alert_id: str,
    status: str,
    actor: str,
    assigned_to: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Update workflow state and preserve administrator evidence."""
    normalized = str(status).strip().upper()
    if normalized not in VALID_STATUSES:
        raise ValueError("Unsupported alert status.")
    timestamp = current_timestamp()
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute("""
            UPDATE security_alerts SET status = ?, assigned_to = ?,
                resolution_note = CASE WHEN ? IN ('RESOLVED','DISMISSED') THEN ? ELSE resolution_note END,
                updated_at = ? WHERE alert_id = ?
        """, (normalized, assigned_to, normalized, note, timestamp, alert_id))
        if cursor.rowcount == 0:
            raise KeyError("Alert not found.")
        if note:
            connection.execute("""
                INSERT INTO alert_notes (alert_id, timestamp, actor, note)
                VALUES (?, ?, ?, ?)
            """, (alert_id, timestamp, actor, note.strip()))
    result = get_alert(alert_id)
    if result is None:
        raise KeyError("Alert not found.")
    return result


def add_alert_note(alert_id: str, actor: str, note: str) -> dict[str, Any]:
    """Append one investigation note."""
    normalized_note = str(note).strip()
    if not normalized_note:
        raise ValueError("Investigation note is required.")
    timestamp = current_timestamp()
    with sqlite3.connect(database_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM security_alerts WHERE alert_id = ?", (alert_id,)
        ).fetchone()
        if exists is None:
            raise KeyError("Alert not found.")
        cursor = connection.execute("""
            INSERT INTO alert_notes (alert_id, timestamp, actor, note)
            VALUES (?, ?, ?, ?)
        """, (alert_id, timestamp, actor, normalized_note))
        connection.execute(
            "UPDATE security_alerts SET updated_at = ? WHERE alert_id = ?",
            (timestamp, alert_id),
        )
        note_id = cursor.lastrowid
    return {"id": note_id, "alert_id": alert_id, "timestamp": timestamp, "actor": actor, "note": normalized_note}


def alert_summary() -> dict[str, int]:
    """Return alert counts for operations dashboards."""
    sync_alerts_from_events()
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("""
            SELECT COUNT(*),
                SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status IN ('ACKNOWLEDGED','INVESTIGATING') THEN 1 ELSE 0 END),
                SUM(CASE WHEN status IN ('RESOLVED','DISMISSED') THEN 1 ELSE 0 END),
                SUM(CASE WHEN severity = 'CRITICAL' AND status NOT IN ('RESOLVED','DISMISSED') THEN 1 ELSE 0 END)
            FROM security_alerts
        """).fetchone()
    return {
        "total": row[0] or 0,
        "open": row[1] or 0,
        "in_progress": row[2] or 0,
        "closed": row[3] or 0,
        "active_critical": row[4] or 0,
    }
