"""Plans, entitlements, trials, usage meters and limits (P2.3).

Design rules, from the commercial roadmap addendum:

- Entitlements are enforced here, in the backend - never only in the UI.
- Plan limits must never remove a protection required for safe operation. MANDATORY_PROTECTIONS
  lists what no plan, status or override can gate; FEATURES may only contain capabilities outside
  it (a test asserts the two never overlap).
- On trial expiry or payment failure an org enters a restricted mode that blocks *new* growth
  (new agents, new gated configuration) but preserves export, evidence, security controls and
  safe offboarding. Existing agents keep being enforced exactly as before.
- Reviewers, auditors and other members are never metered, so oversight is never discouraged.
- Overrides are explicit, reasoned, optionally time-limited and audited.

Every org starts UNASSIGNED, which enforces nothing - exactly the behaviour before P2.3 - until an
install operator assigns a plan. The plan limits below are WORKING VALUES pending commercial
decisions; they live only in PLANS, so changing them is a data change, not a code change.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db_compat as sqlite3
from .database import database_path

# Capabilities every edition always includes, whatever its plan, status or overrides.
MANDATORY_PROTECTIONS = frozenset({
    "agent_identity", "authorization", "redaction", "evidence", "emergency_stop",
    "basic_recovery", "evidence_export", "offboarding",
})

# Capabilities a plan may or may not include.
FEATURES = frozenset({"siem_export", "incident_integrations", "scheduled_reports"})

# Metered units. Members are deliberately not metered (see module docstring).
METERS = {
    "agents": "Registered agent identities.",
    "controlled_requests_monthly": "Tool requests evaluated this calendar month (UTC).",
    "deliveries_monthly": "Successful outbound deliveries this calendar month (UTC).",
    "integrations": "Configured SIEM, incident-system and notification destinations.",
}

UNLIMITED = {"soft": None, "hard": None}

# WORKING VALUES - placeholders until pricing is decided. A None limit is unlimited. Controlled
# requests and deliveries carry no hard limit on any plan: refusing an agent's request because of
# a quota is a commercial decision that has not been made, so they are reported, not enforced.
PLANS: dict[str, dict[str, Any]] = {
    "UNASSIGNED": {
        "label": "Unassigned (no plan enforced)",
        "features": FEATURES,
        "limits": {meter: UNLIMITED for meter in METERS},
    },
    "FOUNDATION": {
        "label": "Foundation",
        "features": frozenset(),
        "limits": {
            "agents": {"soft": 20, "hard": 25},
            "controlled_requests_monthly": {"soft": 50_000, "hard": None},
            "deliveries_monthly": {"soft": 10_000, "hard": None},
            "integrations": {"soft": 3, "hard": 5},
        },
    },
    "ENTERPRISE": {
        "label": "Enterprise",
        "features": FEATURES,
        "limits": {
            "agents": {"soft": 200, "hard": 250},
            "controlled_requests_monthly": {"soft": 1_000_000, "hard": None},
            "deliveries_monthly": {"soft": 250_000, "hard": None},
            "integrations": {"soft": 50, "hard": 100},
        },
    },
    "DEDICATED": {
        "label": "Dedicated",
        "features": FEATURES,
        "limits": {meter: UNLIMITED for meter in METERS},
    },
}

STATUSES = {"ACTIVE", "TRIAL", "EXPIRED", "SUSPENDED"}
RESTRICTED_STATUSES = {"EXPIRED", "SUSPENDED"}
MAX_TRIAL_DAYS = 90


class EntitlementError(PermissionError):
    """An action the org's plan, limits or status does not allow."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def initialize_entitlements() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS org_entitlements (
            org_id TEXT PRIMARY KEY, plan TEXT NOT NULL, status TEXT NOT NULL,
            trial_ends_at TEXT, updated_by TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS entitlement_overrides (
            override_id TEXT PRIMARY KEY, org_id TEXT NOT NULL, override_key TEXT NOT NULL,
            value_json TEXT NOT NULL, reason TEXT NOT NULL, created_by TEXT NOT NULL,
            created_at TEXT NOT NULL, expires_at TEXT, revoked_at TEXT, revoked_by TEXT)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS entitlement_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, org_id TEXT NOT NULL, timestamp TEXT NOT NULL,
            actor TEXT NOT NULL, event_type TEXT NOT NULL, detail_json TEXT NOT NULL)""")


def _record(connection, org_id: str, actor: str, event_type: str, detail: dict) -> None:
    connection.execute(
        "INSERT INTO entitlement_events (org_id, timestamp, actor, event_type, detail_json) VALUES (?, ?, ?, ?, ?)",
        (org_id, utc_now().isoformat(), actor, event_type, json.dumps(detail, sort_keys=True)),
    )


def _assignment(org_id: str) -> dict[str, Any]:
    initialize_entitlements()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM org_entitlements WHERE org_id = ?", (org_id,)).fetchone()
    if row is None:
        return {"plan": "UNASSIGNED", "status": "ACTIVE", "trial_ends_at": None, "updated_by": None, "updated_at": None}
    assignment = dict(row)
    assignment.pop("org_id", None)
    # A lapsed trial is expired from the moment it ends; no background job has to notice.
    if assignment["status"] == "TRIAL" and assignment["trial_ends_at"] and assignment["trial_ends_at"] <= utc_now().isoformat():
        assignment["status"] = "EXPIRED"
    return assignment


def _active_overrides(org_id: str) -> list[dict[str, Any]]:
    now = utc_now().isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT override_id, override_key, value_json, reason, created_by, created_at, expires_at
            FROM entitlement_overrides WHERE org_id = ? AND revoked_at IS NULL
            AND (expires_at IS NULL OR expires_at > ?) ORDER BY created_at""",
            (org_id, now),
        ).fetchall()
    return [{**{k: row[k] for k in row.keys() if k != "value_json"}, "value": json.loads(row["value_json"])} for row in rows]


