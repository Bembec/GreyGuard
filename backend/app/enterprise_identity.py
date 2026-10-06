"""Enterprise federation, workload identity, and privileged-access governance."""
from __future__ import annotations

import hashlib
import json
import secrets
from . import db_compat as sqlite3
from datetime import datetime, timedelta, timezone

from .database import database_path as greyguard_database_path

database_path = greyguard_database_path
ROLES = {"PLATFORM_ADMIN", "SECURITY_ANALYST", "AUDITOR"}


def _now():
    return datetime.now(timezone.utc)


def initialize_enterprise_identity():
    with sqlite3.connect(database_path) as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS identity_providers (
          provider_id TEXT PRIMARY KEY, name TEXT NOT NULL, issuer TEXT NOT NULL UNIQUE,
          client_id TEXT NOT NULL, discovery_url TEXT NOT NULL, enabled INTEGER NOT NULL,
          allowed_domains TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS identity_role_mappings (
          mapping_id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, claim_name TEXT NOT NULL,
          claim_value TEXT NOT NULL, greyguard_role TEXT NOT NULL, priority INTEGER NOT NULL,
          FOREIGN KEY(provider_id) REFERENCES identity_providers(provider_id));
        CREATE TABLE IF NOT EXISTS workload_identities (
          workload_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, subject TEXT NOT NULL UNIQUE,
          certificate_thumbprint TEXT NOT NULL UNIQUE, scopes TEXT NOT NULL, status TEXT NOT NULL,
          created_at TEXT NOT NULL, expires_at TEXT NOT NULL, last_authenticated_at TEXT);
        CREATE TABLE IF NOT EXISTS privilege_elevations (
          elevation_id TEXT PRIMARY KEY, admin_id TEXT NOT NULL, requested_role TEXT NOT NULL,
          reason TEXT NOT NULL, requested_at TEXT NOT NULL, expires_at TEXT NOT NULL,
          status TEXT NOT NULL, decided_by TEXT, decided_at TEXT);
        CREATE TABLE IF NOT EXISTS break_glass_activations (
          activation_id TEXT PRIMARY KEY, admin_id TEXT NOT NULL, reason TEXT NOT NULL,
          activated_at TEXT NOT NULL, expires_at TEXT NOT NULL, closed_at TEXT);
        CREATE TABLE IF NOT EXISTS enterprise_identity_events (
          event_id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
          actor_id TEXT NOT NULL, event_type TEXT NOT NULL, detail TEXT NOT NULL);
        """)


def _event(connection, actor, event_type, detail):
    connection.execute("INSERT INTO enterprise_identity_events(timestamp,actor_id,event_type,detail) VALUES(?,?,?,?)",
                       (_now().isoformat(), actor, event_type, detail))


def list_providers():
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM identity_providers ORDER BY name").fetchall()
    return [{**dict(row), "enabled": bool(row["enabled"]), "allowed_domains": json.loads(row["allowed_domains"])} for row in rows]


def save_provider(actor_id, name, issuer, client_id, allowed_domains=(), enabled=True):
    issuer = str(issuer).strip().rstrip("/")
    if not issuer.startswith("https://") or not name.strip() or not client_id.strip():
        raise ValueError("Provider name, HTTPS issuer, and client ID are required.")
    provider_id = "idp_" + secrets.token_hex(10)
    now = _now().isoformat()
    discovery = issuer + "/.well-known/openid-configuration"
    domains = sorted({str(item).strip().lower() for item in allowed_domains if str(item).strip()})
    with sqlite3.connect(database_path) as connection:
        existing = connection.execute("SELECT provider_id,created_at FROM identity_providers WHERE issuer=?", (issuer,)).fetchone()
        if existing:
            provider_id, created = existing
            connection.execute("UPDATE identity_providers SET name=?,client_id=?,discovery_url=?,enabled=?,allowed_domains=?,updated_at=? WHERE provider_id=?",
                               (name.strip(), client_id.strip(), discovery, int(enabled), json.dumps(domains), now, provider_id))
        else:
            created = now
            connection.execute("INSERT INTO identity_providers VALUES(?,?,?,?,?,?,?,?,?)",
                               (provider_id, name.strip(), issuer, client_id.strip(), discovery, int(enabled), json.dumps(domains), now, now))
        _event(connection, actor_id, "IDENTITY_PROVIDER_SAVED", f"Provider {provider_id} configuration changed; no client secret was stored.")
    return next(item for item in list_providers() if item["provider_id"] == provider_id)


def add_role_mapping(actor_id, provider_id, claim_name, claim_value, role, priority=100):
    role = str(role).upper()
    if role not in ROLES or not claim_name.strip() or not claim_value.strip():
        raise ValueError("A supported role and non-empty claim mapping are required.")
    mapping_id = "map_" + secrets.token_hex(10)
    with sqlite3.connect(database_path) as connection:
        if not connection.execute("SELECT 1 FROM identity_providers WHERE provider_id=?", (provider_id,)).fetchone():
            raise KeyError("Identity provider not found.")
        connection.execute("INSERT INTO identity_role_mappings VALUES(?,?,?,?,?,?)",
                           (mapping_id, provider_id, claim_name.strip(), claim_value.strip(), role, int(priority)))
        _event(connection, actor_id, "ROLE_MAPPING_CREATED", f"Mapping {mapping_id} assigns {role}.")
    return {"mapping_id": mapping_id, "provider_id": provider_id, "claim_name": claim_name.strip(),
            "claim_value": claim_value.strip(), "greyguard_role": role, "priority": int(priority)}


def list_role_mappings():
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM identity_role_mappings ORDER BY priority,mapping_id")]


def create_workload_identity(actor_id, name, subject, certificate_pem, scopes, days=90):
    if "BEGIN CERTIFICATE" not in certificate_pem or not name.strip() or not subject.strip():
        raise ValueError("Name, subject, and a PEM certificate are required.")
    thumbprint = hashlib.sha256(certificate_pem.strip().encode()).hexdigest()
    workload_id = "wli_" + secrets.token_hex(10)
    now = _now()
    normalized_scopes = sorted({str(scope).strip() for scope in scopes if str(scope).strip()})
    with sqlite3.connect(database_path) as connection:
        connection.execute("INSERT INTO workload_identities VALUES(?,?,?,?,?,'ACTIVE',?,?,NULL)",
                           (workload_id, name.strip(), subject.strip(), thumbprint, json.dumps(normalized_scopes), now.isoformat(), (now + timedelta(days=max(1, min(int(days), 365)))).isoformat()))
        _event(connection, actor_id, "WORKLOAD_IDENTITY_CREATED", f"Workload {workload_id} certificate registered.")
    return get_workload_identity(workload_id)


def get_workload_identity(workload_id):
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM workload_identities WHERE workload_id=?", (workload_id,)).fetchone()
    if not row:
        raise KeyError("Workload identity not found.")
    item = dict(row); item["scopes"] = json.loads(item["scopes"]); return item


def list_workload_identities():
    with sqlite3.connect(database_path) as connection:
        ids = [row[0] for row in connection.execute("SELECT workload_id FROM workload_identities ORDER BY created_at DESC")]
    return [get_workload_identity(item) for item in ids]


def request_elevation(admin_id, role, reason, minutes=30):
    role = str(role).upper()
    if role not in ROLES or len(reason.strip()) < 8:
        raise ValueError("A supported role and meaningful reason are required.")
    now = _now(); elevation_id = "elv_" + secrets.token_hex(10)
    expires = now + timedelta(minutes=max(5, min(int(minutes), 120)))
    with sqlite3.connect(database_path) as connection:
        connection.execute("INSERT INTO privilege_elevations VALUES(?,?,?,?,?,?,'PENDING',NULL,NULL)",
                           (elevation_id, admin_id, role, reason.strip(), now.isoformat(), expires.isoformat()))
        _event(connection, admin_id, "ELEVATION_REQUESTED", f"Elevation {elevation_id} requested for {role}.")
    return {"elevation_id": elevation_id, "status": "PENDING", "expires_at": expires.isoformat()}


def decide_elevation(actor_id, elevation_id, approved):
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM privilege_elevations WHERE elevation_id=?", (elevation_id,)).fetchone()
        if not row: raise KeyError("Elevation request not found.")
        if row["status"] != "PENDING": raise ValueError("Elevation request was already decided.")
        if row["admin_id"] == actor_id: raise ValueError("Elevation requests require a different administrator's approval.")
        status = "APPROVED" if approved and row["expires_at"] > _now().isoformat() else "REJECTED"
        connection.execute("UPDATE privilege_elevations SET status=?,decided_by=?,decided_at=? WHERE elevation_id=?",
                           (status, actor_id, _now().isoformat(), elevation_id))
        _event(connection, actor_id, "ELEVATION_DECIDED", f"Elevation {elevation_id} {status.lower()}.")
    return {"elevation_id": elevation_id, "status": status}


def list_elevations():
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM privilege_elevations ORDER BY requested_at DESC")]


def activate_break_glass(admin_id, reason, minutes=30):
    if len(reason.strip()) < 12: raise ValueError("A detailed emergency reason is required.")
    now = _now(); activation_id = "bga_" + secrets.token_hex(10)
    expires = now + timedelta(minutes=max(5, min(int(minutes), 60)))
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT break_glass,mfa_enabled,status FROM administrators WHERE admin_id=?", (admin_id,)).fetchone()
        if not row or not row[0] or not row[1] or row[2] != "ACTIVE":
            raise PermissionError("An active break-glass administrator with MFA is required.")
        connection.execute("INSERT INTO break_glass_activations VALUES(?,?,?,?,?,NULL)",
                           (activation_id, admin_id, reason.strip(), now.isoformat(), expires.isoformat()))
        _event(connection, admin_id, "BREAK_GLASS_ACTIVATED", f"Emergency activation {activation_id}; expires {expires.isoformat()}.")
    return {"activation_id": activation_id, "expires_at": expires.isoformat(), "status": "ACTIVE"}


def identity_summary():
    with sqlite3.connect(database_path) as connection:
        return {"providers": connection.execute("SELECT COUNT(*) FROM identity_providers WHERE enabled=1").fetchone()[0],
                "workload_identities": connection.execute("SELECT COUNT(*) FROM workload_identities WHERE status='ACTIVE'").fetchone()[0],
                "pending_elevations": connection.execute("SELECT COUNT(*) FROM privilege_elevations WHERE status='PENDING' AND expires_at> ?", (_now().isoformat(),)).fetchone()[0],
                "active_break_glass": connection.execute("SELECT COUNT(*) FROM break_glass_activations WHERE closed_at IS NULL AND expires_at> ?", (_now().isoformat(),)).fetchone()[0]}
