"""GreyGuard administrator identities, sessions, and role permissions."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .database import database_path as greyguard_database_path


database_path = greyguard_database_path
SESSION_HOURS = 8
ROLES = {
    "PLATFORM_ADMIN": {
        "read", "incident:manage", "approval:manage", "identity:manage", "admin:manage"
    },
    "SECURITY_ANALYST": {"read", "incident:manage", "approval:manage"},
    "AUDITOR": {"read"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize_admin_auth() -> None:
    """Create administrator and session tables and optional bootstrap account."""
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS administrators (
                admin_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL,
                last_login_at TEXT
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS administrator_sessions (
                session_id TEXT PRIMARY KEY,
                admin_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                FOREIGN KEY (admin_id) REFERENCES administrators(admin_id)
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_admin_sessions_token ON administrator_sessions(token_hash)")

    email = os.getenv("GREYGUARD_BOOTSTRAP_EMAIL")
    password = os.getenv("GREYGUARD_BOOTSTRAP_PASSWORD")
    if email and password:
        create_administrator(
            email=email,
            display_name=os.getenv("GREYGUARD_BOOTSTRAP_NAME", "Platform Administrator"),
            role="PLATFORM_ADMIN",
            password=password,
            ignore_existing=True,
        )


def _password_digest(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000).hex()


def _public_admin(row: sqlite3.Row) -> dict:
    return {
        "admin_id": row["admin_id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "status": row["status"],
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
        "permissions": sorted(ROLES.get(row["role"], set())),
    }


def create_administrator(email, display_name, role, password, ignore_existing=False) -> dict:
    normalized_email = str(email).strip().lower()
    normalized_name = str(display_name).strip()
    normalized_role = str(role).strip().upper()
    if "@" not in normalized_email or not normalized_name:
        raise ValueError("A valid email and display name are required.")
    if normalized_role not in ROLES:
        raise ValueError("Unknown administrator role.")
    if len(str(password)) < 12:
        raise ValueError("Administrator password must contain at least 12 characters.")
    salt = secrets.token_bytes(16)
    admin_id = "adm_" + secrets.token_hex(12)
    timestamp = utc_now()
    try:
        with sqlite3.connect(database_path) as connection:
            connection.execute("""
                INSERT INTO administrators (
                    admin_id,email,display_name,role,password_salt,password_hash,status,created_at
                ) VALUES (?,?,?,?,?,?, 'ACTIVE', ?)
            """, (
                admin_id, normalized_email, normalized_name, normalized_role,
                salt.hex(), _password_digest(str(password), salt), timestamp,
            ))
    except sqlite3.IntegrityError:
        if not ignore_existing:
            raise ValueError("An administrator with this email already exists.")
    return get_administrator_by_email(normalized_email)


def get_administrator_by_email(email: str) -> dict | None:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM administrators WHERE email = ? COLLATE NOCASE",
            (email.strip(),),
        ).fetchone()
    return _public_admin(row) if row else None


def list_administrators() -> list[dict]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM administrators ORDER BY created_at").fetchall()
    return [_public_admin(row) for row in rows]


def authenticate(email: str, password: str) -> dict:
    initialize_admin_auth()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM administrators WHERE email = ? COLLATE NOCASE",
            (email.strip(),),
        ).fetchone()
        if not row or row["status"] != "ACTIVE":
            raise ValueError("Administrator authentication failed.")
        actual = _password_digest(password, bytes.fromhex(row["password_salt"]))
        if not hmac.compare_digest(actual, row["password_hash"]):
            raise ValueError("Administrator authentication failed.")
        token = "gga_" + secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session_id = "ses_" + secrets.token_hex(12)
        created = datetime.now(timezone.utc)
        expires = created + timedelta(hours=SESSION_HOURS)
        connection.execute(
            "INSERT INTO administrator_sessions VALUES (?,?,?,?,?,NULL)",
            (session_id, row["admin_id"], token_hash, created.isoformat(), expires.isoformat()),
        )
        connection.execute(
            "UPDATE administrators SET last_login_at = ? WHERE admin_id = ?",
            (created.isoformat(), row["admin_id"]),
        )
        user = _public_admin(row)
        user["last_login_at"] = created.isoformat()
    return {"access_token": token, "token_type": "session", "expires_at": expires.isoformat(), "administrator": user}


def validate_session(token: str) -> dict:
    if not token or not token.startswith("gga_"):
        raise ValueError("Administrator session is invalid.")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("""
            SELECT a.* FROM administrator_sessions s
            JOIN administrators a ON a.admin_id = s.admin_id
            WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?
              AND a.status = 'ACTIVE'
        """, (token_hash, utc_now())).fetchone()
    if not row:
        raise ValueError("Administrator session has expired or was revoked.")
    return _public_admin(row)


def revoke_session(token: str) -> bool:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            "UPDATE administrator_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
            (utc_now(), token_hash),
        )
    return cursor.rowcount > 0


def has_permission(administrator: dict, permission: str) -> bool:
    return permission in ROLES.get(administrator.get("role", ""), set())


def required_permission(method: str, path: str) -> str:
    if method.upper() == "GET":
        return "read"
    if path.startswith("/alerts") or path.startswith("/notifications"):
        return "incident:manage"
    if path.startswith("/tool-requests/") and path.endswith("/decision"):
        return "approval:manage"
    if path.startswith("/agents"):
        return "identity:manage"
    if path.startswith("/service-accounts"):
        return "admin:manage"
    return "admin:manage"


def get_administrator(admin_id: str) -> dict:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM administrators WHERE admin_id = ?", (admin_id,)
        ).fetchone()
    if not row:
        raise KeyError("Administrator not found.")
    return _public_admin(row)


def _active_platform_admin_count(connection: sqlite3.Connection) -> int:
    return connection.execute(
        "SELECT COUNT(*) FROM administrators WHERE role = 'PLATFORM_ADMIN' AND status = 'ACTIVE'"
    ).fetchone()[0]


def update_administrator(admin_id, display_name=None, role=None, status=None) -> dict:
    """Update an operator while preserving at least one active platform administrator."""
    normalized_role = str(role).strip().upper() if role is not None else None
    normalized_status = str(status).strip().upper() if status is not None else None
    if normalized_role is not None and normalized_role not in ROLES:
        raise ValueError("Unknown administrator role.")
    if normalized_status is not None and normalized_status not in {"ACTIVE", "DISABLED"}:
        raise ValueError("Administrator status must be ACTIVE or DISABLED.")
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        current = connection.execute(
            "SELECT * FROM administrators WHERE admin_id = ?", (admin_id,)
        ).fetchone()
        if not current:
            raise KeyError("Administrator not found.")
        resulting_role = normalized_role or current["role"]
        resulting_status = normalized_status or current["status"]
        removes_platform_admin = (
            current["role"] == "PLATFORM_ADMIN"
            and current["status"] == "ACTIVE"
            and (resulting_role != "PLATFORM_ADMIN" or resulting_status != "ACTIVE")
        )
        if removes_platform_admin and _active_platform_admin_count(connection) <= 1:
            raise ValueError("The final active Platform Administrator cannot be removed or disabled.")
        normalized_name = current["display_name"]
        if display_name is not None:
            normalized_name = str(display_name).strip()
            if not normalized_name:
                raise ValueError("Display name cannot be empty.")
        connection.execute("""
            UPDATE administrators SET display_name = ?, role = ?, status = ?
            WHERE admin_id = ?
        """, (normalized_name, resulting_role, resulting_status, admin_id))
        if resulting_status == "DISABLED":
            connection.execute(
                "UPDATE administrator_sessions SET revoked_at = ? WHERE admin_id = ? AND revoked_at IS NULL",
                (utc_now(), admin_id),
            )
    return get_administrator(admin_id)


def reset_administrator_password(admin_id: str, new_password: str) -> dict:
    if len(str(new_password)) < 12:
        raise ValueError("Administrator password must contain at least 12 characters.")
    salt = secrets.token_bytes(16)
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute("""
            UPDATE administrators SET password_salt = ?, password_hash = ? WHERE admin_id = ?
        """, (salt.hex(), _password_digest(str(new_password), salt), admin_id))
        if cursor.rowcount == 0:
            raise KeyError("Administrator not found.")
        connection.execute(
            "UPDATE administrator_sessions SET revoked_at = ? WHERE admin_id = ? AND revoked_at IS NULL",
            (utc_now(), admin_id),
        )
    return get_administrator(admin_id)


def revoke_administrator_sessions(admin_id: str) -> int:
    get_administrator(admin_id)
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            "UPDATE administrator_sessions SET revoked_at = ? WHERE admin_id = ? AND revoked_at IS NULL",
            (utc_now(), admin_id),
        )
    return cursor.rowcount
