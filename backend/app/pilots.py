"""Paid-pilot tracking for onboarding (P5), following provisional P4 decision D2.

A pilot is a fixed-scope, 90-day evaluation on the Enterprise plan in TRIAL status, hosted, with
success criteria agreed up front and a conversion decision due at day 75. This module records the
pilot and measures its criteria from the product's own data, so the pilot review argues from
evidence rather than impressions:

- readiness_complete: the org's readiness checklist (org_lifecycle.checklist) is complete;
- sustained_use: agents have sent controlled requests for at least four weeks, and recently;
- human_approval: at least one held action was approved or rejected by a person;
- emergency_exercised: the emergency global deny was switched on at least once;
- evidence_accepted: an org export exists, and an install operator confirms (with a note) that the
  customer's governance approver accepted it;
- no_service_incident: an install operator confirms (with a note) that no SEV1/SEV2 incident was
  caused by GreyGuard during the pilot; the status page's incidents in the window are shown.

Outcomes reuse existing machinery: CONVERT assigns Enterprise ACTIVE, EXTEND lengthens the trial
once by up to 30 days, OFFBOARD starts offboarding. No fee, price or payment detail is stored -
the pilot fee is an open commercial decision (P4 D3).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db_compat as sqlite3
from . import entitlements, org_lifecycle, organizations
from .database import database_path

PILOT_PLAN = "ENTERPRISE"
PILOT_DAYS = 90
DECISION_DAY = 75
MAX_EXTENSION_DAYS = 30
SUSTAINED_USE_DAYS = 28
MANUAL_CRITERIA = ("evidence_accepted", "no_service_incident")
CRITERIA = (
    ("readiness_complete", "Readiness checklist complete"),
    ("sustained_use", "Agents routed through GreyGuard for real work for four weeks or more"),
    ("human_approval", "At least one held action approved or rejected by a person"),
    ("emergency_exercised", "Emergency global deny exercised"),
    ("evidence_accepted", "An evidence export accepted by the customer's governance approver"),
    ("no_service_incident", "No SEV1/SEV2 incident caused by GreyGuard during the pilot"),
)
OUTCOMES = ("CONVERT", "EXTEND", "OFFBOARD")


class PilotError(ValueError):
    """A pilot action the pilot's state does not allow."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def initialize_pilots() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS org_pilots (
            org_id TEXT PRIMARY KEY, status TEXT NOT NULL, started_at TEXT NOT NULL, ends_at TEXT NOT NULL,
            decision_due_at TEXT NOT NULL, extended INTEGER NOT NULL DEFAULT 0, confirmations_json TEXT NOT NULL,
            created_by TEXT NOT NULL, decided_at TEXT, decided_by TEXT, decision TEXT, decision_reason TEXT)""")


def _row(org_id: str) -> dict[str, Any] | None:
    initialize_pilots()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM org_pilots WHERE org_id = ?", (org_id,)).fetchone()
    if row is None:
        return None
    pilot = dict(row)
    pilot["confirmations"] = json.loads(pilot.pop("confirmations_json"))
    return pilot


def _record(org_id: str, actor: str, event_type: str, detail: dict) -> None:
    org_lifecycle.initialize_org_lifecycle()
    with sqlite3.connect(database_path) as connection:
        org_lifecycle._record(connection, org_id, actor, event_type, detail)


def start_pilot(org_id: str, actor: str) -> dict[str, Any]:
    """Install-operator action: put an org on the D2 pilot template."""
    if org_id == organizations.DEFAULT_ORG_ID:
        raise PilotError("The default organization cannot run a pilot.")
    if organizations.get_organization(org_id)["status"] != "ACTIVE":
        raise PilotError("Only an active organization can start a pilot.")
    if _row(org_id) is not None:
        raise PilotError("This organization already has a pilot.")
    entitlements.assign_plan(org_id, PILOT_PLAN, "TRIAL", actor, PILOT_DAYS)
    now = utc_now()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """INSERT INTO org_pilots (org_id, status, started_at, ends_at, decision_due_at, confirmations_json, created_by)
            VALUES (?, 'ACTIVE', ?, ?, ?, '{}', ?)""",
            (org_id, now.isoformat(), (now + timedelta(days=PILOT_DAYS)).isoformat(),
             (now + timedelta(days=DECISION_DAY)).isoformat(), actor))
    _record(org_id, actor, "PILOT_STARTED", {"plan": PILOT_PLAN, "days": PILOT_DAYS, "decision_day": DECISION_DAY})
    return pilot_status(org_id)


def _measured(org_id: str, pilot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    now = utc_now()
    with sqlite3.connect(database_path) as connection:
        first, last = connection.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM tool_requests WHERE org_id = ?", (org_id,)).fetchone()
        approvals = connection.execute("SELECT COUNT(*) FROM approval_events WHERE org_id = ?", (org_id,)).fetchone()[0]
        emergencies = connection.execute(
            "SELECT COUNT(*) FROM policy_emergency_events WHERE org_id = ? AND global_deny = 1", (org_id,)).fetchone()[0]
        try:
            incidents = connection.execute(
                "-- install-level status incidents, not tenant data\nSELECT COUNT(*) FROM status_incidents WHERE severity IN ('SEV1','SEV2') AND started_at >= ?",
                (pilot["started_at"],)).fetchone()[0]
        except sqlite3.Error:
            incidents = 0
    exports = sum(1 for event in org_lifecycle.history(org_id, 500) if event["event_type"] == "EXPORTED")
    checklist = org_lifecycle.checklist(org_id)
    in_use_days = (now - datetime.fromisoformat(first)).days if first else 0
    recent = bool(last) and datetime.fromisoformat(last) >= now - timedelta(days=7)
    confirmations = pilot["confirmations"]
    return {
        "readiness_complete": {"met": all(item["done"] for item in checklist),
                               "evidence": f"{sum(i['done'] for i in checklist)} of {len(checklist)} checklist items"},
        "sustained_use": {"met": in_use_days >= SUSTAINED_USE_DAYS and recent,
                          "evidence": f"{in_use_days} days since the first controlled request" + ("" if recent else "; none in the last 7 days")},
        "human_approval": {"met": approvals > 0, "evidence": f"{approvals} approval decisions"},
        "emergency_exercised": {"met": emergencies > 0, "evidence": f"{emergencies} times switched on"},
        "evidence_accepted": {"met": exports > 0 and "evidence_accepted" in confirmations,
                              "evidence": f"{exports} org exports taken", "confirmation": confirmations.get("evidence_accepted")},
        "no_service_incident": {"met": "no_service_incident" in confirmations,
                                "evidence": f"{incidents} SEV1/SEV2 status-page incidents since the pilot started",
                                "confirmation": confirmations.get("no_service_incident")},
    }


def pilot_status(org_id: str) -> dict[str, Any] | None:
    pilot = _row(org_id)
    if pilot is None:
        return None
    measured = _measured(org_id, pilot)
    now = utc_now()
    criteria = [{"key": key, "label": label, "manual": key in MANUAL_CRITERIA, **measured[key]} for key, label in CRITERIA]
    return {**pilot, "criteria": criteria, "criteria_met": sum(c["met"] for c in criteria), "criteria_total": len(criteria),
            "days_remaining": max(0, (datetime.fromisoformat(pilot["ends_at"]) - now).days),
            "decision_due": pilot["status"] == "ACTIVE" and datetime.fromisoformat(pilot["decision_due_at"]) <= now,
            "template": {"plan": PILOT_PLAN, "days": PILOT_DAYS, "decision_day": DECISION_DAY,
                         "max_extension_days": MAX_EXTENSION_DAYS}}


def confirm(org_id: str, criterion: str, note: str, actor: str) -> dict[str, Any]:
    """Install-operator action: confirm a criterion only a person can judge, with a note."""
    if criterion not in MANUAL_CRITERIA:
        raise PilotError("Only evidence_accepted and no_service_incident are confirmed by hand.")
    if len(str(note).strip()) < 10:
        raise PilotError("A confirmation needs a note of at least 10 characters saying who confirmed what.")
    pilot = _row(org_id)
    if pilot is None:
        raise KeyError("This organization has no pilot.")
    if pilot["status"] != "ACTIVE":
        raise PilotError("This pilot has already been decided.")
    pilot["confirmations"][criterion] = {"by": actor, "at": utc_now().isoformat(), "note": note.strip()}
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE org_pilots SET confirmations_json = ? WHERE org_id = ?",
                           (json.dumps(pilot["confirmations"], sort_keys=True), org_id))
    _record(org_id, actor, "PILOT_CRITERION_CONFIRMED", {"criterion": criterion, "note": note.strip()})
    return pilot_status(org_id)


def decide(org_id: str, outcome: str, reason: str, actor: str, extend_days: int | None = None) -> dict[str, Any]:
    """Install-operator action: the pilot's conversion decision."""
    if outcome not in OUTCOMES:
        raise PilotError("The outcome is CONVERT, EXTEND or OFFBOARD.")
    if len(str(reason).strip()) < 10:
        raise PilotError("A pilot decision needs a reason of at least 10 characters.")
    pilot = _row(org_id)
    if pilot is None:
        raise KeyError("This organization has no pilot.")
    if pilot["status"] != "ACTIVE":
        raise PilotError("This pilot has already been decided.")
    now = utc_now()
    if outcome == "EXTEND":
        if pilot["extended"]:
            raise PilotError("A pilot can be extended only once.")
        if not extend_days or not 1 <= int(extend_days) <= MAX_EXTENSION_DAYS:
            raise PilotError(f"An extension is 1 to {MAX_EXTENSION_DAYS} days.")
        ends = max(datetime.fromisoformat(pilot["ends_at"]), now) + timedelta(days=int(extend_days))
        if (ends - now).days > entitlements.MAX_TRIAL_DAYS:
            raise PilotError("An extension is decided near the end of the pilot (from day "
                             f"{DECISION_DAY}); this one would run past {entitlements.MAX_TRIAL_DAYS} days from today.")
        entitlements.assign_plan(org_id, PILOT_PLAN, "TRIAL", actor, max(1, (ends - now).days))
        with sqlite3.connect(database_path) as connection:
            connection.execute("UPDATE org_pilots SET extended = 1, ends_at = ?, decision_due_at = ? WHERE org_id = ?",
                               (ends.isoformat(), (ends - timedelta(days=15)).isoformat(), org_id))
        _record(org_id, actor, "PILOT_EXTENDED", {"days": int(extend_days), "reason": reason.strip()})
        return pilot_status(org_id)
    if outcome == "CONVERT":
        entitlements.assign_plan(org_id, PILOT_PLAN, "ACTIVE", actor)
    else:
        org_lifecycle.start_offboarding(org_id, actor, f"Pilot not converted: {reason.strip()}")
    status = {"CONVERT": "CONVERTED", "OFFBOARD": "OFFBOARDED"}[outcome]
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE org_pilots SET status = ?, decided_at = ?, decided_by = ?, decision = ?, decision_reason = ? WHERE org_id = ?",
            (status, now.isoformat(), actor, outcome, reason.strip(), org_id))
    _record(org_id, actor, "PILOT_DECIDED", {"outcome": outcome, "reason": reason.strip()})
    return pilot_status(org_id)
