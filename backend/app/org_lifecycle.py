"""Organization lifecycle: onboarding, export, offboarding and deletion (P2.5).

An organization moves ACTIVE -> OFFBOARDING -> DELETED:

- Onboarding: an install operator creates a customer's org without joining it, invites the
  customer's first owner, and can assign a plan in the same step. A checklist computed from the
  org's real data shows how far it is from a governed production setup.
- Export: an org's owners (or an install operator) can download every row the org owns, at any
  time - restricted mode and offboarding included, because evidence export is a mandatory
  protection. Credential material is redacted; every table carries a row count and digest.
- Offboarding: started by an owner or install operator with a reason. It shuts the org's doors
  at once - agent credentials and service-account keys revoked, outbound integrations and report
  schedules disabled, pending invitations revoked, any subscription cancelled - while members
  keep read access and evidence stays exportable until deletion. An install operator can cancel
  it; revoked credentials stay revoked.
- Deletion: install-operator only, once the offboarding retention period has passed, with the
  org's slug typed as confirmation, and never while a legal hold applies. Every row in every
  org-scoped table is deleted in one transaction, the org's files are removed, erased audit
  events are recorded so the install-wide integrity chain still verifies, and a deletion
  certificate is kept. The organizations row stays as a DELETED tombstone.

The lifecycle log (org_lifecycle_events) and offboarding records are install-level: they must
outlive the org they describe.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import audit_integrity, billing, entitlements, organizations, tenant_guard
from . import db_compat as sqlite3
from .database import database_path

EXPORT_FORMAT = "greyguard-organization-export/1"
DEFAULT_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 365

# Columns whose values are credential material. Exports replace them with REDACTED; a test
# requires every secret-looking column in the schema to be listed here or in EVIDENCE_COLUMNS,
# so a new column cannot reach an export without a decision.
REDACTED_COLUMNS = frozenset({
    "credential_hash", "credential_salt", "key_hash", "token_hash", "claim_token", "token",
    "password_hash", "password_salt", "mfa_secret",
})
# Secret-looking names that are not secrets: digests, chain hashes, references and identifiers.
EVIDENCE_COLUMNS = frozenset({
    "evidence_hash", "identifier_hash", "payload_hash", "previous_hash", "record_hash", "override_key",
    "key_id", "key_prefix", "public_key_fingerprint", "dedupe_key", "credential_reference",
    "signing_key_reference", "secret_id", "credential_status", "password_expires_at",
})
SECRET_LOOKING = re.compile(r"hash|salt|secret|token|password|credential|key", re.IGNORECASE)
REDACTED = "REDACTED"

# Foreign-key children, deleted before everything else so no parent row is removed while a
# child still references it. A test checks this against the live SQLite schema.
CHILD_TABLES_FIRST = (
    "alert_notes", "approval_events", "execution_events", "export_queue", "policy_change_events",
    "policy_test_cases", "secret_events", "service_account_keys",
)


class LifecycleError(ValueError):
    """A lifecycle action the org's current state does not allow."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def initialize_org_lifecycle() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS org_offboarding (
            org_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, started_by TEXT NOT NULL, reason TEXT NOT NULL,
            deletion_eligible_at TEXT NOT NULL, actions_json TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS org_lifecycle_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, org_id TEXT NOT NULL, timestamp TEXT NOT NULL,
            actor TEXT NOT NULL, event_type TEXT NOT NULL, detail_json TEXT NOT NULL)""")


def _record(connection, org_id: str, actor: str, event_type: str, detail: dict) -> None:
    connection.execute(
        "INSERT INTO org_lifecycle_events (org_id, timestamp, actor, event_type, detail_json) VALUES (?, ?, ?, ?, ?)",
        (org_id, utc_now().isoformat(), actor, event_type, json.dumps(detail, sort_keys=True, default=str)))


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _existing_tables(connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _scoped_tables(connection) -> list[str]:
    """Every org-scoped table that exists, foreign-key children first."""
    existing = _existing_tables(connection)
    rest = sorted(tenant_guard.ORG_SCOPED_TABLES - set(CHILD_TABLES_FIRST))
    return [table for table in (*CHILD_TABLES_FIRST, *rest) if table in existing]


def history(org_id: str, limit: int = 100) -> list[dict[str, Any]]:
    initialize_org_lifecycle()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT timestamp, actor, event_type, detail_json FROM org_lifecycle_events WHERE org_id = ? ORDER BY event_id DESC LIMIT ?",
            (org_id, max(1, min(int(limit), 500)))).fetchall()
    return [{"timestamp": r["timestamp"], "actor": r["actor"], "event_type": r["event_type"],
             "detail": json.loads(r["detail_json"])} for r in rows]


def offboarding(org_id: str) -> dict[str, Any] | None:
    initialize_org_lifecycle()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM org_offboarding WHERE org_id = ?", (org_id,)).fetchone()
    if row is None:
        return None
    record = dict(row)
    record["actions"] = json.loads(record.pop("actions_json"))
    return record


# --- Onboarding --------------------------------------------------------------------------------

def onboard(name: str, slug: str | None, owner_email: str, actor_admin_id: str, actor: str,
            plan: str | None = None, trial_days: int | None = None) -> dict[str, Any]:
    """Install-operator action: create a customer org, invite its first owner, and optionally
    assign a plan (a trial when trial_days is given)."""
    initialize_org_lifecycle()
    org = organizations.create_organization(name, actor_admin_id, slug, creator_is_owner=False)
    invitation = organizations.issue_invitation(org["org_id"], owner_email, "PLATFORM_ADMIN", "OWNER", actor_admin_id)
    if plan:
        entitlements.assign_plan(org["org_id"], plan, "TRIAL" if trial_days else "ACTIVE", actor, trial_days)
    with sqlite3.connect(database_path) as connection:
        _record(connection, org["org_id"], actor, "ONBOARDED",
                {"owner_email": invitation["email"], "plan": plan, "trial_days": trial_days})
    return {"organization": org, "owner_invitation": invitation}


def checklist(org_id: str) -> list[dict[str, Any]]:
    """Onboarding progress, computed from the org's real data rather than ticked by hand."""
    members = [member for member in organizations.list_members(org_id) if member.get("status", "ACTIVE") == "ACTIVE"]
    with sqlite3.connect(database_path) as connection:
        mfa = {row[0]: bool(row[1]) for row in connection.execute(
            "SELECT admin_id, mfa_enabled FROM administrators").fetchall()}
        approved_policy = connection.execute(
            "SELECT COUNT(*) FROM policy_versions WHERE org_id = ? AND status = 'PUBLISHED'", (org_id,)).fetchone()[0]
    usage = entitlements.usage(org_id, ("agents", "integrations"))
    exported = any(event["event_type"] == "EXPORTED" for event in history(org_id, 500))
    items = [
        ("owner_active", "An owner has joined", any(m["governance_role"] == "OWNER" for m in members)),
        ("separation_of_duties", "At least two administrators, so approvals can need a second person", len(members) >= 2),
        ("auditor_assigned", "An auditor has read-only oversight", any(m["operational_role"] == "AUDITOR" for m in members)),
        ("mfa_everyone", "Every member uses MFA", bool(members) and all(mfa.get(m["admin_id"]) for m in members)),
        ("plan_assigned", "A plan is assigned", entitlements.get_entitlements(org_id, meters=())["plan"] != "UNASSIGNED"),
        ("policy_baseline", "A policy baseline is active", approved_policy > 0),
        ("first_agent", "A first agent is registered", usage["agents"] > 0),
        ("integration", "An evidence or incident integration is configured", usage["integrations"] > 0),
        ("export_tested", "An evidence export has been tested", exported),
    ]
    return [{"key": key, "label": label, "done": bool(done)} for key, label, done in items]


