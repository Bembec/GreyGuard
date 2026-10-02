"""Persistent in-app security notifications derived from GreyGuard alerts."""

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .database import database_path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize_notification_database() -> None:
    """Create the durable administrator notification inbox."""
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS security_notifications (
                notification_id TEXT PRIMARY KEY,
                source_alert_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                resource_path TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                read_at TEXT,
                read_by TEXT
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_notification_unread "
            "ON security_notifications(is_read, created_at)"
        )


def sync_notifications() -> int:
    """Create one deduplicated notification for every security alert."""
    initialize_notification_database()
    from .alerts import get_alerts

    alerts = get_alerts(limit=500)["alerts"]
    created = 0
    with sqlite3.connect(database_path) as connection:
        for alert in alerts:
            alert_id = str(alert["alert_id"])
            cursor = connection.execute("""
                INSERT OR IGNORE INTO security_notifications (
                    notification_id, source_alert_id, created_at, severity,
                    title, message, resource_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                "ntf_" + uuid.uuid4().hex,
                alert_id,
                str(alert["created_at"]),
                str(alert["severity"]),
                str(alert["title"]),
                str(alert["summary"]),
                f"/incidents?alert={alert_id}",
            ))
            created += int(cursor.rowcount > 0)
    return created


def _serialize(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["is_read"] = bool(result["is_read"])
    return result


def list_notifications(
    unread_only: bool = False,
    severity: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    sync_notifications()
    clauses: list[str] = []
    parameters: list[Any] = []
    if unread_only:
        clauses.append("is_read = 0")
    if severity:
        clauses.append("severity = ?")
        parameters.append(severity.strip().upper())
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    safe_limit = max(1, min(int(limit), 500))
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM security_notifications" + where
            + " ORDER BY created_at DESC LIMIT ?",
            (*parameters, safe_limit),
        ).fetchall()
    notifications = [_serialize(row) for row in rows]
    return {"notifications": notifications, "count": len(notifications)}


def notification_summary() -> dict[str, int]:
    sync_notifications()
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("""
            SELECT COUNT(*),
                SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END),
                SUM(CASE WHEN is_read = 0 AND severity = 'CRITICAL' THEN 1 ELSE 0 END),
                SUM(CASE WHEN is_read = 0 AND severity = 'HIGH' THEN 1 ELSE 0 END)
            FROM security_notifications
        """).fetchone()
    return {
        "total": row[0] or 0,
        "unread": row[1] or 0,
        "unread_critical": row[2] or 0,
        "unread_high": row[3] or 0,
    }


def mark_notification_read(notification_id: str, actor: str) -> dict[str, Any]:
    timestamp = utc_now()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute("""
            UPDATE security_notifications
            SET is_read = 1, read_at = COALESCE(read_at, ?),
                read_by = COALESCE(read_by, ?)
            WHERE notification_id = ?
        """, (timestamp, actor, notification_id))
        if cursor.rowcount == 0:
            raise KeyError("Notification not found.")
        row = connection.execute(
            "SELECT * FROM security_notifications WHERE notification_id = ?",
            (notification_id,),
        ).fetchone()
    return _serialize(row)


def mark_all_notifications_read(actor: str) -> int:
    timestamp = utc_now()
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute("""
            UPDATE security_notifications
            SET is_read = 1, read_at = ?, read_by = ?
            WHERE is_read = 0
        """, (timestamp, actor))
    return cursor.rowcount
