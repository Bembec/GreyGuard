"""Plans, entitlements, trials, usage meters and limits (P2.3).

Design rules, from the commercial roadmap addendum:

- Entitlements are enforced here, in the backend - never only in the UI.
- Plan limits must never remove a protection required for safe operation. MANDATORY_PROTECTIONS
  lists what no plan, status or override can gate; FEATURES may only contain capabilities outside
  it (a test asserts the two never overlap).
- On trial expiry, suspension, an overdue payment past its grace period, a cancelled subscription
  or a lapsed self-hosted licence lease (RESTRICTION_REASONS) an org enters a restricted mode that blocks *new* growth
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

from . import billing, licensing, organizations
from . import db_compat as sqlite3
from .database import database_path

# Capabilities every edition always includes, whatever its plan, status or overrides.
MANDATORY_PROTECTIONS = frozenset({
    "agent_identity", "authorization", "redaction", "evidence", "emergency_stop",
    "basic_recovery", "evidence_export", "offboarding",
})

# Capabilities a plan may or may not include.
FEATURES = frozenset({"siem_export", "incident_integrations", "scheduled_reports", "gateway_nodes"})

# Metered units. Members are deliberately not metered (see module docstring).
METERS = {
    "agents": "Registered agent identities.",
    "controlled_requests_monthly": "Tool requests evaluated this calendar month (UTC).",
    "deliveries_monthly": "Successful outbound deliveries this calendar month (UTC).",
    "integrations": "Configured SIEM, incident-system and notification destinations.",
}

UNLIMITED = {"soft": None, "hard": None}

# Monitored only (P4 decision D6): these meters may carry a soft limit that is reported, but can
# never refuse anything - refusing an agent's controlled request or a security delivery over a
# volume quota would interrupt security operations. The engine will not enforce them, plans may
# not give them a hard limit, and overrides may not add one.
MONITORED_ONLY_METERS = frozenset({"controlled_requests_monthly", "deliveries_monthly"})

# PROVISIONAL VALUES (P4 decision D6, 2026-10-15): Foundation and Enterprise keep these limits
# while pilots provide evidence. A None limit is unlimited. Controlled requests and deliveries are
# monitored only (MONITORED_ONLY_METERS) and never refuse anything.
#
# UNASSIGNED grants no capacity and no gated features: a new org needs an explicit plan or a
# controlled trial before it can add agents or integrations. Existing enforcement, evidence and
# exports are unaffected either way.
#
# TRANSITIONAL exists only for orgs that already existed when D6 shipped (see
# _migrate_existing_orgs): it preserves their pre-D6 behaviour explicitly and audibly until an
# install operator assigns a real plan. It can never be assigned by hand.
#
# DEDICATED limits come from each org's contract (contract_limits, required when the plan is
# assigned), never from an implicit "unlimited".
NO_CAPACITY = {"soft": 0, "hard": 0}
PLANS: dict[str, dict[str, Any]] = {
    "UNASSIGNED": {
        "label": "No plan assigned",
        "features": frozenset(),
        "limits": {"agents": NO_CAPACITY, "integrations": NO_CAPACITY,
                   "controlled_requests_monthly": UNLIMITED, "deliveries_monthly": UNLIMITED},
    },
    "TRANSITIONAL": {
        "label": "Transitional (existing org before plans were required)",
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
        # Replaced per org by its contract_limits; this default only applies if a contract row is
        # somehow missing, and grants no capacity rather than unlimited.
        "limits": {"agents": NO_CAPACITY, "integrations": NO_CAPACITY,
                   "controlled_requests_monthly": UNLIMITED, "deliveries_monthly": UNLIMITED},
    },
}
ASSIGNABLE_PLANS = ("UNASSIGNED", "FOUNDATION", "ENTERPRISE", "DEDICATED")
CONTRACT_METERS = ("agents", "integrations")

STATUSES = {"ACTIVE", "TRIAL", "EXPIRED", "SUSPENDED"}
RESTRICTED_STATUSES = {"EXPIRED", "SUSPENDED"}
MAX_TRIAL_DAYS = 90

# Every reason an org can be in restricted mode, and how a refusal names it. The plan status is
# set by an install operator; billing (billing.py) and the install's licence lease (licensing.py)
# are separate inputs, so lifting one never lifts another.
RESTRICTION_REASONS = {
    "PLAN_EXPIRED": "the plan has expired",
    "PLAN_SUSPENDED": "the plan is suspended",
    "PAYMENT_OVERDUE": "payment is overdue past its grace period",
    "SUBSCRIPTION_CANCELED": "the subscription is cancelled",
    "LICENSE_LAPSED": "this install's licence lease has lapsed",
    "LICENSE_MISSING": "this install has no valid licence lease",
    "ORG_OFFBOARDING": "the organization is offboarding",
    "ORG_DELETED": "the organization has been deleted",
}


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
        connection.execute("""CREATE TABLE IF NOT EXISTS entitlement_schema_marks (
            mark TEXT PRIMARY KEY, applied_at TEXT NOT NULL)""")
    sqlite3.ensure_columns(database_path, "org_entitlements", {"contract_limits_json": "TEXT"})
    _migrate_existing_orgs()


D6_MARK = "d6_explicit_plans"


def _migrate_existing_orgs() -> None:
    """Once per install: when plans became required (D6), every org that already existed on an
    install with real data gets an explicit, audited TRANSITIONAL assignment, so nothing that was
    working stops. A fresh install has nothing to preserve, and its orgs start UNASSIGNED."""
    with sqlite3.connect(database_path) as connection:
        if connection.execute("SELECT 1 FROM entitlement_schema_marks WHERE mark = ?", (D6_MARK,)).fetchone():
            return
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        has_data = False
        for table in ("agent_identities", "export_destinations", "incident_destinations", "notification_destinations"):
            if table in tables and connection.execute(
                    f"-- install-wide existence check across every org_id\nSELECT 1 FROM {table} LIMIT 1").fetchone():
                has_data = True
        orgs = connection.execute("SELECT org_id FROM organizations WHERE status != 'DELETED'").fetchall() \
            if "organizations" in tables else []
        if len(orgs) > 1:
            has_data = True
        migrated = []
        if has_data:
            now = utc_now().isoformat()
            for (org_id,) in orgs:
                if connection.execute("SELECT 1 FROM org_entitlements WHERE org_id = ?", (org_id,)).fetchone():
                    continue
                connection.execute(
                    "INSERT INTO org_entitlements (org_id, plan, status, trial_ends_at, updated_by, updated_at) VALUES (?, 'TRANSITIONAL', 'ACTIVE', NULL, ?, ?)",
                    (org_id, "migration:d6", now))
                _record(connection, org_id, "migration:d6", "PLAN_ASSIGNED", {
                    "plan": "TRANSITIONAL", "status": "ACTIVE",
                    "reason": "Existed before plans were required; pre-D6 behaviour preserved until an operator assigns a plan."})
                migrated.append(org_id)
        connection.execute("INSERT INTO entitlement_schema_marks (mark, applied_at) VALUES (?, ?)", (D6_MARK, utc_now().isoformat()))


def _record(connection, org_id: str, actor: str, event_type: str, detail: dict) -> None:
    connection.execute(
        "INSERT INTO entitlement_events (org_id, timestamp, actor, event_type, detail_json) VALUES (?, ?, ?, ?, ?)",
        (org_id, utc_now().isoformat(), actor, event_type, json.dumps(detail, sort_keys=True)),
    )


def _assignment(org_id: str) -> dict[str, Any]:
    sqlite3.initialize_once("entitlements", database_path, initialize_entitlements)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM org_entitlements WHERE org_id = ?", (org_id,)).fetchone()
    if row is None:
        return {"plan": "UNASSIGNED", "status": "ACTIVE", "trial_ends_at": None, "updated_by": None, "updated_at": None,
                "contract_limits": None}
    assignment = dict(row)
    assignment.pop("org_id", None)
    raw = assignment.pop("contract_limits_json", None)
    assignment["contract_limits"] = json.loads(raw) if raw else None
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
        # Only active agents and enabled integrations consume capacity (D6). Revoked, disabled and
        # archived records stay as history and cost nothing.
        "agents": ("SELECT COUNT(*) FROM agent_identities WHERE org_id = ? AND credential_status = 'ACTIVE' AND archived_at IS NULL", (org_id,)),
        # Timestamps carry their own offsets; comparing against the UTC month start is accurate to
        # within the offset at month boundaries, which is fine for a usage meter.
        "controlled_requests_monthly": (
            "SELECT COUNT(*) FROM tool_requests WHERE org_id = ? AND timestamp >= ?", (org_id, month)),
        "deliveries_monthly": (
            "SELECT COUNT(*) FROM outbound_delivery_evidence WHERE org_id = ? AND event = 'SUCCESS' AND occurred_at >= ?",
            (org_id, month)),
        "integrations": (
            "SELECT (SELECT COUNT(*) FROM export_destinations WHERE org_id = ? AND enabled = 1 AND archived_at IS NULL)"
            " + (SELECT COUNT(*) FROM incident_destinations WHERE org_id = ? AND enabled = 1 AND archived_at IS NULL)"
            " + (SELECT COUNT(*) FROM notification_destinations WHERE org_id = ? AND enabled = 1 AND archived_at IS NULL)",
            (org_id, org_id, org_id)),
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
    if assignment["plan"] == "DEDICATED" and assignment.get("contract_limits"):
        for meter, value in assignment["contract_limits"].items():
            if meter in limits:
                limits[meter] = {**limits[meter], **value}
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
    reasons = [f"PLAN_{assignment['status']}"] if assignment["status"] in RESTRICTED_STATUSES else []
    reasons += [reason for reason in (billing.restriction(org_id), licensing.restriction(), _lifecycle_restriction(org_id)) if reason]
    return {
        "org_id": org_id,
        **assignment,
        "plan_label": plan["label"],
        "plan_required": assignment["plan"] == "UNASSIGNED",
        "transitional": assignment["plan"] == "TRANSITIONAL",
        "restricted": bool(reasons),
        "restriction_reasons": reasons,
        "features": sorted(features),
        "mandatory_protections": sorted(MANDATORY_PROTECTIONS),
        "limits": limits,
        "usage": current,
        "soft_limits_exceeded": sorted(
            meter for meter, limit in limits.items()
            if limit["soft"] is not None and meter in current and current[meter] >= limit["soft"]),
        "overrides": overrides,
    }


def _lifecycle_restriction(org_id: str) -> str | None:
    return {"OFFBOARDING": "ORG_OFFBOARDING", "DELETED": "ORG_DELETED"}.get(organizations.org_status(org_id))


def _restricted_message(entitlements: dict[str, Any], what: str) -> str:
    because = " and ".join(RESTRICTION_REASONS[reason] for reason in entitlements["restriction_reasons"])
    return (f"This organization is restricted because {because}: {what} is paused. "
            "Evidence, export and security controls remain available.")


def require_feature(org_id: str, feature: str) -> None:
    """Refuse a gated capability the org's plan does not include. Mandatory protections can
    never be refused here."""
    if feature in MANDATORY_PROTECTIONS:
        return
    if feature not in FEATURES:
        raise ValueError(f"Unknown entitlement feature: {feature}")
    entitlements = get_entitlements(org_id, meters=())
    if entitlements["restricted"]:
        raise EntitlementError(_restricted_message(entitlements, f"new {feature.replace('_', ' ')} configuration"))
    if entitlements["plan_required"]:
        raise EntitlementError(PLAN_REQUIRED_MESSAGE)
    if feature not in entitlements["features"]:
        raise EntitlementError(
            f"The {entitlements['plan_label']} plan does not include {feature.replace('_', ' ')}.")


def require_capacity(org_id: str, meter: str, increment: int = 1) -> dict[str, Any]:
    """Refuse growth past a hard limit, or any growth while restricted. Returns the meter's state;
    'soft_limit_reached' tells the caller to warn without refusing."""
    if meter not in METERS:
        raise ValueError(f"Unknown meter: {meter}")
    if meter in MONITORED_ONLY_METERS:
        raise ValueError(f"{meter} is monitored only and is never enforced.")
    entitlements = get_entitlements(org_id, meters=(meter,))
    if entitlements["restricted"]:
        raise EntitlementError(_restricted_message(entitlements, f"adding {meter.replace('_', ' ')}"))
    if entitlements["plan_required"]:
        raise EntitlementError(PLAN_REQUIRED_MESSAGE)
    limit = entitlements["limits"][meter]
    current = entitlements["usage"][meter]
    if limit["hard"] is not None and current + increment > limit["hard"]:
        raise EntitlementError(
            f"The {entitlements['plan_label']} plan allows {limit['hard']} active {meter.replace('_', ' ')}; "
            f"{current} are in use. Archive one you no longer need, or ask your GreyGuard operator.")
    after = current + increment
    reached = limit["soft"] is not None and after > limit["soft"]
    return {"meter": meter, "usage": after, "limit": limit, "soft_limit_reached": reached,
            "warning": (f"Approaching the plan limit: {after} of {limit['hard'] if limit['hard'] is not None else limit['soft']} "
                        f"active {meter.replace('_', ' ')}.") if reached else None}


PLAN_REQUIRED_MESSAGE = ("This organization has no plan yet: new agents and integrations need an assigned plan "
                         "or trial from your GreyGuard operator. Existing agents, evidence and exports are unaffected.")


def require_new_integration_capacity(org_id: str, table: str, name: str, enabled: bool = True) -> dict[str, Any] | None:
    """Integrations meter check for a destination save. Only enabled destinations consume
    capacity: saving one disabled is free, updating an already-enabled one is not growth, and
    enabling a new or disabled one is. Returns the capacity state (with any soft-limit warning)."""
    if table not in ("export_destinations", "incident_destinations", "notification_destinations"):
        raise ValueError("Unknown integration table.")
    sqlite3.initialize_once("entitlements", database_path, initialize_entitlements)
    with sqlite3.connect(database_path) as connection:
        existing = connection.execute(
            f"SELECT enabled, archived_at FROM {table} WHERE org_id = ? AND LOWER(name) = LOWER(?)", (org_id, str(name).strip())
        ).fetchone()
    if existing and existing[1]:
        raise ValueError("That destination is archived and kept as history; use a new name.")
    if not enabled or (existing and existing[0]):
        return None
    return require_capacity(org_id, "integrations")


def _validate_contract(contract_limits) -> dict[str, Any]:
    if not isinstance(contract_limits, dict) or set(contract_limits) != set(CONTRACT_METERS):
        raise ValueError("A Dedicated plan needs contract limits for agents and integrations.")
    clean = {}
    for meter in CONTRACT_METERS:
        value = contract_limits[meter]
        soft, hard = (value or {}).get("soft"), (value or {}).get("hard")
        for number in (soft, hard):
            if not isinstance(number, int) or isinstance(number, bool) or number < 0:
                raise ValueError(f"Contract {meter} limits must be non-negative integers.")
        if soft > hard:
            raise ValueError(f"The contract's soft {meter} limit cannot exceed its hard limit.")
        clean[meter] = {"soft": soft, "hard": hard}
    return clean


def assign_plan(org_id: str, plan: str, status: str, actor: str, trial_days: int | None = None,
                contract_limits: dict[str, Any] | None = None) -> dict[str, Any]:
    """Install-operator action: set an org's plan and status, audited."""
    plan, status = str(plan).upper(), str(status).upper()
    if plan not in ASSIGNABLE_PLANS:
        raise ValueError("Unknown plan." if plan not in PLANS else "That plan cannot be assigned.")
    contract = _validate_contract(contract_limits) if plan == "DEDICATED" else None
    if plan != "DEDICATED" and contract_limits:
        raise ValueError("Contract limits apply only to the Dedicated plan.")
    if status not in STATUSES:
        raise ValueError("Unknown entitlement status.")
    trial_ends_at = None
    if status == "TRIAL":
        if not trial_days or not 1 <= int(trial_days) <= MAX_TRIAL_DAYS:
            raise ValueError(f"A trial needs a length of 1 to {MAX_TRIAL_DAYS} days.")
        trial_ends_at = (utc_now() + timedelta(days=int(trial_days))).isoformat()
    sqlite3.initialize_once("entitlements", database_path, initialize_entitlements)
    now = utc_now().isoformat()
    with sqlite3.connect(database_path) as connection:
        contract_json = json.dumps(contract, sort_keys=True) if contract else None
        updated = connection.execute(
            "UPDATE org_entitlements SET plan = ?, status = ?, trial_ends_at = ?, updated_by = ?, updated_at = ?, contract_limits_json = ? WHERE org_id = ?",
            (plan, status, trial_ends_at, actor, now, contract_json, org_id)).rowcount
        if not updated:
            connection.execute(
                "INSERT INTO org_entitlements (org_id, plan, status, trial_ends_at, updated_by, updated_at, contract_limits_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (org_id, plan, status, trial_ends_at, actor, now, contract_json))
        _record(connection, org_id, actor, "PLAN_ASSIGNED", {"plan": plan, "status": status, "trial_ends_at": trial_ends_at,
                                                             "contract_limits": contract})
    return get_entitlements(org_id, meters=())


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
        if meter in MONITORED_ONLY_METERS and level == "hard" and value is not None:
            raise ValueError(f"{meter} is monitored only; it cannot have a hard limit.")
    else:
        raise ValueError("Override keys start with feature: or limit:.")
    if len(str(reason).strip()) < 10:
        raise ValueError("An override needs a reason of at least 10 characters.")
    if expires_in_days is not None and not 1 <= int(expires_in_days) <= 365:
        raise ValueError("An override can last 1 to 365 days, or indefinitely.")
    sqlite3.initialize_once("entitlements", database_path, initialize_entitlements)
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
    sqlite3.initialize_once("entitlements", database_path, initialize_entitlements)
    with sqlite3.connect(database_path) as connection:
        revoked = connection.execute(
            "UPDATE entitlement_overrides SET revoked_at = ?, revoked_by = ? WHERE override_id = ? AND org_id = ? AND revoked_at IS NULL",
            (utc_now().isoformat(), actor, override_id, org_id)).rowcount
        if not revoked:
            raise KeyError("Active override not found.")
        _record(connection, org_id, actor, "OVERRIDE_REVOKED", {"override_id": override_id})
    return get_entitlements(org_id)


def entitlement_history(org_id: str, limit: int = 50) -> list[dict[str, Any]]:
    sqlite3.initialize_once("entitlements", database_path, initialize_entitlements)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT timestamp, actor, event_type, detail_json FROM entitlement_events WHERE org_id = ? ORDER BY event_id DESC LIMIT ?",
            (org_id, max(1, min(int(limit), 200)))).fetchall()
    return [{"timestamp": r["timestamp"], "actor": r["actor"], "event_type": r["event_type"],
             "detail": json.loads(r["detail_json"])} for r in rows]
