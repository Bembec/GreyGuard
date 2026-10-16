"""Exact policy-decision provenance for tool requests (P7.5 Control Graph, owner decision 2).

Every new tool request gets one decision record, written when the decision is made. It names the
policy version that was in force, a stable id for the rule that matched, the outcome, a snapshot of
that rule, and fingerprints that let anyone check the decision later without trusting a policy
record that could have changed since:

- `policy_fingerprint`: SHA-256 over the canonical content of the policy that decided (its id,
  version, permissions, risk weights and thresholds) as it was read at decision time.
- `record_fingerprint`: SHA-256 over every other stored field of the record, so a changed record no
  longer matches its own fingerprint.

The table is append-only: a database trigger refuses every UPDATE, on SQLite and PostgreSQL alike.
DELETE stays possible on purpose, so organization deletion and any future retention deletion keep
working exactly as before (the owner asked that retention controls not be weakened).

`audit_events` is deliberately not touched: adding a column there would change the hashed content
of rows the integrity chain already sealed.

Requests decided before this existed have no record; readers label their policy version
"inferred" from publication times (see `inferred_policy_version`), never as fact.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from . import db_compat as sqlite3
from .database import database_path

# Version 2 (owner decision, 2026-10-16) adds authentication_method: how the agent proved its
# identity for this request (AGENT_KEY or CLIENT_CERTIFICATE), or NOT_RECORDED when the decision
# was made outside an authenticated API call (the CLI, tests). Version-1 records keep verifying
# against version-1 fields: the fingerprint covers exactly the fields its version wrote.
# Version 3 adds audit_event_id: the audit event written for the same decision, so an incident
# derived from that event links to its request exactly (audit_events itself is never altered:
# a new column would change the content its integrity chain has already sealed).
SCHEMA_VERSION = 3
AUTHENTICATION_METHODS = ("AGENT_KEY", "CLIENT_CERTIFICATE", "NOT_RECORDED")

POLICY_SOURCES = ("PUBLISHED", "ROLLOUT", "BUILTIN", "NONE")
RULE_TYPES = ("PERMISSION", "DEFAULT_RULE", "EMERGENCY_CONTROL", "AGENT_STATE")

_FIELDS_V1 = (
    "request_id", "org_id", "agent_name", "action", "decided_at", "outcome", "policy_source",
    "policy_version_id", "policy_version_number", "matched_rule_id", "rule_type", "rule_name",
    "rule_snapshot_json", "policy_fingerprint", "schema_version",
)
_FIELDS_BY_VERSION = {
    1: _FIELDS_V1,
    2: (*_FIELDS_V1, "authentication_method"),
    3: (*_FIELDS_V1, "authentication_method", "audit_event_id"),
}
_FIELDS = _FIELDS_BY_VERSION[SCHEMA_VERSION]


def _fields_for(record: dict[str, Any]) -> tuple[str, ...]:
    return _FIELDS_BY_VERSION.get(int(record.get("schema_version") or 1), _FIELDS_V1)


def canonical(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def policy_fingerprint(policy: dict[str, Any]) -> str:
    """The decision-relevant content of a policy, as it was read when deciding."""
    return sha256(canonical({
        "policy_id": policy.get("policy_id"),
        "version_number": policy.get("version_number"),
        "permissions": policy.get("permissions", {}),
        "risk_weights": policy.get("risk_weights", {}),
        "max_blocked_attempts": policy.get("max_blocked_attempts"),
        "max_risk_score": policy.get("max_risk_score"),
    }))


def record_fingerprint(record: dict[str, Any]) -> str:
    return sha256(canonical({field: record.get(field) for field in _fields_for(record)}))


def initialize_decision_provenance() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS decision_records (
                request_id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                action TEXT NOT NULL,
                decided_at TEXT NOT NULL,
                outcome TEXT NOT NULL,
                policy_source TEXT NOT NULL,
                policy_version_id TEXT,
                policy_version_number INTEGER,
                matched_rule_id TEXT NOT NULL,
                rule_type TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                rule_snapshot_json TEXT NOT NULL,
                policy_fingerprint TEXT,
                record_fingerprint TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                authentication_method TEXT,
                audit_event_id INTEGER
            )
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(decision_records)")} \
            if sqlite3.backend_name() == "sqlite" else {"authentication_method", "audit_event_id"}
        # Later versions on a SQLite database created earlier (PostgreSQL: migrations 35 and 37).
        if "authentication_method" not in columns:
            connection.execute("ALTER TABLE decision_records ADD COLUMN authentication_method TEXT")
        if "audit_event_id" not in columns:
            connection.execute("ALTER TABLE decision_records ADD COLUMN audit_event_id INTEGER")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_decision_records_org_agent ON decision_records (org_id, agent_name, decided_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_decision_records_audit_event ON decision_records (org_id, audit_event_id)"
        )
        if sqlite3.backend_name() == "sqlite":
            # PostgreSQL gets the same guarantee from migration 20261016_34.
            connection.execute("""
                CREATE TRIGGER IF NOT EXISTS decision_records_append_only
                BEFORE UPDATE ON decision_records /* append-only for every org_id */
                BEGIN
                    SELECT RAISE(ABORT, 'decision records are append-only');
                END
            """)


def provenance(
    *,
    outcome: str,
    rule_type: str,
    matched_rule_id: str,
    rule_name: str,
    rule_snapshot: dict[str, Any],
    policy: dict[str, Any] | None = None,
    policy_source: str = "NONE",
) -> dict[str, Any]:
    """What decided: built by main.evaluate_action at the moment of decision."""
    return {
        "outcome": outcome,
        "rule_type": rule_type,
        "matched_rule_id": matched_rule_id,
        "rule_name": rule_name,
        "rule_snapshot": rule_snapshot,
        "policy_source": policy_source if policy is not None else "NONE",
        "policy_version_id": policy.get("policy_id") if policy else None,
        "policy_version_number": policy.get("version_number") if policy else None,
        "policy_fingerprint": policy_fingerprint(policy) if policy is not None else None,
    }


def record_decision(request_id: str, *, org_id: str, agent_name: str, action: str, decided_at: str,
                    decided: dict[str, Any], authentication_method: str | None = None) -> dict[str, Any]:
    """Append the decision record for one new tool request. Never updates an existing one."""
    method = authentication_method or "NOT_RECORDED"
    if method not in AUTHENTICATION_METHODS:
        raise ValueError("Unknown authentication method.")
    record = {
        "request_id": request_id,
        "org_id": org_id,
        "agent_name": agent_name,
        "action": action,
        "decided_at": decided_at,
        "outcome": decided["outcome"],
        "policy_source": decided["policy_source"],
        "policy_version_id": decided["policy_version_id"],
        "policy_version_number": decided["policy_version_number"],
        "matched_rule_id": decided["matched_rule_id"],
        "rule_type": decided["rule_type"],
        "rule_name": decided["rule_name"],
        "rule_snapshot_json": canonical(decided["rule_snapshot"]),
        "policy_fingerprint": decided["policy_fingerprint"],
        "schema_version": SCHEMA_VERSION,
        "authentication_method": method,
        "audit_event_id": decided.get("audit_event_id"),
    }
    record["record_fingerprint"] = record_fingerprint(record)
    columns = ", ".join(record)
    placeholders = ", ".join("?" for _ in record)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            f"INSERT INTO decision_records ({columns}) VALUES ({placeholders})",  # nosec B608  # column names are code constants; every value is a bound parameter (org_id included)
            tuple(record.values()),
        )
    return record


def _serialize(row) -> dict[str, Any]:
    record = {field: row[field] for field in (*_FIELDS, "record_fingerprint")}
    if int(record["schema_version"] or 1) < 2:
        record["authentication_method"] = None  # version 1 did not record it
    if int(record["schema_version"] or 1) < 3:
        record["audit_event_id"] = None  # versions 1 and 2 did not record it
    record["rule_snapshot"] = json.loads(record.pop("rule_snapshot_json"))
    return record


def get_decision_records(request_ids: list[str], *, org_id: str) -> dict[str, dict[str, Any]]:
    """The records for these requests in this org, keyed by request id. Others are never read."""
    if not request_ids:
        return {}
    found: dict[str, dict[str, Any]] = {}
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        for start in range(0, len(request_ids), 200):
            chunk = request_ids[start:start + 200]
            rows = connection.execute(
                f"SELECT * FROM decision_records WHERE org_id = ? AND request_id IN ({', '.join('?' for _ in chunk)})",  # nosec B608  # placeholders only; every value is a bound parameter
                (org_id, *chunk),
            ).fetchall()
            for row in rows:
                found[row["request_id"]] = _serialize(row)
    return found


def record_intact(record: dict[str, Any]) -> bool:
    """Whether a read record still matches the fingerprint taken when it was written."""
    stored = {field: record.get(field) for field in _fields_for(record) if field != "rule_snapshot_json"}
    stored["rule_snapshot_json"] = canonical(record["rule_snapshot"])
    return record_fingerprint(stored) == record.get("record_fingerprint")


def request_for_audit_event(audit_event_id: int, *, org_id: str) -> str | None:
    """The request whose decision wrote this audit event, in this org: an exact link, or None."""
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT request_id FROM decision_records WHERE org_id = ? AND audit_event_id = ?", (org_id, int(audit_event_id))
        ).fetchone()
    return row[0] if row else None


def verify_record(record: dict[str, Any], *, org_id: str) -> dict[str, Any]:
    """Check a record against its own fingerprint, and its policy against the stored version.

    `record_intact`: the record still matches the fingerprint taken when it was written.
    `policy_matches`: the stored policy version still has the content that decided (None when no
    stored version decided, e.g. an emergency control or the built-in fallback)."""
    intact = record_intact(record)
    policy_matches = None
    if record.get("policy_version_id"):
        from .policy_control import get_policy_version

        current = get_policy_version(record["policy_version_id"], org_id=org_id)
        policy_matches = current is not None and policy_fingerprint(current) == record.get("policy_fingerprint")
    return {"record_intact": intact, "policy_matches": policy_matches}


def inferred_policy_version(versions: list[dict[str, Any]], decided_at: str) -> dict[str, Any] | None:
    """For a request with no record: the version published most recently before it.

    Usually right, but wrong around a publication or under a staged rollout, which is why callers
    always label it "inferred" and never present it as the deciding version."""
    candidates = [v for v in versions if v.get("published_at") and v["published_at"] <= decided_at]
    return max(candidates, key=lambda v: (v["published_at"], v["version_number"]), default=None)