def lifecycle(org_id: str) -> dict[str, Any]:
    org = organizations.get_organization(org_id)
    items = checklist(org_id) if org["status"] != "DELETED" else []
    return {"org_id": org_id, "name": org["name"], "status": org["status"], "offboarding": offboarding(org_id),
            "checklist": items, "checklist_complete": sum(item["done"] for item in items),
            "history": history(org_id)}


# --- Export ------------------------------------------------------------------------------------

def export_organization(org_id: str, actor: str) -> dict[str, Any]:
    """Every row of every org-scoped table for one org, with credential material redacted. Each
    table carries a row count and SHA-256 digest, and the bundle a digest over all of them."""
    org = organizations.get_organization(org_id)
    if org["status"] == "DELETED":
        raise LifecycleError("This organization has been deleted; nothing remains to export.")
    initialize_org_lifecycle()
    tables: dict[str, list[dict[str, Any]]] = {}
    manifest: dict[str, dict[str, Any]] = {}
    redacted: dict[str, list[str]] = {}
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        for table in sorted(_scoped_tables(connection)):
            rows = [dict(row) for row in connection.execute(f"SELECT * FROM {table} WHERE org_id = ?", (org_id,)).fetchall()]
            columns = sorted({column for row in rows for column in row} & REDACTED_COLUMNS)
            for row in rows:
                for column in columns:
                    if row[column] is not None:
                        row[column] = REDACTED
            tables[table] = rows
            manifest[table] = {"rows": len(rows), "sha256": hashlib.sha256(_canonical(rows)).hexdigest()}
            if columns:
                redacted[table] = columns
    bundle = {
        "format": EXPORT_FORMAT, "generated_at": utc_now().isoformat(), "generated_by": actor,
        "organization": {key: org[key] for key in ("org_id", "name", "slug", "status", "created_at")},
        "members": organizations.list_members(org_id), "manifest": manifest, "redacted_columns": redacted,
        "tables": tables,
    }
    bundle["digest"] = hashlib.sha256(_canonical({k: bundle[k] for k in ("format", "organization", "manifest")})).hexdigest()
    with sqlite3.connect(database_path) as connection:
        _record(connection, org_id, actor, "EXPORTED",
                {"digest": bundle["digest"], "rows": sum(item["rows"] for item in manifest.values())})
    return bundle


