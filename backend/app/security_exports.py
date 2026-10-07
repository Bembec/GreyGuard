"""Governed SIEM export queues with signing, minimization, and delivery evidence."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from . import db_compat as sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from .database import database_path
from .observability import redact
from .outbound_delivery import (
    PermanentDeliveryError, SSRFBlocked, backoff_seconds,
    new_claim_token, record_evidence, safe_error, send_json,
)


DESTINATION_TYPES = {"SIGNED_WEBHOOK", "SPLUNK", "MICROSOFT_SENTINEL", "ELASTIC", "GRAFANA_LOKI", "SYSLOG", "STIX_TAXII"}
MINIMIZATION_PROFILES = {"MINIMAL", "STANDARD", "FORENSIC"}
LEASE_SECONDS = 120


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def initialize_security_exports():
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS export_destinations (
            destination_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            destination_type TEXT NOT NULL, endpoint TEXT NOT NULL, enabled INTEGER NOT NULL,
            signing_key_reference TEXT, minimization_profile TEXT NOT NULL,
            rate_limit_per_minute INTEGER NOT NULL, max_attempts INTEGER NOT NULL,
            created_at TEXT NOT NULL, created_by TEXT NOT NULL, last_success_at TEXT,
            last_failure_at TEXT, last_error TEXT)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS export_queue (
            export_id TEXT PRIMARY KEY, destination_id TEXT NOT NULL, created_at TEXT NOT NULL,
            available_at TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL,
            event_type TEXT NOT NULL, payload_json TEXT NOT NULL, signature TEXT,
            delivered_at TEXT, last_error TEXT,
            FOREIGN KEY(destination_id) REFERENCES export_destinations(destination_id))""")
        queue_columns = {row[1] for row in connection.execute("PRAGMA table_info(export_queue)")}
        if "claim_token" not in queue_columns:
            connection.execute("ALTER TABLE export_queue ADD COLUMN claim_token TEXT")
        if "claimed_at" not in queue_columns:
            connection.execute("ALTER TABLE export_queue ADD COLUMN claimed_at TEXT")


def _destination(row):
    item = dict(row)
    item["enabled"] = bool(item["enabled"])
    item["credentials_stored"] = False
    return item


def list_destinations():
    initialize_security_exports()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [_destination(row) for row in connection.execute("SELECT * FROM export_destinations ORDER BY name")]


