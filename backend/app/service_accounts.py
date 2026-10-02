"""Machine identities and one-time API key lifecycle management."""

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .database import database_path


AVAILABLE_SCOPES = {
    "agents:read",
    "alerts:read",
    "audit:read",
    "policy:read",
    "tools:execute",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize_service_accounts() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS service_accounts (
                account_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                scopes_json TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                last_used_at TEXT,
                use_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS service_account_keys (
                key_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                key_prefix TEXT NOT NULL UNIQUE,
                key_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                revoked_at TEXT,
                last_used_at TEXT,
                use_count INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(account_id) REFERENCES service_accounts(account_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS service_account_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                key_id TEXT,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detail TEXT NOT NULL
            )
        """)


def _normalize_scopes(scopes: list[str]) -> list[str]:
    normalized = sorted({str(scope).strip().lower() for scope in scopes if str(scope).strip()})
    if not normalized:
        raise ValueError("At least one service-account scope is required.")
    unsupported = sorted(set(normalized) - AVAILABLE_SCOPES)
    if unsupported:
        raise ValueError("Unsupported service-account scope: " + ", ".join(unsupported))
    return normalized


def _expires_at(days: int | None) -> str | None:
    if days is None:
        return None
    if days < 1 or days > 365:
        raise ValueError("Expiration must be between 1 and 365 days.")
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _event(connection, account_id, key_id, actor, event_type, detail=""):
    connection.execute("""
        INSERT INTO service_account_events (
            account_id, key_id, timestamp, actor, event_type, detail
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (account_id, key_id, utc_now(), actor, event_type, detail))


def _issue_key(connection, account_id: str, expires_at: str | None, actor: str) -> dict[str, str | None]:
    key_id = "sak_" + uuid.uuid4().hex
    prefix = "ggsa_" + secrets.token_hex(5)
    plaintext = prefix + "_" + secrets.token_urlsafe(32)
    connection.execute("""
        INSERT INTO service_account_keys (
            key_id, account_id, key_prefix, key_hash, status,
            created_at, expires_at
        ) VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?)
    """, (
        key_id, account_id, prefix,
        hashlib.sha256(plaintext.encode("utf-8")).hexdigest(),
        utc_now(), expires_at,
    ))
    _event(connection, account_id, key_id, actor, "API_KEY_ISSUED", "API key revealed once.")
    return {"key_id": key_id, "api_key": plaintext, "key_prefix": prefix, "expires_at": expires_at}


def _keys(connection, account_id: str) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute("""
        SELECT key_id, key_prefix, status, created_at, expires_at,
               revoked_at, last_used_at, use_count
        FROM service_account_keys WHERE account_id = ?
        ORDER BY created_at DESC
    """, (account_id,)).fetchall()
    return [dict(row) for row in rows]


def _public(connection, row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["scopes"] = json.loads(result.pop("scopes_json"))
    result["keys"] = _keys(connection, result["account_id"])
    return result


def get_service_account(account_id: str) -> dict[str, Any]:
    initialize_service_accounts()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM service_accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
        if row is None:
            raise KeyError("Service account not found.")
        return _public(connection, row)


def list_service_accounts() -> list[dict[str, Any]]:
    initialize_service_accounts()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM service_accounts ORDER BY created_at DESC"
        ).fetchall()
        return [_public(connection, row) for row in rows]


def create_service_account(
    name: str,
    description: str,
    scopes: list[str],
    expires_in_days: int | None,
    actor: str,
) -> dict[str, Any]:
    initialize_service_accounts()
    normalized_name = str(name).strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 _.-]{2,99}", normalized_name):
        raise ValueError("Service-account name must contain 3-100 safe characters.")
    normalized_scopes = _normalize_scopes(scopes)
    account_id = "svc_" + uuid.uuid4().hex
    timestamp = utc_now()
    expiration = _expires_at(expires_in_days)
    try:
        with sqlite3.connect(database_path) as connection:
            connection.execute("""
                INSERT INTO service_accounts (
                    account_id, name, description, status, scopes_json,
                    created_by, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?)
            """, (
                account_id, normalized_name, str(description).strip(),
                json.dumps(normalized_scopes), actor, timestamp, timestamp, expiration,
            ))
            issued = _issue_key(connection, account_id, expiration, actor)
            _event(connection, account_id, issued["key_id"], actor, "SERVICE_ACCOUNT_CREATED", "Machine identity created.")
    except sqlite3.IntegrityError as error:
        raise ValueError("A service account with this name already exists.") from error
    result = get_service_account(account_id)
    result["issued_key"] = issued
    return result


def rotate_service_account_key(account_id: str, expires_in_days: int | None, actor: str) -> dict[str, Any]:
    account = get_service_account(account_id)
    if account["status"] != "ACTIVE":
        raise ValueError("Revoked service accounts cannot rotate keys.")
    expiration = _expires_at(expires_in_days) if expires_in_days is not None else account["expires_at"]
    timestamp = utc_now()
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            UPDATE service_account_keys SET status = 'REVOKED', revoked_at = ?
            WHERE account_id = ? AND status = 'ACTIVE'
        """, (timestamp, account_id))
        issued = _issue_key(connection, account_id, expiration, actor)
        connection.execute(
            "UPDATE service_accounts SET updated_at = ?, expires_at = ? WHERE account_id = ?",
            (timestamp, expiration, account_id),
        )
        _event(connection, account_id, issued["key_id"], actor, "API_KEY_ROTATED", "Previous active keys revoked.")
    result = get_service_account(account_id)
    result["issued_key"] = issued
    return result


def revoke_service_account(account_id: str, actor: str) -> dict[str, Any]:
    get_service_account(account_id)
    timestamp = utc_now()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE service_accounts SET status = 'REVOKED', updated_at = ? WHERE account_id = ?",
            (timestamp, account_id),
        )
        connection.execute("""
            UPDATE service_account_keys SET status = 'REVOKED', revoked_at = COALESCE(revoked_at, ?)
            WHERE account_id = ? AND status = 'ACTIVE'
        """, (timestamp, account_id))
        _event(connection, account_id, None, actor, "SERVICE_ACCOUNT_REVOKED", "All API keys revoked.")
    return get_service_account(account_id)


def authenticate_service_key(api_key: str, required_scope: str | None = None) -> dict[str, Any]:
    initialize_service_accounts()
    if (
        not api_key
        or not re.fullmatch(r"ggsa_[0-9a-f]{10}_[A-Za-z0-9_-]{32,}", api_key)
    ):
        raise ValueError("Service API key is invalid.")
    prefix = api_key[:15]
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    now = utc_now()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("""
            SELECT a.*, k.key_id, k.key_hash, k.status AS key_status,
                   k.expires_at AS key_expires_at
            FROM service_account_keys k
            JOIN service_accounts a ON a.account_id = k.account_id
            WHERE k.key_prefix = ?
        """, (prefix,)).fetchone()
        if row is None or not hmac.compare_digest(digest, row["key_hash"]):
            raise ValueError("Service API key is invalid.")
        if row["status"] != "ACTIVE" or row["key_status"] != "ACTIVE":
            raise ValueError("Service API key is revoked.")
        expiration = row["key_expires_at"] or row["expires_at"]
        if expiration and expiration <= now:
            raise ValueError("Service API key has expired.")
        scopes = json.loads(row["scopes_json"])
        if required_scope and required_scope not in scopes:
            raise PermissionError("Service account lacks the required scope.")
        connection.execute("""
            UPDATE service_account_keys SET last_used_at = ?, use_count = use_count + 1
            WHERE key_id = ?
        """, (now, row["key_id"]))
        connection.execute("""
            UPDATE service_accounts SET last_used_at = ?, use_count = use_count + 1
            WHERE account_id = ?
        """, (now, row["account_id"]))
        _event(connection, row["account_id"], row["key_id"], row["name"], "API_KEY_USED", required_scope or "Identity verified.")
        result = {
            "account_id": row["account_id"], "name": row["name"],
            "status": row["status"], "scopes": scopes,
            "authenticated": True,
        }
    return result
