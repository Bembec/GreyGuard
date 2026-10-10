"""Controlled policy adapters, signed bundles and staged rollouts."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from . import db_compat as sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from .database import database_path
from .policy_control import get_policy_version


ADAPTER_TYPES = {"OPA", "CEDAR", "CERBOS"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_policy_integrations():
    """Create the org-scoped policy integration tables (P2.2 policy batch).

    policy_adapters holds one fixed row per adapter type, so - like adapter_configs in batch 2 -
    its key is reshaped to a composite (adapter_type, org_id); each org's rows are seeded on
    first use. policy_rollouts and policy_integration_events gain a plain org_id."""
    with connect() as connection:
        adapter_columns = [row[1] for row in connection.execute("PRAGMA table_info(policy_adapters)")]
        if adapter_columns and "org_id" not in adapter_columns:
            connection.execute("ALTER TABLE policy_adapters RENAME TO policy_adapters_pre_org")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS policy_adapters (
            adapter_type TEXT NOT NULL, enabled INTEGER NOT NULL, endpoint TEXT,
            owner TEXT NOT NULL, purpose TEXT NOT NULL, updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL, org_id TEXT NOT NULL DEFAULT 'org_default',
            PRIMARY KEY (adapter_type, org_id))"""
        )
        if adapter_columns and "org_id" not in adapter_columns:
            connection.execute(
                """INSERT INTO policy_adapters
                (adapter_type,enabled,endpoint,owner,purpose,updated_by,updated_at,org_id)
                SELECT adapter_type,enabled,endpoint,owner,purpose,updated_by,updated_at,'org_default'
                FROM policy_adapters_pre_org"""
            )
            connection.execute("DROP TABLE policy_adapters_pre_org")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS policy_rollouts (
            rollout_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL, percentage INTEGER NOT NULL,
            agent_allowlist_json TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            org_id TEXT NOT NULL DEFAULT 'org_default')"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS policy_integration_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
            actor TEXT NOT NULL, event_type TEXT NOT NULL, detail TEXT NOT NULL,
            org_id TEXT NOT NULL DEFAULT 'org_default')"""
        )
        for table in ("policy_rollouts", "policy_integration_events"):
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if "org_id" not in columns:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
    _seed_adapters("org_default")


def _seed_adapters(org_id):
    with connect() as connection:
        for adapter in sorted(ADAPTER_TYPES):
            connection.execute(
                """INSERT OR IGNORE INTO policy_adapters
                (adapter_type,enabled,endpoint,owner,purpose,updated_by,updated_at,org_id)
                VALUES(?,0,NULL,'','','SYSTEM',?,?)""", (adapter, utc_now(), org_id)
            )


def list_policy_adapters(*, org_id):
    _seed_adapters(org_id)
    with connect() as connection:
        rows = connection.execute("SELECT * FROM policy_adapters WHERE org_id=? ORDER BY adapter_type", (org_id,)).fetchall()
    return [{**dict(row), "enabled": bool(row["enabled"]), "credentials_stored": False} for row in rows]


def configure_policy_adapter(adapter_type, enabled, endpoint, owner, purpose, actor, *, org_id):
    adapter = adapter_type.upper()
    if adapter not in ADAPTER_TYPES:
        raise ValueError("Unsupported policy adapter.")
    if enabled and (not endpoint or not endpoint.startswith("https://")):
        raise ValueError("Enabled adapters require an HTTPS endpoint.")
    if enabled and (not owner.strip() or not purpose.strip()):
        raise ValueError("Enabled adapters require an owner and purpose.")
    _seed_adapters(org_id)
    with connect() as connection:
        connection.execute(
            """UPDATE policy_adapters SET enabled=?,endpoint=?,owner=?,purpose=?,updated_by=?,updated_at=?
            WHERE adapter_type=? AND org_id=?""",
            (int(enabled), endpoint or None, owner.strip(), purpose.strip(), actor, utc_now(), adapter, org_id),
        )
        connection.execute(
            "INSERT INTO policy_integration_events(timestamp,actor,event_type,detail,org_id) VALUES(?,?,?,?,?)",
            (utc_now(), actor, "POLICY_ADAPTER_UPDATED", f"{adapter} enabled={bool(enabled)}", org_id),
        )
    return next(item for item in list_policy_adapters(org_id=org_id) if item["adapter_type"] == adapter)


def _bundle_key():
    key = os.environ.get("GREYGUARD_POLICY_SIGNING_KEY", "")
    if len(key) < 32:
        raise RuntimeError("GREYGUARD_POLICY_SIGNING_KEY must contain at least 32 characters.")
    return key.encode()


def export_signed_policy_bundle(policy_id, *, org_id):
    policy = get_policy_version(policy_id, org_id=org_id)
    document = {
        "schema": "greyguard.policy.bundle.v1",
        "policy": policy,
        "issued_at": utc_now(),
    }
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(_bundle_key(), canonical, hashlib.sha256).hexdigest()
    return {"document": document, "algorithm": "HMAC-SHA256", "signature": signature}


def verify_signed_policy_bundle(bundle):
    document = bundle.get("document")
    signature = bundle.get("signature", "")
    if not isinstance(document, dict) or bundle.get("algorithm") != "HMAC-SHA256":
        return {"valid": False, "reason": "Unsupported or malformed policy bundle."}
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    expected = hmac.new(_bundle_key(), canonical, hashlib.sha256).hexdigest()
    valid = hmac.compare_digest(expected, signature)
    return {"valid": valid, "reason": "Signature verified." if valid else "Signature mismatch."}


def create_rollout(policy_id, percentage, agent_allowlist, actor, *, org_id):
    policy = get_policy_version(policy_id, org_id=org_id)
    if policy["status"] not in {"PENDING_APPROVAL", "PUBLISHED"}:
        raise ValueError("Only reviewed or published policies can be staged.")
    if percentage < 0 or percentage > 100:
        raise ValueError("Rollout percentage must be from 0 to 100.")
    rollout_id = str(uuid4())
    timestamp = utc_now()
    with connect() as connection:
        connection.execute("UPDATE policy_rollouts SET status='PAUSED',updated_at=? WHERE status='ACTIVE' AND org_id=?", (timestamp, org_id))
        connection.execute(
            """INSERT INTO policy_rollouts
            (rollout_id,policy_id,percentage,agent_allowlist_json,status,created_by,created_at,updated_at,org_id)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (rollout_id, policy_id, percentage, json.dumps(sorted(set(agent_allowlist))), "ACTIVE", actor, timestamp, timestamp, org_id),
        )
    return get_rollout(rollout_id, org_id=org_id)