def _month_start() -> str:
    return utc_now().strftime("%Y-%m-01")


def usage(org_id: str, meters=None) -> dict[str, int]:
    """Current value of the requested meters (all of them by default) for one org. A limit check
    reads only its own meter, so checking one limit never depends on another module's tables."""
    month = _month_start()
    queries = {
        "agents": ("SELECT COUNT(*) FROM agent_identities WHERE org_id = ?", (org_id,)),
        # Timestamps carry their own offsets; comparing against the UTC month start is accurate to
        # within the offset at month boundaries, which is fine for a usage meter.
        "controlled_requests_monthly": (
            "SELECT COUNT(*) FROM tool_requests WHERE org_id = ? AND timestamp >= ?", (org_id, month)),
        "deliveries_monthly": (
            "SELECT COUNT(*) FROM outbound_delivery_evidence WHERE org_id = ? AND event = 'SUCCESS' AND occurred_at >= ?",
            (org_id, month)),
        "integrations": (
            "SELECT (SELECT COUNT(*) FROM export_destinations WHERE org_id = ?)"
            " + (SELECT COUNT(*) FROM incident_destinations WHERE org_id = ?)"
            " + (SELECT COUNT(*) FROM notification_destinations WHERE org_id = ?)", (org_id, org_id, org_id)),
    }
    # No fallback for a missing table: a meter that silently read 0 would under-count and let an
    # org past a hard limit. Every owning module creates its table at startup.
    with sqlite3.connect(database_path) as connection:
        return {
            meter: connection.execute(*queries[meter]).fetchone()[0] or 0
            for meter in (METERS if meters is None else meters)
        }