# --- Offboarding -------------------------------------------------------------------------------

def _close_doors(org_id: str, actor: str) -> dict[str, Any]:
    """Stop everything that acts or sends data on the org's behalf. Each step reports what it did;
    a failing step is recorded and the rest still run."""
    from . import main, service_accounts  # main imports half the backend; keep it lazy

    actions: dict[str, Any] = {}

    def step(name, function):
        try:
            actions[name] = function()
        except Exception as error:  # recorded, never silently dropped
            actions[name] = {"error": str(error)}

    def revoke_agents():
        with sqlite3.connect(database_path) as connection:
            names = [row[0] for row in connection.execute(
                "SELECT agent_name FROM agent_identities WHERE org_id = ? AND credential_status != 'REVOKED'", (org_id,)).fetchall()]
        for name in names:
            main.revoke_agent_credential(name, actor=actor, org_id=org_id)
        return len(names)

    def revoke_service_accounts():
        accounts = [a for a in service_accounts.list_service_accounts(org_id) if a.get("status") != "REVOKED"]
        for account in accounts:
            service_accounts.revoke_service_account(account["account_id"], actor, org_id)
        return len(accounts)

    def disable(table):
        def run():
            with sqlite3.connect(database_path) as connection:
                existing = _existing_tables(connection)
                if table not in existing:
                    return 0
                return connection.execute(f"UPDATE {table} SET enabled = 0 WHERE org_id = ? AND enabled != 0", (org_id,)).rowcount
        return run

    def revoke_invitations():
        with sqlite3.connect(database_path) as connection:
            return connection.execute(
                "UPDATE org_invitations SET revoked_at = ? WHERE org_id = ? AND accepted_at IS NULL AND revoked_at IS NULL",
                (utc_now().isoformat(), org_id)).rowcount

    def cancel_billing():
        account = billing.get_account(org_id)
        if account is None or account["billing_state"] == "CANCELED":
            return "none"
        billing.cancel_account(org_id, actor)
        return "cancelled"

    step("agent_credentials_revoked", revoke_agents)
    step("service_accounts_revoked", revoke_service_accounts)
    for table in ("export_destinations", "incident_destinations", "notification_destinations", "report_schedules"):
        step(f"{table}_disabled", disable(table))
    step("invitations_revoked", revoke_invitations)
    step("billing", cancel_billing)
    return actions


