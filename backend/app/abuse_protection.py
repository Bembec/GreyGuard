"""Persistent request throttling, authentication lockouts, and burst evidence."""

import hashlib
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .database import database_path


DEFAULT_POLICIES = {
    "ADMIN_AUTH": {"request_limit": 20, "window_seconds": 300, "block_seconds": 900, "max_failed_attempts": 5},
    "SERVICE_ACCOUNT": {"request_limit": 60, "window_seconds": 60, "block_seconds": 300, "max_failed_attempts": 5},
    "AGENT_ACTION": {"request_limit": 120, "window_seconds": 60, "block_seconds": 300, "max_failed_attempts": 10},
    "GENERAL": {"request_limit": 300, "window_seconds": 60, "block_seconds": 60, "max_failed_attempts": 10},
}


def utc_now_datetime() -> datetime:
    return datetime.now(timezone.utc)


def utc_now() -> str:
    return utc_now_datetime().isoformat()


def initialize_abuse_protection() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_policies (
                category TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                request_limit INTEGER NOT NULL,
                window_seconds INTEGER NOT NULL,
                block_seconds INTEGER NOT NULL,
                max_failed_attempts INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                updated_by TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_counters (
                identifier_hash TEXT NOT NULL,
                category TEXT NOT NULL,
                window_started_at TEXT NOT NULL,
                request_count INTEGER NOT NULL DEFAULT 0,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                blocked_until TEXT,
                last_seen_at TEXT NOT NULL,
                burst_recorded INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(identifier_hash, category)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS abuse_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                identifier_hint TEXT NOT NULL,
                request_count INTEGER NOT NULL,
                detail TEXT NOT NULL
            )
        """)
        timestamp = utc_now()
        for category, policy in DEFAULT_POLICIES.items():
            connection.execute("""
                INSERT OR IGNORE INTO rate_limit_policies (
                    category, enabled, request_limit, window_seconds,
                    block_seconds, max_failed_attempts, updated_at, updated_by
                ) VALUES (?, 1, ?, ?, ?, ?, ?, 'system')
            """, (
                category, policy["request_limit"], policy["window_seconds"],
                policy["block_seconds"], policy["max_failed_attempts"], timestamp,
            ))


def _identifier(identifier: str) -> tuple[str, str]:
    normalized = str(identifier or "anonymous").strip() or "anonymous"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    if normalized.startswith("ggsa_"):
        hint = normalized[:15]
    elif "@" in normalized:
        name, _, domain = normalized.partition("@")
        hint = (name[:2] + "***@" + domain)[:80]
    else:
        hint = normalized[:3] + "***" if len(normalized) > 3 else "anonymous"
    return digest, hint


def _policy(connection, category: str) -> sqlite3.Row:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT * FROM rate_limit_policies WHERE category = ?", (category,)
    ).fetchone()
    if row is None:
        raise ValueError("Unknown rate-limit category.")
    return row


def _event(connection, category, event_type, severity, hint, count, detail):
    connection.execute("""
        INSERT INTO abuse_events (
            event_id, timestamp, category, event_type, severity,
            identifier_hint, request_count, detail
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ("abe_" + uuid.uuid4().hex, utc_now(), category, event_type, severity, hint, count, detail))


def check_rate_limit(identifier: str, category: str = "GENERAL") -> dict[str, Any]:
    """Consume one request and return an allow/block decision."""
    initialize_abuse_protection()
    normalized_category = str(category).upper()
    identifier_hash, hint = _identifier(identifier)
    now = utc_now_datetime()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        policy = _policy(connection, normalized_category)
        if not policy["enabled"]:
            return {"allowed": True, "remaining": policy["request_limit"], "retry_after": 0}
        row = connection.execute("""
            SELECT * FROM rate_limit_counters
            WHERE identifier_hash = ? AND category = ?
        """, (identifier_hash, normalized_category)).fetchone()
        if row and row["blocked_until"]:
            blocked_until = datetime.fromisoformat(row["blocked_until"])
            if blocked_until > now:
                return {"allowed": False, "remaining": 0, "retry_after": max(1, int((blocked_until - now).total_seconds()))}
        window_start = now
        count = 1
        failed = row["failed_attempts"] if row else 0
        burst_recorded = 0
        if row:
            existing_start = datetime.fromisoformat(row["window_started_at"])
            if (now - existing_start).total_seconds() < policy["window_seconds"]:
                window_start = existing_start
                count = row["request_count"] + 1
                burst_recorded = row["burst_recorded"]
        blocked_until = None
        if count > policy["request_limit"]:
            blocked_until = (now + timedelta(seconds=policy["block_seconds"])).isoformat()
            _event(connection, normalized_category, "RATE_LIMIT_EXCEEDED", "HIGH", hint, count, "Request quota exceeded; temporary block applied.")
        elif count >= max(2, int(policy["request_limit"] * 0.8)) and not burst_recorded:
            burst_recorded = 1
            _event(connection, normalized_category, "SUSPICIOUS_BURST", "MEDIUM", hint, count, "Request volume reached 80 percent of the configured limit.")
        connection.execute("""
            INSERT INTO rate_limit_counters (
                identifier_hash, category, window_started_at, request_count,
                failed_attempts, blocked_until, last_seen_at, burst_recorded
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(identifier_hash, category) DO UPDATE SET
                window_started_at=excluded.window_started_at,
                request_count=excluded.request_count,
                failed_attempts=excluded.failed_attempts,
                blocked_until=excluded.blocked_until,
                last_seen_at=excluded.last_seen_at,
                burst_recorded=excluded.burst_recorded
        """, (
            identifier_hash, normalized_category, window_start.isoformat(), count,
            failed, blocked_until, now.isoformat(), burst_recorded,
        ))
        return {
            "allowed": blocked_until is None,
            "remaining": max(0, policy["request_limit"] - count),
            "retry_after": policy["block_seconds"] if blocked_until else 0,
        }


def record_authentication_failure(identifier: str, category: str = "ADMIN_AUTH") -> dict[str, Any]:
    initialize_abuse_protection()
    identifier_hash, hint = _identifier(identifier)
    normalized_category = category.upper()
    now = utc_now_datetime()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        policy = _policy(connection, normalized_category)
        row = connection.execute("""
            SELECT * FROM rate_limit_counters
            WHERE identifier_hash = ? AND category = ?
        """, (identifier_hash, normalized_category)).fetchone()
        failures = (row["failed_attempts"] if row else 0) + 1
        blocked_until = row["blocked_until"] if row else None
        if failures >= policy["max_failed_attempts"]:
            blocked_until = (now + timedelta(seconds=policy["block_seconds"])).isoformat()
            _event(connection, normalized_category, "AUTHENTICATION_LOCKOUT", "HIGH", hint, failures, "Failed-authentication threshold reached.")
        connection.execute("""
            INSERT INTO rate_limit_counters (
                identifier_hash, category, window_started_at, request_count,
                failed_attempts, blocked_until, last_seen_at, burst_recorded
            ) VALUES (?, ?, ?, 0, ?, ?, ?, 0)
            ON CONFLICT(identifier_hash, category) DO UPDATE SET
                failed_attempts=excluded.failed_attempts,
                blocked_until=excluded.blocked_until,
                last_seen_at=excluded.last_seen_at
        """, (identifier_hash, normalized_category, now.isoformat(), failures, blocked_until, now.isoformat()))
    return {"failed_attempts": failures, "locked": bool(blocked_until)}


def clear_authentication_failures(identifier: str, category: str = "ADMIN_AUTH") -> None:
    identifier_hash, _ = _identifier(identifier)
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            UPDATE rate_limit_counters SET failed_attempts = 0, blocked_until = NULL
            WHERE identifier_hash = ? AND category = ?
        """, (identifier_hash, category.upper()))


def list_policies() -> list[dict[str, Any]]:
    initialize_abuse_protection()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM rate_limit_policies ORDER BY category").fetchall()
    return [{**dict(row), "enabled": bool(row["enabled"])} for row in rows]


def update_policy(category: str, values: dict[str, Any], actor: str) -> dict[str, Any]:
    normalized = category.upper()
    required = ("request_limit", "window_seconds", "block_seconds", "max_failed_attempts")
    if any(int(values[name]) < 1 for name in required):
        raise ValueError("Rate-limit values must be positive integers.")
    if int(values["request_limit"]) > 10000 or int(values["window_seconds"]) > 86400 or int(values["block_seconds"]) > 86400:
        raise ValueError("Rate-limit policy exceeds the supported safety range.")
    initialize_abuse_protection()
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute("""
            UPDATE rate_limit_policies SET enabled=?, request_limit=?,
                window_seconds=?, block_seconds=?, max_failed_attempts=?,
                updated_at=?, updated_by=? WHERE category=?
        """, (
            int(bool(values["enabled"])), int(values["request_limit"]),
            int(values["window_seconds"]), int(values["block_seconds"]),
            int(values["max_failed_attempts"]), utc_now(), actor, normalized,
        ))
        if cursor.rowcount == 0:
            raise KeyError("Rate-limit policy not found.")
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM rate_limit_policies WHERE category=?", (normalized,)
        ).fetchone()
    return {**dict(row), "enabled": bool(row["enabled"])}


def list_abuse_events(limit: int = 100) -> list[dict[str, Any]]:
    initialize_abuse_protection()
    safe_limit = max(1, min(int(limit), 500))
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM abuse_events ORDER BY timestamp DESC LIMIT ?", (safe_limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def abuse_summary() -> dict[str, int]:
    initialize_abuse_protection()
    now = utc_now()
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("""
            SELECT COUNT(*),
                SUM(CASE WHEN event_type='RATE_LIMIT_EXCEEDED' THEN 1 ELSE 0 END),
                SUM(CASE WHEN event_type='AUTHENTICATION_LOCKOUT' THEN 1 ELSE 0 END),
                SUM(CASE WHEN event_type='SUSPICIOUS_BURST' THEN 1 ELSE 0 END)
            FROM abuse_events
        """).fetchone()
        active = connection.execute(
            "SELECT COUNT(*) FROM rate_limit_counters WHERE blocked_until > ?", (now,)
        ).fetchone()[0]
    return {"events": row[0] or 0, "quota_blocks": row[1] or 0, "auth_lockouts": row[2] or 0, "bursts": row[3] or 0, "active_blocks": active}