def get_entitlements(org_id: str, meters=None) -> dict[str, Any]:
    """The org's effective entitlements: plan, status, features, limits, usage and overrides.
    `meters` narrows which usage meters are computed (all by default)."""
    assignment = _assignment(org_id)
    plan = PLANS[assignment["plan"]]
    features = set(plan["features"])
    limits = {meter: dict(value) for meter, value in plan["limits"].items()}
    overrides = _active_overrides(org_id)
    for override in overrides:
        kind, _, name = override["override_key"].partition(":")
        if kind == "feature" and name in FEATURES:
            (features.add if override["value"] else features.discard)(name)
        elif kind == "limit":
            meter, _, level = name.partition(":")
            if meter in limits and level in ("soft", "hard"):
                limits[meter][level] = override["value"]
    current = usage(org_id, meters)
    return {
        "org_id": org_id,
        **assignment,
        "plan_label": plan["label"],
        "restricted": assignment["status"] in RESTRICTED_STATUSES,
        "features": sorted(features),
        "mandatory_protections": sorted(MANDATORY_PROTECTIONS),
        "limits": limits,
        "usage": current,
        "soft_limits_exceeded": sorted(
            meter for meter, limit in limits.items()
            if limit["soft"] is not None and meter in current and current[meter] >= limit["soft"]),
        "overrides": overrides,
    }


def require_feature(org_id: str, feature: str) -> None:
    """Refuse a gated capability the org's plan does not include. Mandatory protections can
    never be refused here."""
    if feature in MANDATORY_PROTECTIONS:
        return
    if feature not in FEATURES:
        raise ValueError(f"Unknown entitlement feature: {feature}")
    entitlements = get_entitlements(org_id, meters=())
    if entitlements["restricted"]:
        raise EntitlementError(
            f"This organization's plan is {entitlements['status'].lower()}: new {feature.replace('_', ' ')} "
            "configuration is paused. Evidence, export and security controls remain available.")
    if feature not in entitlements["features"]:
        raise EntitlementError(
            f"The {entitlements['plan_label']} plan does not include {feature.replace('_', ' ')}.")


def require_capacity(org_id: str, meter: str, increment: int = 1) -> dict[str, Any]:
    """Refuse growth past a hard limit, or any growth while restricted. Returns the meter's state;
    'soft_limit_reached' tells the caller to warn without refusing."""
    if meter not in METERS:
        raise ValueError(f"Unknown meter: {meter}")
    entitlements = get_entitlements(org_id, meters=(meter,))
    if entitlements["restricted"]:
        raise EntitlementError(
            f"This organization's plan is {entitlements['status'].lower()}: new {meter.replace('_', ' ')} "
            "cannot be added. Evidence, export and security controls remain available.")
    limit = entitlements["limits"][meter]
    current = entitlements["usage"][meter]
    if limit["hard"] is not None and current + increment > limit["hard"]:
        raise EntitlementError(
            f"The {entitlements['plan_label']} plan allows {limit['hard']} {meter.replace('_', ' ')}; "
            f"{current} are in use.")
    return {"meter": meter, "usage": current, "limit": limit,
            "soft_limit_reached": limit["soft"] is not None and current + increment > limit["soft"]}


def require_new_integration_capacity(org_id: str, table: str, name: str) -> None:
    """Integrations meter check for a destination save: saving an existing destination (an
    update, matched by name within the org) never counts as growth."""
    if table not in ("export_destinations", "incident_destinations", "notification_destinations"):
        raise ValueError("Unknown integration table.")
    initialize_entitlements()
    with sqlite3.connect(database_path) as connection:
        exists = connection.execute(
            f"SELECT 1 FROM {table} WHERE org_id = ? AND LOWER(name) = LOWER(?)", (org_id, str(name).strip())
        ).fetchone()
    if not exists:
        require_capacity(org_id, "integrations")


