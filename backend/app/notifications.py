"""Persistent in-app security notifications derived from GreyGuard alerts.

P2.2 agent scoping, batch C: a notification belongs to the org of the alert it was derived from.
As with alerts, org_id is nullable - NULL marks an install-level notification (from an
install-level alert, see alerts._visibility()), which only install operators see. Each org has
its own retention policy (the former singleton, reshaped to a composite (id, org_id) key like
simulation_config in batch 8); install-level notifications follow a fixed
INSTALL_LEVEL_RETENTION_DAYS, because no tenant's policy should decide what happens to them.
"""

from . import db_compat as sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .database import ALL_ORGS, database_path

DEFAULT_RETENTION_DAYS = 90
INSTALL_LEVEL_RETENTION_DAYS = 90


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _visibility(org_id, include_install_level: bool) -> tuple[str, tuple]:
    if include_install_level:
        return "(org_id = ? OR org_id IS NULL)", (org_id,)
    return "org_id = ?", (org_id,)


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
                read_by TEXT,
                org_id TEXT
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_notification_unread "
            "ON security_notifications(is_read, created_at)"
        )
        policy_columns = [row[1] for row in connection.execute("PRAGMA table_info(notification_retention_policy)")]
        if policy_columns and "org_id" not in policy_columns:
            # The former singleton (PK id, CHECK id = 1) would let only one org hold a policy.
            # SQLite cannot alter a primary key in place, so rebuild with a composite (id, org_id)
            # key, carrying the pre-existing row into the default org. Nothing references this
            # table, so renaming the old one aside is safe.
            connection.execute("ALTER TABLE notification_retention_policy RENAME TO notification_retention_policy_pre_org")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS notification_retention_policy (
                id INTEGER NOT NULL CHECK (id = 1),
                org_id TEXT NOT NULL DEFAULT 'org_default',
                retention_days INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL,
                PRIMARY KEY (id, org_id)
            )
        """)
        if policy_columns and "org_id" not in policy_columns:
            connection.execute("""
                INSERT INTO notification_retention_policy (id, org_id, retention_days, updated_at, updated_by)
                SELECT id, 'org_default', retention_days, updated_at, updated_by
                FROM notification_retention_policy_pre_org
            """)
            connection.execute("DROP TABLE notification_retention_policy_pre_org")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS notification_retention_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                retention_days INTEGER NOT NULL,
                deleted_count INTEGER NOT NULL DEFAULT 0,
                org_id TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS notification_retention_tombstones (
                source_alert_id TEXT PRIMARY KEY,
                expired_at TEXT NOT NULL,
                org_id TEXT
            )
        """)
        # Everything that predates orgs belongs to org_default; the backfill runs only once,
        # when the column is first added. (notification_retention_policy is rebuilt above.)
        for table in ("security_notifications", "notification_retention_events",
                      "notification_retention_tombstones"):
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if "org_id" not in columns:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN org_id TEXT")
                connection.execute(f"UPDATE {table} SET org_id = 'org_default'")


