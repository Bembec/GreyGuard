"""Customer-hosted gateway nodes: enrollment, signed policy distribution and bounded offline use (P3).

In the hybrid deployment model a customer runs an enforcement gateway next to its agents and the
hosted control plane distributes policy to it. This module is the control-plane side:

- Enrollment. An org administrator registers a node and receives a one-time enrollment token
  (24 hours). The node exchanges it, once, for its own node credential. Only a hash of either is
  stored. Nodes belong to one org and only ever receive that org's policy.
- Distribution. A node fetches a policy bundle: the org's published policy, its emergency
  controls and the agents whose credentials are revoked, signed with Ed25519. A gateway holds
  only the public key, so it can verify bundles but never forge one - unlike the install's HMAC
  policy-bundle export, whose verifier must hold the signing secret.
- Bounded offline use. Every bundle carries valid_until (issued_at + the node's offline
  allowance, 5 minutes to 7 days). A gateway that cannot refresh before then must fail closed
  and deny. That allowance is also the worst-case staleness of a revocation or an emergency stop
  at that node - the revocation-freshness bound.
- Revocation. Revoking a node kills its credential at once; its last bundle still expires on
  schedule, which is why the offline allowance should be short.
- Fleet view. Heartbeats record which bundle each node applied, so administrators see nodes that
  are out of date or have gone quiet past their offline allowance.

Gateways are an Enterprise capability (entitlement feature gateway_nodes).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import db_compat as sqlite3
from .database import database_path

BUNDLE_SCHEMA = "greyguard.gateway.bundle.v1"
ENROLLMENT_HOURS = 24
MIN_OFFLINE_SECONDS, MAX_OFFLINE_SECONDS = 300, 7 * 24 * 3600
DEFAULT_OFFLINE_SECONDS = 3600


class GatewayError(ValueError):
    """A gateway request that cannot be carried out."""


class GatewayAuthError(PermissionError):
    """A node credential or enrollment token that is missing, wrong, used or revoked."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _signing_key() -> Ed25519PrivateKey:
    value = os.getenv("GREYGUARD_DISTRIBUTION_SIGNING_KEY", "").strip()
    if not value:
        raise RuntimeError("GREYGUARD_DISTRIBUTION_SIGNING_KEY is not configured.")
    try:
        return Ed25519PrivateKey.from_private_bytes(_unb64(value))
    except ValueError as error:
        raise RuntimeError("GREYGUARD_DISTRIBUTION_SIGNING_KEY is not a valid Ed25519 private key.") from error


def public_key() -> dict[str, str]:
    """The key gateways verify bundles with. Safe to publish."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    raw = _signing_key().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {"algorithm": "Ed25519", "public_key": _b64(raw), "key_id": hashlib.sha256(raw).hexdigest()[:16]}


def initialize_gateways() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS gateway_nodes (
            node_id TEXT PRIMARY KEY, org_id TEXT NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL,
            enrollment_token_hash TEXT UNIQUE, enrollment_expires_at TEXT, credential_hash TEXT UNIQUE,
            max_offline_seconds INTEGER NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
            enrolled_at TEXT, last_seen_at TEXT, applied_digest TEXT, node_version TEXT,
            revoked_at TEXT, revoked_by TEXT, revoke_reason TEXT, UNIQUE (org_id, name))""")
        connection.execute("""CREATE TABLE IF NOT EXISTS gateway_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, org_id TEXT NOT NULL, node_id TEXT NOT NULL,
            timestamp TEXT NOT NULL, actor TEXT NOT NULL, event_type TEXT NOT NULL, detail_json TEXT NOT NULL)""")


def _event(connection, org_id, node_id, actor, event_type, detail=None):
    connection.execute(
        "INSERT INTO gateway_events (org_id, node_id, timestamp, actor, event_type, detail_json) VALUES (?, ?, ?, ?, ?, ?)",
        (org_id, node_id, utc_now().isoformat(), actor, event_type, json.dumps(detail or {}, sort_keys=True)))