def assign_plan(org_id: str, plan: str, status: str, actor: str, trial_days: int | None = None) -> dict[str, Any]:
    """Install-operator action: set an org's plan and status, audited."""
    plan, status = str(plan).upper(), str(status).upper()
    if plan not in PLANS:
        raise ValueError("Unknown plan.")
    if status not in STATUSES:
        raise ValueError("Unknown entitlement status.")
    trial_ends_at = None
    if status == "TRIAL":
        if not trial_days or not 1 <= int(trial_days) <= MAX_TRIAL_DAYS:
            raise ValueError(f"A trial needs a length of 1 to {MAX_TRIAL_DAYS} days.")
        trial_ends_at = (utc_now() + timedelta(days=int(trial_days))).isoformat()
    initialize_entitlements()
    now = utc_now().isoformat()
    with sqlite3.connect(database_path) as connection:
        updated = connection.execute(
            "UPDATE org_entitlements SET plan = ?, status = ?, trial_ends_at = ?, updated_by = ?, updated_at = ? WHERE org_id = ?",
            (plan, status, trial_ends_at, actor, now, org_id)).rowcount
        if not updated:
            connection.execute(
                "INSERT INTO org_entitlements (org_id, plan, status, trial_ends_at, updated_by, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (org_id, plan, status, trial_ends_at, actor, now))
        _record(connection, org_id, actor, "PLAN_ASSIGNED", {"plan": plan, "status": status, "trial_ends_at": trial_ends_at})
    return get_entitlements(org_id)


def add_override(org_id: str, key: str, value: Any, reason: str, actor: str, expires_in_days: int | None = None) -> dict[str, Any]:
    """Install-operator action: an explicit, reasoned and audited exception to the plan."""
    kind, _, name = str(key).partition(":")
    if kind == "feature":
        if name not in FEATURES:
            raise ValueError("Overrides can only grant or withhold plan features, never mandatory protections.")
        if not isinstance(value, bool):
            raise ValueError("A feature override must be true or false.")
    elif kind == "limit":
        meter, _, level = name.partition(":")
        if meter not in METERS or level not in ("soft", "hard"):
            raise ValueError("A limit override key looks like limit:<meter>:soft or limit:<meter>:hard.")
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            raise ValueError("A limit override must be a non-negative integer, or null for unlimited.")
    else:
        raise ValueError("Override keys start with feature: or limit:.")
    if len(str(reason).strip()) < 10:
        raise ValueError("An override needs a reason of at least 10 characters.")
    if expires_in_days is not None and not 1 <= int(expires_in_days) <= 365:
        raise ValueError("An override can last 1 to 365 days, or indefinitely.")
    initialize_entitlements()
    override_id = "ovr_" + uuid.uuid4().hex
    now = utc_now()
    expires_at = (now + timedelta(days=int(expires_in_days))).isoformat() if expires_in_days else None
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """INSERT INTO entitlement_overrides (override_id, org_id, override_key, value_json, reason,
            created_by, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (override_id, org_id, key, json.dumps(value), reason.strip(), actor, now.isoformat(), expires_at))
        _record(connection, org_id, actor, "OVERRIDE_ADDED",
                {"override_id": override_id, "key": key, "value": value, "reason": reason.strip(), "expires_at": expires_at})
    return get_entitlements(org_id)


def revoke_override(org_id: str, override_id: str, actor: str) -> dict[str, Any]:
    initialize_entitlements()
    with sqlite3.connect(database_path) as connection:
        revoked = connection.execute(
            "UPDATE entitlement_overrides SET revoked_at = ?, revoked_by = ? WHERE override_id = ? AND org_id = ? AND revoked_at IS NULL",
            (utc_now().isoformat(), actor, override_id, org_id)).rowcount
        if not revoked:
            raise KeyError("Active override not found.")
        _record(connection, org_id, actor, "OVERRIDE_REVOKED", {"override_id": override_id})
    return get_entitlements(org_id)


def entitlement_history(org_id: str, limit: int = 50) -> list[dict[str, Any]]:
    initialize_entitlements()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT timestamp, actor, event_type, detail_json FROM entitlement_events WHERE org_id = ? ORDER BY event_id DESC LIMIT ?",
            (org_id, max(1, min(int(limit), 200)))).fetchall()
    return [{"timestamp": r["timestamp"], "actor": r["actor"], "event_type": r["event_type"],
             "detail": json.loads(r["detail_json"])} for r in rows]