def get_rollout(rollout_id, *, org_id):
    with connect() as connection:
        row = connection.execute("SELECT * FROM policy_rollouts WHERE rollout_id=? AND org_id=?", (rollout_id, org_id)).fetchone()
    if row is None:
        raise KeyError("Policy rollout not found.")
    result = dict(row)
    result["agent_allowlist"] = json.loads(result.pop("agent_allowlist_json"))
    return result


def list_rollouts(*, org_id):
    with connect() as connection:
        ids = [row[0] for row in connection.execute("SELECT rollout_id FROM policy_rollouts WHERE org_id=? ORDER BY created_at DESC", (org_id,)).fetchall()]
    return [get_rollout(item, org_id=org_id) for item in ids]


def update_rollout(rollout_id, status, percentage, actor, *, org_id):
    if status not in {"ACTIVE", "PAUSED", "COMPLETED", "CANCELLED"}:
        raise ValueError("Invalid rollout status.")
    if percentage < 0 or percentage > 100:
        raise ValueError("Rollout percentage must be from 0 to 100.")
    get_rollout(rollout_id, org_id=org_id)
    with connect() as connection:
        if status == "ACTIVE":
            connection.execute("UPDATE policy_rollouts SET status='PAUSED',updated_at=? WHERE status='ACTIVE' AND rollout_id<>? AND org_id=?", (utc_now(), rollout_id, org_id))
        connection.execute("UPDATE policy_rollouts SET status=?,percentage=?,updated_at=? WHERE rollout_id=? AND org_id=?", (status, percentage, utc_now(), rollout_id, org_id))
        connection.execute("INSERT INTO policy_integration_events(timestamp,actor,event_type,detail,org_id) VALUES(?,?,?,?,?)", (utc_now(), actor, "POLICY_ROLLOUT_UPDATED", f"{rollout_id} status={status} percentage={percentage}", org_id))
    return get_rollout(rollout_id, org_id=org_id)


def effective_rollout_policy(agent_name, *, org_id):
    """Return the staged policy selected deterministically for an agent, from its own org's
    active rollout only - one org's rollout can never change another org's enforcement."""
    with connect() as connection:
        row = connection.execute("SELECT * FROM policy_rollouts WHERE status='ACTIVE' AND org_id=? ORDER BY created_at DESC LIMIT 1", (org_id,)).fetchone()
    if row is None:
        return None
    allowlist = json.loads(row["agent_allowlist_json"])
    bucket = int(hashlib.sha256(agent_name.encode()).hexdigest()[:8], 16) % 100
    if agent_name not in allowlist and bucket >= row["percentage"]:
        return None
    return get_policy_version(row["policy_id"], org_id=org_id)