def start_offboarding(org_id: str, actor: str, reason: str, retention_days: int = DEFAULT_RETENTION_DAYS) -> dict[str, Any]:
    if org_id == organizations.DEFAULT_ORG_ID:
        raise LifecycleError("The default organization cannot be offboarded.")
    if len(str(reason).strip()) < 10:
        raise LifecycleError("Offboarding needs a reason of at least 10 characters.")
    if not 0 <= int(retention_days) <= MAX_RETENTION_DAYS:
        raise LifecycleError(f"The retention period is 0 to {MAX_RETENTION_DAYS} days.")
    org = organizations.get_organization(org_id)
    if org["status"] != "ACTIVE":
        raise LifecycleError(f"This organization is already {org['status'].lower()}.")
    initialize_org_lifecycle()
    now = utc_now()
    with sqlite3.connect(database_path) as connection:
        # Mark the org first, so nothing new can be added while its doors are being closed.
        if not connection.execute("UPDATE organizations SET status = 'OFFBOARDING' WHERE org_id = ? AND status = 'ACTIVE'",
                                  (org_id,)).rowcount:
            raise LifecycleError("This organization is no longer active.")
    actions = _close_doors(org_id, actor)
    eligible = now + timedelta(days=int(retention_days))
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO org_offboarding (org_id, started_at, started_by, reason, deletion_eligible_at, actions_json) VALUES (?, ?, ?, ?, ?, ?)",
            (org_id, now.isoformat(), actor, reason.strip(), eligible.isoformat(), json.dumps(actions, sort_keys=True)))
        _record(connection, org_id, actor, "OFFBOARDING_STARTED",
                {"reason": reason.strip(), "deletion_eligible_at": eligible.isoformat(), "actions": actions})
    return lifecycle(org_id)


def cancel_offboarding(org_id: str, actor: str) -> dict[str, Any]:
    """Install-operator action. The org becomes ACTIVE again, but revoked credentials stay revoked
    and disabled integrations stay disabled: they are reissued and re-enabled deliberately."""
    initialize_org_lifecycle()
    with sqlite3.connect(database_path) as connection:
        if not connection.execute("UPDATE organizations SET status = 'ACTIVE' WHERE org_id = ? AND status = 'OFFBOARDING'",
                                  (org_id,)).rowcount:
            raise LifecycleError("This organization is not offboarding.")
        connection.execute("DELETE FROM org_offboarding WHERE org_id = ?", (org_id,))
        _record(connection, org_id, actor, "OFFBOARDING_CANCELLED", {})
    return lifecycle(org_id)


# --- Deletion ----------------------------------------------------------------------------------

def _legal_hold_blocks(connection, agent_names: list[str]) -> bool:
    holds = connection.execute("SELECT agent_name FROM audit_legal_holds WHERE active = 1").fetchall()
    return any(hold[0] is None or hold[0] in agent_names for hold in holds)