def _public(row, current_digest: str | None = None) -> dict[str, Any]:
    node = {k: row[k] for k in ("node_id", "name", "status", "max_offline_seconds", "created_by", "created_at",
                                "enrolled_at", "last_seen_at", "applied_digest", "node_version", "revoked_at",
                                "revoke_reason", "enrollment_expires_at")}
    if node["status"] == "ACTIVE":
        seen = node["last_seen_at"]
        quiet = seen is None or datetime.fromisoformat(seen) < utc_now() - timedelta(seconds=node["max_offline_seconds"])
        node["health"] = "SILENT" if quiet else ("IN_SYNC" if current_digest and node["applied_digest"] == current_digest else "OUT_OF_DATE")
    else:
        node["health"] = node["status"]
    return node


def create_node(org_id: str, name: str, actor: str, max_offline_seconds: int = DEFAULT_OFFLINE_SECONDS) -> dict[str, Any]:
    name = str(name).strip()
    if not 3 <= len(name) <= 100:
        raise GatewayError("A gateway name is 3 to 100 characters.")
    if not MIN_OFFLINE_SECONDS <= int(max_offline_seconds) <= MAX_OFFLINE_SECONDS:
        raise GatewayError(f"The offline allowance is {MIN_OFFLINE_SECONDS} seconds to {MAX_OFFLINE_SECONDS // 86400} days.")
    initialize_gateways()
    token = "ggenr_" + secrets.token_urlsafe(32)
    node_id = "gw_" + uuid.uuid4().hex
    now = utc_now()
    expires = (now + timedelta(hours=ENROLLMENT_HOURS)).isoformat()
    with sqlite3.connect(database_path) as connection:
        try:
            connection.execute(
                """INSERT INTO gateway_nodes (node_id, org_id, name, status, enrollment_token_hash, enrollment_expires_at,
                max_offline_seconds, created_by, created_at) VALUES (?, ?, ?, 'PENDING', ?, ?, ?, ?, ?)""",
                (node_id, org_id, name, _hash(token), expires, int(max_offline_seconds), actor, now.isoformat()))
        except sqlite3.IntegrityError as error:
            raise GatewayError("A gateway with this name already exists.") from error
        _event(connection, org_id, node_id, actor, "NODE_CREATED", {"name": name, "max_offline_seconds": int(max_offline_seconds)})
    return {"node_id": node_id, "name": name, "enrollment_token": token, "enrollment_expires_at": expires,
            "notice": "Give this enrollment token to the gateway now; it works once and is not shown again."}


def enroll(token: str, node_version: str | None = None) -> dict[str, Any]:
    """The node's side: exchange a one-time enrollment token for a node credential."""
    initialize_gateways()
    credential = "ggnode_" + secrets.token_urlsafe(32)
    now = utc_now().isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        # Identify first, scope second: the token hash is globally unique.
        row = connection.execute(
            "SELECT node_id, org_id, enrollment_expires_at FROM gateway_nodes WHERE enrollment_token_hash = ? AND status = 'PENDING'",
            (_hash(str(token)),)).fetchone()
        if row is None or row["enrollment_expires_at"] <= now:
            raise GatewayAuthError("Enrollment token is invalid, used or expired.")
        # Single use: the token hash is cleared in the same statement that activates the node.
        updated = connection.execute(
            """UPDATE gateway_nodes SET status = 'ACTIVE', enrollment_token_hash = NULL, credential_hash = ?,
            enrolled_at = ?, node_version = ? WHERE node_id = ? AND org_id = ? AND status = 'PENDING'""",
            (_hash(credential), now, (node_version or "")[:100] or None, row["node_id"], row["org_id"])).rowcount
        if not updated:
            raise GatewayAuthError("Enrollment token is invalid, used or expired.")
        _event(connection, row["org_id"], row["node_id"], "gateway", "NODE_ENROLLED", {"node_version": node_version})
    return {"node_id": row["node_id"], "node_credential": credential, "verification_key": public_key(),
            "notice": "Store the node credential in the gateway's secret store; it is not shown again."}


def authenticate(node_id: str | None, credential: str | None) -> dict[str, Any]:
    if not node_id or not credential:
        raise GatewayAuthError("Gateway node credentials are required.")
    initialize_gateways()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT node_id, org_id, status, credential_hash, max_offline_seconds FROM gateway_nodes WHERE node_id = ?",
            (node_id,)).fetchone()
    if row is None or row["status"] != "ACTIVE" or not row["credential_hash"] \
            or not hmac.compare_digest(row["credential_hash"], _hash(credential)):
        raise GatewayAuthError("Gateway node authentication failed.")
    return dict(row)


