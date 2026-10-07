"""GreyGuard administrator identities, sessions, and role permissions."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from . import db_compat as sqlite3
import base64
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .database import database_path as greyguard_database_path


database_path = greyguard_database_path
SESSION_MINUTES = 15
REFRESH_DAYS = 7
PASSWORD_DAYS = 90
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
        admin_columns = {row[1] for row in connection.execute("PRAGMA table_info(administrators)")}
        for name, definition in {
            "mfa_secret": "TEXT", "mfa_enabled": "INTEGER NOT NULL DEFAULT 0",
            "password_expires_at": "TEXT", "break_glass": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if name not in admin_columns:
                connection.execute(f"ALTER TABLE administrators ADD COLUMN {name} {definition}")
        session_columns = {row[1] for row in connection.execute("PRAGMA table_info(administrator_sessions)")}
        for name, definition in {
            "device_name": "TEXT", "ip_address": "TEXT", "last_seen_at": "TEXT",
            "elevated_until": "TEXT",
        }.items():
            if name not in session_columns:
                connection.execute(f"ALTER TABLE administrator_sessions ADD COLUMN {name} {definition}")
        admin_columns = {row[1] for row in connection.execute("PRAGMA table_info(administrators)")}
        if "sso_provider_id" not in admin_columns:
            connection.execute("ALTER TABLE administrators ADD COLUMN sso_provider_id TEXT")
        connection.execute("""CREATE TABLE IF NOT EXISTS administrator_refresh_tokens (
            refresh_id TEXT PRIMARY KEY, family_id TEXT NOT NULL, session_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            used_at TEXT, revoked_at TEXT, replaced_by TEXT,
            FOREIGN KEY(session_id) REFERENCES administrator_sessions(session_id))""")
        connection.execute("""CREATE TABLE IF NOT EXISTS administrator_security_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id TEXT NOT NULL,
            timestamp TEXT NOT NULL, event_type TEXT NOT NULL, detail TEXT NOT NULL)""")

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
        "mfa_enabled": bool(row["mfa_enabled"]) if "mfa_enabled" in row.keys() else False,
        "password_expires_at": row["password_expires_at"] if "password_expires_at" in row.keys() else None,
        "break_glass": bool(row["break_glass"]) if "break_glass" in row.keys() else False,
        "sso_provider_id": row["sso_provider_id"] if "sso_provider_id" in row.keys() else None,
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
                    admin_id,email,display_name,role,password_salt,password_hash,status,created_at,
                    password_expires_at
                ) VALUES (?,?,?,?,?,?, 'ACTIVE', ?,?)
            """, (
                admin_id, normalized_email, normalized_name, normalized_role,
                salt.hex(), _password_digest(str(password), salt), timestamp,
                (datetime.now(timezone.utc) + timedelta(days=PASSWORD_DAYS)).isoformat(),
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


def _totp(secret, at=None):
    counter = int((at or datetime.now(timezone.utc)).timestamp()) // 30
    key = base64.b32decode(secret)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return str((struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff) % 1_000_000).zfill(6)


def _valid_totp(secret, code):
    now = datetime.now(timezone.utc)
    return bool(code) and any(hmac.compare_digest(_totp(secret, now + timedelta(seconds=offset)), str(code)) for offset in (-30, 0, 30))


def _issue_session(connection, row, device_name, ip_address) -> dict:
    """Create a session + refresh token for an already-authenticated administrator row.

    Shared by password login and SSO login: by the time either caller reaches this, the person
    has already proven their identity by one accepted method, so issuance itself is identical.
    """
    token = "gga_" + secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session_id = "ses_" + secrets.token_hex(12)
    created = datetime.now(timezone.utc)
    expires = created + timedelta(minutes=SESSION_MINUTES)
    connection.execute(
        """INSERT INTO administrator_sessions
        (session_id,admin_id,token_hash,created_at,expires_at,revoked_at,device_name,ip_address,last_seen_at)
        VALUES (?,?,?,?,?,NULL,?,?,?)""",
        (session_id, row["admin_id"], token_hash, created.isoformat(), expires.isoformat(),
         str(device_name)[:100], str(ip_address)[:64], created.isoformat()),
    )
    refresh = "ggr_" + secrets.token_urlsafe(40)
    refresh_id = "ref_" + secrets.token_hex(12)
    family_id = "fam_" + secrets.token_hex(12)
    connection.execute("INSERT INTO administrator_refresh_tokens VALUES(?,?,?,?,?,?,NULL,NULL,NULL)", (
        refresh_id, family_id, session_id, hashlib.sha256(refresh.encode()).hexdigest(),
        created.isoformat(), (created + timedelta(days=REFRESH_DAYS)).isoformat(),
    ))
    connection.execute(
        "UPDATE administrators SET last_login_at = ? WHERE admin_id = ?",
        (created.isoformat(), row["admin_id"]),
    )
    user = _public_admin(row)
    user["last_login_at"] = created.isoformat()
    return {"access_token": token, "refresh_token": refresh, "token_type": "session",
            "expires_at": expires.isoformat(), "administrator": user}


def authenticate(email: str, password: str, mfa_code=None, device_name="Unknown device", ip_address="") -> dict:
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
        if row["password_expires_at"] and row["password_expires_at"] <= utc_now():
            raise ValueError("Administrator password has expired.")
        if row["mfa_enabled"] and not _valid_totp(row["mfa_secret"], mfa_code):
            raise PermissionError("MFA_REQUIRED" if not mfa_code else "Invalid MFA code.")
        return _issue_session(connection, row, device_name, ip_address)


def provision_sso_administrator(email: str, display_name: str, role: str, provider_id: str) -> dict:
    """Create-or-update the local administrator record behind a successful SSO sign-in.

    Called only after the ID token has been fully verified and the caller has already resolved
    `role` from the provider's configured role mapping. An existing non-ACTIVE account is never
    reactivated here - suspension always wins, whether the account was created locally or by SSO.
    """
    normalized_email = str(email).strip().lower()
    normalized_role = str(role).strip().upper()
    if normalized_role not in ROLES:
        raise ValueError("Unknown administrator role.")
    initialize_admin_auth()
    now = utc_now()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM administrators WHERE email = ? COLLATE NOCASE", (normalized_email,)).fetchone()
        if row:
            if row["status"] != "ACTIVE":
                raise ValueError("Administrator authentication failed.")
            connection.execute(
                "UPDATE administrators SET role=?,display_name=?,sso_provider_id=? WHERE admin_id=?",
                (normalized_role, str(display_name).strip() or row["display_name"], provider_id, row["admin_id"]),
            )
            admin_id = row["admin_id"]
        else:
            admin_id = "adm_" + secrets.token_hex(12)
            # No local password is possible for an SSO-provisioned account; store an unguessable,
            # unusable placeholder rather than widen the NOT NULL password columns.
            salt = secrets.token_bytes(16)
            placeholder_password_hash = secrets.token_hex(32)
            connection.execute(
                """INSERT INTO administrators
                (admin_id,email,display_name,role,password_salt,password_hash,status,created_at,
                 password_expires_at,sso_provider_id)
                VALUES (?,?,?,?,?,?,'ACTIVE',?,NULL,?)""",
                (admin_id, normalized_email, str(display_name).strip() or normalized_email, normalized_role,
                 salt.hex(), placeholder_password_hash, now, provider_id),
            )
        row = connection.execute("SELECT * FROM administrators WHERE admin_id=?", (admin_id,)).fetchone()
    return _public_admin(row)


def issue_sso_session(email: str, device_name="Unknown device", ip_address="") -> dict:
    """Issue a session for an administrator who has already been SSO-provisioned/validated."""
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM administrators WHERE email = ? COLLATE NOCASE", (email.strip(),)).fetchone()
        if not row or row["status"] != "ACTIVE":
            raise ValueError("Administrator authentication failed.")
        return _issue_session(connection, row, device_name, ip_address)


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
    if path.startswith("/auth/"):
        return "read"
    if path.startswith("/compliance-reports"):
        return "read"
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
            UPDATE administrators SET password_salt = ?, password_hash = ?, password_expires_at=?
            WHERE admin_id = ?
        """, (salt.hex(), _password_digest(str(new_password), salt),
               (datetime.now(timezone.utc)+timedelta(days=PASSWORD_DAYS)).isoformat(), admin_id))
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


def refresh_access_token(refresh_token, device_name="Unknown device", ip_address=""):
    if not refresh_token or not refresh_token.startswith("ggr_"):
        raise ValueError("Refresh token is invalid.")
    digest = hashlib.sha256(refresh_token.encode()).hexdigest()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("""SELECT r.*,s.admin_id FROM administrator_refresh_tokens r
            JOIN administrator_sessions s ON s.session_id=r.session_id WHERE r.token_hash=?""", (digest,)).fetchone()
        if not row:
            raise ValueError("Refresh token is invalid.")
        if row["used_at"] or row["revoked_at"]:
            timestamp = utc_now()
            connection.execute("UPDATE administrator_refresh_tokens SET revoked_at=COALESCE(revoked_at,?) WHERE family_id=?", (timestamp,row["family_id"]))
            connection.execute("UPDATE administrator_sessions SET revoked_at=COALESCE(revoked_at,?) WHERE admin_id=?", (timestamp,row["admin_id"]))
            connection.execute("INSERT INTO administrator_security_events(admin_id,timestamp,event_type,detail) VALUES(?,?,?,?)", (row["admin_id"],timestamp,"REFRESH_TOKEN_REUSE","Token family and sessions revoked."))
            connection.commit()
            raise ValueError("Refresh token reuse detected; all sessions were revoked.")
        if row["expires_at"] <= utc_now():
            raise ValueError("Refresh token has expired.")
        now = datetime.now(timezone.utc)
        access = "gga_" + secrets.token_urlsafe(32)
        new_refresh = "ggr_" + secrets.token_urlsafe(40)
        new_refresh_id = "ref_" + secrets.token_hex(12)
        connection.execute("""UPDATE administrator_sessions SET token_hash=?,created_at=?,expires_at=?,
            device_name=?,ip_address=?,last_seen_at=?,revoked_at=NULL WHERE session_id=?""", (
            hashlib.sha256(access.encode()).hexdigest(), now.isoformat(),
            (now + timedelta(minutes=SESSION_MINUTES)).isoformat(), str(device_name)[:100],
            str(ip_address)[:64], now.isoformat(), row["session_id"],
        ))
        connection.execute("UPDATE administrator_refresh_tokens SET used_at=?,replaced_by=? WHERE refresh_id=?", (now.isoformat(),new_refresh_id,row["refresh_id"]))
        connection.execute("INSERT INTO administrator_refresh_tokens VALUES(?,?,?,?,?,?,NULL,NULL,NULL)", (
            new_refresh_id,row["family_id"],row["session_id"],hashlib.sha256(new_refresh.encode()).hexdigest(),
            now.isoformat(),(now+timedelta(days=REFRESH_DAYS)).isoformat(),
        ))
        admin = connection.execute("SELECT * FROM administrators WHERE admin_id=?", (row["admin_id"],)).fetchone()
        public = _public_admin(admin)
    return {"access_token":access,"refresh_token":new_refresh,"token_type":"session",
            "expires_at":(now+timedelta(minutes=SESSION_MINUTES)).isoformat(),"administrator":public}


def begin_mfa_enrollment(admin_id):
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE administrators SET mfa_secret=?,mfa_enabled=0 WHERE admin_id=?", (secret,admin_id))
    return {"secret": secret, "otpauth_uri": f"otpauth://totp/GreyGuard:{admin_id}?secret={secret}&issuer=GreyGuard"}


def confirm_mfa(admin_id, code):
    with sqlite3.connect(database_path) as connection:
        connection.row_factory=sqlite3.Row
        row=connection.execute("SELECT mfa_secret FROM administrators WHERE admin_id=?",(admin_id,)).fetchone()
        if not row or not row["mfa_secret"] or not _valid_totp(row["mfa_secret"],code):
            raise ValueError("MFA confirmation code is invalid.")
        connection.execute("UPDATE administrators SET mfa_enabled=1 WHERE admin_id=?",(admin_id,))
    return get_administrator(admin_id)


def list_sessions(admin_id):
    with sqlite3.connect(database_path) as connection:
        connection.row_factory=sqlite3.Row
        rows=connection.execute("""SELECT session_id,created_at,expires_at,revoked_at,
            device_name,ip_address,last_seen_at,elevated_until FROM administrator_sessions
            WHERE admin_id=? ORDER BY created_at DESC""",(admin_id,)).fetchall()
    return [dict(row) for row in rows]


def revoke_session_by_id(admin_id, session_id):
    with sqlite3.connect(database_path) as connection:
        cursor=connection.execute("UPDATE administrator_sessions SET revoked_at=COALESCE(revoked_at,?) WHERE admin_id=? AND session_id=?",(utc_now(),admin_id,session_id))
    if not cursor.rowcount: raise KeyError("Session not found.")
    return True