def save_destination(name, destination_type, endpoint, enabled, signing_key_reference,
                     minimization_profile, rate_limit_per_minute, max_attempts, actor):
    destination_type = destination_type.upper()
    minimization_profile = minimization_profile.upper()
    if destination_type not in DESTINATION_TYPES:
        raise ValueError("Unsupported export destination type.")
    if minimization_profile not in MINIMIZATION_PROFILES:
        raise ValueError("Unsupported data-minimization profile.")
    if not endpoint.startswith("https://") and destination_type != "SYSLOG":
        raise ValueError("Export endpoints must use HTTPS.")
    if destination_type == "SYSLOG" and not endpoint.startswith("tls://"):
        raise ValueError("Syslog destinations must use TLS.")
    if not 1 <= rate_limit_per_minute <= 10_000 or not 1 <= max_attempts <= 20:
        raise ValueError("Export limits are outside the supported range.")
    destination_id = "dst_" + uuid.uuid4().hex
    with sqlite3.connect(database_path) as connection:
        existing = connection.execute("SELECT destination_id FROM export_destinations WHERE name=?", (name.strip(),)).fetchone()
        if existing:
            destination_id = existing[0]
            connection.execute("""UPDATE export_destinations SET destination_type=?,endpoint=?,enabled=?,
                signing_key_reference=?,minimization_profile=?,rate_limit_per_minute=?,max_attempts=?
                WHERE destination_id=?""", (destination_type, endpoint, int(enabled), signing_key_reference,
                minimization_profile, rate_limit_per_minute, max_attempts, destination_id))
        else:
            connection.execute("""INSERT INTO export_destinations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (destination_id, name.strip(), destination_type, endpoint, int(enabled), signing_key_reference,
                 minimization_profile, rate_limit_per_minute, max_attempts, utc_now(), actor, None, None, None))
    return next(item for item in list_destinations() if item["destination_id"] == destination_id)


def _minimize(event, profile):
    safe = redact(event)
    common = {key: safe[key] for key in ("timestamp", "event_type", "severity", "outcome", "correlation_id") if key in safe}
    if profile == "MINIMAL":
        return common
    if profile == "STANDARD":
        allowed = common | {key: safe[key] for key in ("agent_name", "request_id", "action", "risk_score", "detail") if key in safe}
        return allowed
    return safe


def _adapter_payload(destination_type, event):
    if destination_type == "SPLUNK":
        return {"event": event, "sourcetype": "greyguard:security"}
    if destination_type == "MICROSOFT_SENTINEL":
        return {"records": [event], "Log-Type": "GreyGuardSecurity"}
    if destination_type == "ELASTIC":
        return {"@timestamp": event.get("timestamp", utc_now()), "event": event}
    if destination_type == "GRAFANA_LOKI":
        return {"streams": [{"stream": {"service": "greyguard"}, "values": [[str(int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)), json.dumps(event, separators=(",", ":"))]]}]}
    if destination_type == "SYSLOG":
        return {"facility": "authpriv", "severity": event.get("severity", "INFO"), "message": json.dumps(event, separators=(",", ":"))}
    if destination_type == "STIX_TAXII":
        return {"type": "bundle", "id": "bundle--" + str(uuid.uuid4()), "objects": [{"type": "observed-data", "spec_version": "2.1", "id": "observed-data--" + str(uuid.uuid4()), "created": utc_now(), "modified": utc_now(), "first_observed": event.get("timestamp", utc_now()), "last_observed": event.get("timestamp", utc_now()), "number_observed": 1, "object_refs": [], "x_greyguard_event": event}]}
    return event


def enqueue_export(destination_id, event, actor):
    initialize_security_exports()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        destination = connection.execute("SELECT * FROM export_destinations WHERE destination_id=?", (destination_id,)).fetchone()
        if not destination:
            raise KeyError("Export destination not found.")
        if not destination["enabled"]:
            raise PermissionError("Export destination is disabled.")
        minimized = _minimize({**event, "queued_by": actor}, destination["minimization_profile"])
        payload = _adapter_payload(destination["destination_type"], minimized)
        serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature = None
        if destination["signing_key_reference"]:
            key = os.getenv(destination["signing_key_reference"])
            if not key:
                raise ValueError("Signing-key environment reference is unavailable.")
            signature = "sha256=" + hmac.new(key.encode(), serialized.encode(), hashlib.sha256).hexdigest()
        export_id = "exp_" + uuid.uuid4().hex
        connection.execute("""INSERT INTO export_queue(export_id,destination_id,created_at,available_at,status,
            attempts,event_type,payload_json,signature,delivered_at,last_error) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (export_id, destination_id, utc_now(), utc_now(), "QUEUED", 0,
             str(event.get("event_type", "SECURITY_EVENT")), serialized, signature, None, None))
    record_evidence("SECURITY_EXPORT", export_id, "ENQUEUED", detail={"destination_id": destination_id})
    return get_export(export_id)


def get_export(export_id):
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM export_queue WHERE export_id=?", (export_id,)).fetchone()
    if not row:
        raise KeyError("Export record not found.")
    return dict(row)


def real_sender(endpoint, payload, signature, *, idempotency_key=None):
    """The production transport: POST the minimized, adapter-shaped payload, signed if configured."""
    if endpoint.startswith("tls://"):
        # Syslog-over-TLS needs a raw TLS socket transport, not an HTTPS POST. Not built in this
        # milestone; fail loud and dead-letter rather than silently drop or mis-send the event.
        raise PermanentDeliveryError("Syslog (tls://) delivery is not yet implemented; this export cannot be sent.")
    headers = {"X-GreyGuard-Signature": signature} if signature else None
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    send_json(endpoint, body, headers=headers, idempotency_key=idempotency_key)