def delete_organization(org_id: str, actor: str, confirm_slug: str) -> dict[str, Any]:
    """Install-operator action: permanently delete everything an offboarded org owns."""
    from . import isolation_operations, main

    if org_id == organizations.DEFAULT_ORG_ID:
        raise LifecycleError("The default organization cannot be deleted.")
    org = organizations.get_organization(org_id)
    if org["status"] != "OFFBOARDING":
        raise LifecycleError("Only an organization that is offboarding can be deleted.")
    if str(confirm_slug).strip() != org["slug"]:
        raise LifecycleError("Type the organization's slug exactly to confirm deletion.")
    record = offboarding(org_id)
    now = utc_now()
    if record is None or record["deletion_eligible_at"] > now.isoformat():
        raise LifecycleError(f"Deletion is possible from {record['deletion_eligible_at'] if record else 'the end of offboarding'}.")
    audit_integrity.initialize_audit_integrity()
    audit_integrity.seal_audit_events()
    exports = [event["detail"]["digest"] for event in history(org_id, 500) if event["event_type"] == "EXPORTED"]
    with sqlite3.connect(database_path) as connection:
        agent_names = [row[0] for row in connection.execute(
            "SELECT agent_name FROM agent_identities WHERE org_id = ?", (org_id,)).fetchall()]
        if _legal_hold_blocks(connection, agent_names):
            raise LifecycleError("A legal hold covers this organization's evidence; release it before deletion.")
        files = [row[0] for row in connection.execute(
            "SELECT quarantine_path FROM quarantined_artifacts WHERE org_id = ?", (org_id,)).fetchall()] \
            if "quarantined_artifacts" in _existing_tables(connection) else []
        erased = [row[0] for row in connection.execute("SELECT id FROM audit_events WHERE org_id = ?", (org_id,)).fetchall()]
        audit_integrity.record_erasures(connection, erased, actor, f"Organization {org_id} deleted")
        deleted: dict[str, int] = {}
        for table in _scoped_tables(connection):
            count = connection.execute(f"DELETE FROM {table} WHERE org_id = ?", (org_id,)).rowcount
            if count:
                deleted[table] = count
        deleted["org_memberships"] = connection.execute("DELETE FROM org_memberships WHERE org_id = ?", (org_id,)).rowcount
        deleted["org_invitations"] = connection.execute("DELETE FROM org_invitations WHERE org_id = ?", (org_id,)).rowcount
        connection.execute("UPDATE administrator_sessions SET active_org_id = NULL WHERE active_org_id = ?", (org_id,))
        # The tombstone keeps the name for the certificate but frees the slug for reuse.
        connection.execute("UPDATE organizations SET status = 'DELETED', slug = ? WHERE org_id = ?",
                           (f"deleted-{org_id}", org_id))
    # Files and runtime state go only after the database deletion committed.
    removed_files = 0
    workspace = (isolation_operations.workspace_root / org_id).resolve()
    if isolation_operations._inside(isolation_operations.workspace_root, workspace) and workspace.exists():
        shutil.rmtree(workspace)
        removed_files += 1
    for path in files:
        target = Path(path).resolve()
        if isolation_operations._inside(isolation_operations.quarantine_root, target) and target.exists():
            target.unlink()
            removed_files += 1
    for name in agent_names:
        main.agent_states.pop(name, None)
    if agent_names:
        main.save_state()
    certificate = {
        "certificate_id": "del_" + uuid.uuid4().hex, "org_id": org_id, "name": org["name"],
        "deleted_at": utc_now().isoformat(), "deleted_by": actor, "offboarding_reason": record["reason"],
        "rows_deleted": deleted, "total_rows_deleted": sum(deleted.values()), "audit_events_erased": len(erased),
        "files_removed": removed_files, "agents_removed": sorted(agent_names), "export_digests": exports,
    }
    certificate["certificate_sha256"] = hashlib.sha256(_canonical(certificate)).hexdigest()
    with sqlite3.connect(database_path) as connection:
        _record(connection, org_id, actor, "DELETED", certificate)
    return certificate


def deletion_certificate(org_id: str) -> dict[str, Any]:
    for event in history(org_id, 500):
        if event["event_type"] == "DELETED":
            return event["detail"]
    raise KeyError("No deletion certificate for this organization.")


def verify_certificate(certificate: dict[str, Any]) -> bool:
    body = {key: value for key, value in certificate.items() if key != "certificate_sha256"}
    return hashlib.sha256(_canonical(body)).hexdigest() == certificate.get("certificate_sha256")
