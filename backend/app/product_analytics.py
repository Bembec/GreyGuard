"""Privacy-safe product analytics for customer success (P5).

Rules, from the commercial roadmap addendum: product analytics must exclude prompts, secrets and
sensitive payloads, and must be disableable where required.

- Adoption is computed from data the product already holds, as counts only: how many agents,
  requests and decisions, approvals, integrations, reports, exports and active members. Nothing
  about what an agent asked for - no targets, payloads, results, names or prompts - is read.
- The only data collected for analytics is a daily page-view count per org and page path. A path
  must be a fixed navigation path (lowercase letters, digits and hyphens - no identifiers, query
  strings or values); no user, session or IP address is recorded; at most MAX_PATHS_PER_DAY paths
  per org per day.
- Off for the whole install with GREYGUARD_PRODUCT_ANALYTICS=off. Off for one org by its owners;
  turning it off also deletes the page-view counts already collected for that org.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db_compat as sqlite3
from .database import database_path

PATH_PATTERN = re.compile(r"^/(?:[a-z][a-z0-9-]{0,40})(?:/[a-z][a-z0-9-]{0,40})?$")
MAX_PATHS_PER_DAY = 100
RETENTION_DAYS = 400
EXCLUDED = ("agent prompts, request targets and payloads", "tool results", "secrets and credentials",
            "user, session and IP identifiers", "page URLs beyond fixed navigation paths")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def install_enabled() -> bool:
    return os.getenv("GREYGUARD_PRODUCT_ANALYTICS", "on").strip().lower() not in ("off", "false", "0", "no")


def initialize_product_analytics() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS product_usage_daily (
            org_id TEXT NOT NULL, day TEXT NOT NULL, path TEXT NOT NULL, views INTEGER NOT NULL,
            PRIMARY KEY (org_id, day, path))""")
        connection.execute("""CREATE TABLE IF NOT EXISTS product_analytics_settings (
            org_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL, updated_by TEXT NOT NULL, updated_at TEXT NOT NULL)""")


def org_enabled(org_id: str) -> bool:
    if not install_enabled():
        return False
    sqlite3.initialize_once("product_analytics", database_path, initialize_product_analytics)
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT enabled FROM product_analytics_settings WHERE org_id = ?", (org_id,)).fetchone()
    return True if row is None else bool(row[0])


def record_page_view(org_id: str, path: str) -> bool:
    """Count one view of a fixed navigation path. Returns False when nothing was recorded."""
    if not PATH_PATTERN.fullmatch(str(path)) or not org_enabled(org_id):
        return False
    day = utc_now().strftime("%Y-%m-%d")
    with sqlite3.connect(database_path) as connection:
        updated = connection.execute(
            "UPDATE product_usage_daily SET views = views + 1 WHERE org_id = ? AND day = ? AND path = ?",
            (org_id, day, path)).rowcount
        if updated:
            return True
        paths = connection.execute("SELECT COUNT(*) FROM product_usage_daily WHERE org_id = ? AND day = ?",
                                   (org_id, day)).fetchone()[0]
        if paths >= MAX_PATHS_PER_DAY:
            return False
        connection.execute("INSERT OR IGNORE INTO product_usage_daily (org_id, day, path, views) VALUES (?, ?, ?, 0)",
                           (org_id, day, path))
        connection.execute("UPDATE product_usage_daily SET views = views + 1 WHERE org_id = ? AND day = ? AND path = ?",
                           (org_id, day, path))
        # Keep the table bounded.
        cutoff = (utc_now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
        connection.execute("DELETE FROM product_usage_daily WHERE org_id = ? AND day < ?", (org_id, cutoff))
    return True


def set_org_enabled(org_id: str, enabled: bool, actor: str) -> dict[str, Any]:
    initialize_product_analytics()
    now = utc_now().isoformat()
    with sqlite3.connect(database_path) as connection:
        if not connection.execute("UPDATE product_analytics_settings SET enabled = ?, updated_by = ?, updated_at = ? WHERE org_id = ?",
                                  (int(enabled), actor, now, org_id)).rowcount:
            connection.execute("INSERT INTO product_analytics_settings (org_id, enabled, updated_by, updated_at) VALUES (?, ?, ?, ?)",
                               (org_id, int(enabled), actor, now))
        if not enabled:
            connection.execute("DELETE FROM product_usage_daily WHERE org_id = ?", (org_id,))
    return {"org_id": org_id, "enabled": org_enabled(org_id), "install_enabled": install_enabled()}


def _count(connection, sql, params) -> int:
    try:
        return connection.execute(sql, params).fetchone()[0] or 0
    except sqlite3.Error:  # a module whose table does not exist on this install yet
        return 0


def adoption(org_id: str, days: int = 30) -> dict[str, Any]:
    """Counts only - never contents - over the last `days` days."""
    initialize_product_analytics()
    since = (utc_now() - timedelta(days=days)).isoformat()
    since_day = since[:10]
    with sqlite3.connect(database_path) as connection:
        decisions = {row[0]: row[1] for row in connection.execute(
            "SELECT policy_decision, COUNT(*) FROM tool_requests WHERE org_id = ? AND timestamp >= ? GROUP BY policy_decision",
            (org_id, since)).fetchall()}
        metrics = {
            "agents": _count(connection, "SELECT COUNT(*) FROM agent_identities WHERE org_id = ?", (org_id,)),
            "active_agents": _count(connection, "SELECT COUNT(DISTINCT agent_name) FROM tool_requests WHERE org_id = ? AND timestamp >= ?", (org_id, since)),
            "controlled_requests": sum(decisions.values()),
            "decisions": decisions,
            "approvals_decided": _count(connection, "SELECT COUNT(*) FROM approval_events WHERE org_id = ? AND timestamp >= ?", (org_id, since)),
            "integrations": _count(connection, "SELECT (SELECT COUNT(*) FROM export_destinations WHERE org_id = ?) + (SELECT COUNT(*) FROM incident_destinations WHERE org_id = ?) + (SELECT COUNT(*) FROM notification_destinations WHERE org_id = ?)", (org_id, org_id, org_id)),
            "compliance_reports": _count(connection, "SELECT COUNT(*) FROM compliance_reports WHERE org_id = ? AND created_at >= ?", (org_id, since)),
            "gateways": _count(connection, "SELECT COUNT(*) FROM gateway_nodes WHERE org_id = ? AND status = 'ACTIVE'", (org_id,)),
            "members": _count(connection, "SELECT COUNT(*) FROM org_memberships WHERE org_id = ? AND status = 'ACTIVE'", (org_id,)),
            "members_signed_in": _count(connection, "SELECT COUNT(*) FROM org_memberships m JOIN administrators a ON a.admin_id = m.admin_id WHERE m.org_id = ? AND m.status = 'ACTIVE' AND a.last_login_at >= ?", (org_id, since)),
            "org_exports": _count(connection, "SELECT COUNT(*) FROM org_lifecycle_events WHERE org_id = ? AND event_type = 'EXPORTED' AND timestamp >= ?", (org_id, since)),
        }
        pages = [{"path": row[0], "views": row[1]} for row in connection.execute(
            "SELECT path, SUM(views) FROM product_usage_daily WHERE org_id = ? AND day >= ? GROUP BY path ORDER BY SUM(views) DESC, path LIMIT 20",
            (org_id, since_day)).fetchall()]
    return {"org_id": org_id, "days": days, "metrics": metrics, "page_views": pages,
            "analytics_enabled": org_enabled(org_id), "install_enabled": install_enabled(), "never_collected": list(EXCLUDED)}