def process_queue(sender, limit=100, worker_id=None):
    """Deliver due exports through an injected transport; safe for worker and test use."""
    initialize_security_exports()
    processed = 0
    now = utc_now()
    claim_token = new_claim_token()
    with sqlite3.connect(database_path) as connection:
        connection.execute("""UPDATE export_queue SET claim_token=?,claimed_at=? WHERE export_id IN (
            SELECT q.export_id FROM export_queue q JOIN export_destinations d USING(destination_id)
            WHERE (q.status='QUEUED' OR (q.status='SENDING' AND q.claimed_at<=?)) AND q.available_at<=? AND d.enabled=1
            ORDER BY q.created_at LIMIT ?)""",
            (claim_token, now, (datetime.now(timezone.utc) - timedelta(seconds=LEASE_SECONDS)).isoformat(), now, limit))
        connection.execute("UPDATE export_queue SET status='SENDING' WHERE claim_token=?", (claim_token,))
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""SELECT q.*,d.endpoint,d.destination_type,d.max_attempts,d.rate_limit_per_minute
            FROM export_queue q JOIN export_destinations d USING(destination_id) WHERE q.claim_token=?""", (claim_token,)).fetchall()
    per_destination = {}
    for row in rows:
        count = per_destination.get(row["destination_id"], 0)
        if count >= row["rate_limit_per_minute"]:
            # Rate-limited this tick, not failed: release the claim so the next tick can retry it.
            with sqlite3.connect(database_path) as connection:
                connection.execute("UPDATE export_queue SET status='QUEUED',claim_token=NULL,claimed_at=NULL WHERE export_id=?", (row["export_id"],))
            continue
        per_destination[row["destination_id"]] = count + 1
        attempts = row["attempts"] + 1
        record_evidence("SECURITY_EXPORT", row["export_id"], "ATTEMPT", attempt=attempts, worker_id=worker_id)
        try:
            sender(row["endpoint"], json.loads(row["payload_json"]), row["signature"], idempotency_key=row["export_id"])
            with sqlite3.connect(database_path) as connection:
                connection.execute("UPDATE export_queue SET status='DELIVERED',attempts=?,delivered_at=?,last_error=NULL,claim_token=NULL,claimed_at=NULL WHERE export_id=?", (attempts, utc_now(), row["export_id"]))
                connection.execute("UPDATE export_destinations SET last_success_at=?,last_error=NULL WHERE destination_id=?", (utc_now(), row["destination_id"]))
            record_evidence("SECURITY_EXPORT", row["export_id"], "SUCCESS", attempt=attempts, worker_id=worker_id)
        except SSRFBlocked as error:
            with sqlite3.connect(database_path) as connection:
                connection.execute("UPDATE export_queue SET status='BLOCKED',attempts=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE export_id=?", (attempts, safe_error(error), row["export_id"]))
            record_evidence("SECURITY_EXPORT", row["export_id"], "BLOCKED", attempt=attempts, detail={"error": str(error)}, worker_id=worker_id)
        except PermanentDeliveryError as error:
            with sqlite3.connect(database_path) as connection:
                connection.execute("UPDATE export_queue SET status='DEAD_LETTER',attempts=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE export_id=?", (attempts, safe_error(error), row["export_id"]))
                connection.execute("UPDATE export_destinations SET last_failure_at=?,last_error=? WHERE destination_id=?", (utc_now(), safe_error(error), row["destination_id"]))
            record_evidence("SECURITY_EXPORT", row["export_id"], "DEAD_LETTER", attempt=attempts, detail={"error": str(error)}, worker_id=worker_id)
        except Exception as error:
            terminal = attempts >= row["max_attempts"]
            available = (datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds(attempts))).isoformat()
            with sqlite3.connect(database_path) as connection:
                connection.execute("UPDATE export_queue SET status=?,attempts=?,available_at=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE export_id=?", ("DEAD_LETTER" if terminal else "QUEUED", attempts, available, safe_error(error), row["export_id"]))
                connection.execute("UPDATE export_destinations SET last_failure_at=?,last_error=? WHERE destination_id=?", (utc_now(), safe_error(error), row["destination_id"]))
            record_evidence("SECURITY_EXPORT", row["export_id"], "DEAD_LETTER" if terminal else "RETRY", attempt=attempts, detail={"error": safe_error(error)}, worker_id=worker_id)
        processed += 1
    return {"processed": processed}


def export_summary():
    initialize_security_exports()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        counts = {row["status"]: row["count"] for row in connection.execute("SELECT status,COUNT(*) count FROM export_queue GROUP BY status")}
        recent = [dict(row) for row in connection.execute("SELECT export_id,destination_id,created_at,status,attempts,event_type,delivered_at,last_error FROM export_queue ORDER BY created_at DESC LIMIT 100")]
    return {"counts": counts, "recent": recent, "raw_secrets_exposed": False}