def sync_notifications() -> int:
    """Create one deduplicated notification for every security alert, in the alert's own org.

    Install-level derivation across every org (like alerts.sync_alerts_from_events()): each
    notification inherits its alert's org_id, never the caller's."""
    initialize_notification_database()
    from .alerts import get_alerts

    alerts = get_alerts(limit=500, org_id=ALL_ORGS)["alerts"]
    created = 0
    with sqlite3.connect(database_path) as connection:
        for alert in alerts:
            alert_id = str(alert["alert_id"])
            cursor = connection.execute("""
                INSERT OR IGNORE INTO security_notifications (
                    notification_id, source_alert_id, created_at, severity,
                    title, message, resource_path, org_id
                ) SELECT ?, ?, ?, ?, ?, ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM notification_retention_tombstones
                    WHERE source_alert_id = ?
                )
            """, (
                "ntf_" + uuid.uuid4().hex,
                alert_id,
                str(alert["created_at"]),
                str(alert["severity"]),
                str(alert["title"]),
                str(alert["summary"]),
                f"/incidents?alert={alert_id}",
                alert.get("org_id"),
                alert_id,
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
    *,
    org_id,
    include_install_level: bool = False,
) -> dict[str, Any]:
    sync_notifications()
    cleanup_expired_notifications("system", automatic=True, org_id=org_id,
                                  include_install_level=include_install_level)
    visible, visible_parameters = _visibility(org_id, include_install_level)
    clauses: list[str] = [visible]
    parameters: list[Any] = list(visible_parameters)
    if unread_only:
        clauses.append("is_read = 0")
    if severity:
        clauses.append("severity = ?")
        parameters.append(severity.strip().upper())
    where = " WHERE " + " AND ".join(clauses)
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


def notification_summary(*, org_id, include_install_level: bool = False) -> dict[str, int]:
    sync_notifications()
    cleanup_expired_notifications("system", automatic=True, org_id=org_id,
                                  include_install_level=include_install_level)
    visible, visible_parameters = _visibility(org_id, include_install_level)
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(f"""
            SELECT COUNT(*),
                SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END),
                SUM(CASE WHEN is_read = 0 AND severity = 'CRITICAL' THEN 1 ELSE 0 END),
                SUM(CASE WHEN is_read = 0 AND severity = 'HIGH' THEN 1 ELSE 0 END)
            FROM security_notifications WHERE {visible}
        """, visible_parameters).fetchone()
    return {
        "total": row[0] or 0,
        "unread": row[1] or 0,
        "unread_critical": row[2] or 0,
        "unread_high": row[3] or 0,
    }


def mark_notification_read(notification_id: str, actor: str, *, org_id,
                           include_install_level: bool = False) -> dict[str, Any]:
    timestamp = utc_now()
    visible, visible_parameters = _visibility(org_id, include_install_level)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(f"""
            UPDATE security_notifications
            SET is_read = 1, read_at = COALESCE(read_at, ?),
                read_by = COALESCE(read_by, ?)
            WHERE notification_id = ? AND {visible}
        """, (timestamp, actor, notification_id, *visible_parameters))
        if cursor.rowcount == 0:
            raise KeyError("Notification not found.")
        row = connection.execute(
            f"SELECT * FROM security_notifications WHERE notification_id = ? AND {visible}",
            (notification_id, *visible_parameters),
        ).fetchone()
    return _serialize(row)


def mark_all_notifications_read(actor: str, *, org_id, include_install_level: bool = False) -> int:
    timestamp = utc_now()
    visible, visible_parameters = _visibility(org_id, include_install_level)
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(f"""
            UPDATE security_notifications
            SET is_read = 1, read_at = ?, read_by = ?
            WHERE is_read = 0 AND {visible}
        """, (timestamp, actor, *visible_parameters))
    return cursor.rowcount


def get_retention_policy(org_id) -> dict[str, Any]:
    initialize_notification_database()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        # Each org gets the default policy the first time it is read.
        connection.execute("""
            INSERT OR IGNORE INTO notification_retention_policy
                (id, org_id, retention_days, updated_at, updated_by)
            VALUES (1, ?, ?, ?, 'system-default')
        """, (org_id, DEFAULT_RETENTION_DAYS, utc_now()))
        row = connection.execute(
            "SELECT retention_days, updated_at, updated_by FROM notification_retention_policy "
            "WHERE id = 1 AND org_id = ?",
            (org_id,),
        ).fetchone()
    return dict(row)


def update_retention_policy(retention_days: int, actor: str, org_id) -> dict[str, Any]:
    days = int(retention_days)
    if days < 7 or days > 3650:
        raise ValueError("Notification retention must be between 7 and 3650 days.")
    get_retention_policy(org_id)
    timestamp = utc_now()
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            UPDATE notification_retention_policy
            SET retention_days = ?, updated_at = ?, updated_by = ? WHERE id = 1 AND org_id = ?
        """, (days, timestamp, actor, org_id))
        connection.execute("""
            INSERT INTO notification_retention_events
                (timestamp, actor, action, retention_days, deleted_count, org_id)
            VALUES (?, ?, 'POLICY_UPDATED', ?, 0, ?)
        """, (timestamp, actor, days, org_id))
    return get_retention_policy(org_id)


def _expire(connection, scope: str, scope_parameters: tuple, cutoff: str, timestamp: str) -> int:
    expired = connection.execute(
        f"SELECT source_alert_id, org_id FROM security_notifications WHERE created_at < ? AND {scope}",
        (cutoff, *scope_parameters),
    ).fetchall()
    connection.executemany(
        "INSERT OR IGNORE INTO notification_retention_tombstones (source_alert_id, expired_at, org_id) VALUES (?, ?, ?)",
        [(row[0], timestamp, row[1]) for row in expired],
    )
    return connection.execute(
        f"DELETE FROM security_notifications WHERE created_at < ? AND {scope}",
        (cutoff, *scope_parameters),
    ).rowcount


def cleanup_expired_notifications(actor: str, automatic: bool = False, *, org_id,
                                  include_install_level: bool = False) -> dict[str, Any]:
    """Apply one org's retention policy to that org's notifications only. An install operator's
    pass (include_install_level) also expires install-level notifications, on their own fixed
    INSTALL_LEVEL_RETENTION_DAYS."""
    policy = get_retention_policy(org_id)
    days = int(policy["retention_days"])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    timestamp = utc_now()
    with sqlite3.connect(database_path) as connection:
        deleted = _expire(connection, "org_id = ?", (org_id,), cutoff, timestamp)
        if include_install_level:
            install_cutoff = (datetime.now(timezone.utc) - timedelta(days=INSTALL_LEVEL_RETENTION_DAYS)).isoformat()
            _expire(connection, "org_id IS NULL", (), install_cutoff, timestamp)
        if deleted or not automatic:
            connection.execute("""
                INSERT INTO notification_retention_events
                    (timestamp, actor, action, retention_days, deleted_count, org_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (timestamp, actor, "AUTOMATIC_CLEANUP" if automatic else "MANUAL_CLEANUP", days, deleted, org_id))
    return {"deleted": deleted, "retention_days": days, "cutoff": cutoff, "automatic": automatic}


def retention_history(limit: int = 20, *, org_id) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 100))
    initialize_notification_database()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT timestamp, actor, action, retention_days, deleted_count
            FROM notification_retention_events WHERE org_id = ? ORDER BY id DESC LIMIT ?
        """, (org_id, safe_limit)).fetchall()
    return [dict(row) for row in rows]