def _bundle_body(org_id: str) -> dict[str, Any]:
    from . import policy_control
    policy = policy_control.get_published_policy(org_id=org_id)
    emergency = policy_control.get_emergency_controls(org_id=org_id)
    with sqlite3.connect(database_path) as connection:
        revoked = sorted(row[0] for row in connection.execute(
            "SELECT agent_name FROM agent_identities WHERE org_id = ? AND credential_status = 'REVOKED'", (org_id,)).fetchall())
    return {
        "policy": {key: policy[key] for key in ("policy_id", "version_number", "permissions", "risk_weights",
                                                "max_blocked_attempts", "max_risk_score")},
        "emergency": {key: emergency[key] for key in ("global_deny", "disabled_agents", "disabled_tools", "disabled_integrations")},
        "revoked_agents": revoked,
    }


def content_digest(org_id: str) -> str:
    return hashlib.sha256(json.dumps(_bundle_body(org_id), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def issue_bundle(node: dict[str, Any]) -> dict[str, Any]:
    """A signed bundle for an authenticated node, valid for its offline allowance."""
    body = _bundle_body(node["org_id"])
    now = utc_now()
    document = {
        "schema": BUNDLE_SCHEMA, "org_id": node["org_id"], "node_id": node["node_id"],
        "issued_at": now.isoformat(), "valid_until": (now + timedelta(seconds=node["max_offline_seconds"])).isoformat(),
        "content_digest": hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        **body,
    }
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    key = public_key()
    return {"document": document, "algorithm": "Ed25519", "key_id": key["key_id"],
            "signature": _b64(_signing_key().sign(canonical))}


def heartbeat(node: dict[str, Any], applied_digest: str | None, node_version: str | None) -> dict[str, Any]:
    current = content_digest(node["org_id"])
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE gateway_nodes SET last_seen_at = ?, applied_digest = ?, node_version = COALESCE(?, node_version) WHERE node_id = ? AND org_id = ?",
            (utc_now().isoformat(), (applied_digest or "")[:64] or None, (node_version or "")[:100] or None,
             node["node_id"], node["org_id"]))
    return {"current_digest": current, "refresh_required": applied_digest != current}


def list_nodes(org_id: str) -> dict[str, Any]:
    initialize_gateways()
    current = content_digest(org_id)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM gateway_nodes WHERE org_id = ? ORDER BY created_at", (org_id,)).fetchall()
    return {"current_digest": current, "nodes": [_public(row, current) for row in rows]}


def revoke_node(org_id: str, node_id: str, actor: str, reason: str) -> dict[str, Any]:
    if len(str(reason).strip()) < 5:
        raise GatewayError("Revoking a gateway needs a reason.")
    initialize_gateways()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        updated = connection.execute(
            """UPDATE gateway_nodes SET status = 'REVOKED', credential_hash = NULL, enrollment_token_hash = NULL,
            revoked_at = ?, revoked_by = ?, revoke_reason = ? WHERE node_id = ? AND org_id = ? AND status != 'REVOKED'""",
            (utc_now().isoformat(), actor, reason.strip(), node_id, org_id)).rowcount
        if not updated:
            raise KeyError("Gateway not found or already revoked.")
        _event(connection, org_id, node_id, actor, "NODE_REVOKED", {"reason": reason.strip()})
        row = connection.execute("SELECT * FROM gateway_nodes WHERE node_id = ? AND org_id = ?", (node_id, org_id)).fetchone()
    return _public(row)


def revoke_all(org_id: str, actor: str, reason: str) -> int:
    initialize_gateways()
    with sqlite3.connect(database_path) as connection:
        ids = [row[0] for row in connection.execute(
            "SELECT node_id FROM gateway_nodes WHERE org_id = ? AND status != 'REVOKED'", (org_id,)).fetchall()]
    for node_id in ids:
        revoke_node(org_id, node_id, actor, reason)
    return len(ids)
