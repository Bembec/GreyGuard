"""Retiring agents and integrations without destroying evidence (P4 decision D6).

Only active agents and enabled integrations consume plan capacity. Archiving is how an org frees
capacity for good while keeping the record:

- An archived agent's credential is revoked, it can never be re-issued or re-scoped, and its
  identity, credential history, requests, decisions and audit events all remain.
- An archived destination is disabled and can never be re-enabled or edited; its delivery history
  remains. A new destination must use a new name.
- Archiving needs a reason, is limited to the org that owns the record, and is recorded in the
  org's entitlement event log (and, for agents, the credential history).

Nothing here deletes a row.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import db_compat as sqlite3
from . import entitlements
from . import database

DESTINATION_TABLES = {
    "security_export": "export_destinations",
    "incident": "incident_destinations",
    "notification": "notification_destinations",
}


class ArchiveError(ValueError):
    """An archive request that cannot be carried out."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reason(reason: str) -> str:
    reason = str(reason).strip()
    if len(reason) < 10:
        raise ArchiveError("Archiving needs a reason of at least 10 characters.")
    return reason


def _entitlement_event(org_id: str, actor: str, event_type: str, detail: dict[str, Any]) -> None:
    sqlite3.initialize_once("entitlements", database.database_path, entitlements.initialize_entitlements)
    with sqlite3.connect(database.database_path) as connection:
        entitlements._record(connection, org_id, actor, event_type, detail)


def agent_record(org_id: str, agent_name: str) -> dict[str, Any] | None:
    from . import main
    with sqlite3.connect(database.database_path) as connection:
        row = connection.execute(
            "SELECT credential_status, archived_at FROM agent_identities WHERE agent_name = ? AND org_id = ?",
            (main.normalize_agent_name(agent_name), org_id)).fetchone()
    return {"credential_status": row[0], "archived_at": row[1]} if row else None


def archive_agent(org_id: str, agent_name: str, actor: str, reason: str) -> dict[str, Any]:
    from . import main

    reason = _reason(reason)
    name = main.normalize_agent_name(agent_name)
    with sqlite3.connect(database.database_path) as connection:
        row = connection.execute(
            "SELECT credential_status, archived_at FROM agent_identities WHERE agent_name = ? AND org_id = ?",
            (name, org_id)).fetchone()
    if row is None:
        raise KeyError("Agent not found.")
    if row[1]:
        raise ArchiveError("This agent is already archived.")
    if row[0] != "REVOKED":
        main.revoke_agent_credential(name, actor=actor, org_id=org_id)
    now = _now()
    with sqlite3.connect(database.database_path) as connection:
        archived = connection.execute(
            "UPDATE agent_identities SET archived_at = ?, archived_by = ?, archive_reason = ? WHERE agent_name = ? AND org_id = ? AND archived_at IS NULL",
            (now, actor, reason, name, org_id)).rowcount
    if not archived:
        raise ArchiveError("This agent is already archived.")
    main.record_credential_history_event(agent_name=name, event_type="ARCHIVED", actor=actor, timestamp=now, org_id=org_id)
    _entitlement_event(org_id, actor, "AGENT_ARCHIVED", {"agent_name": name, "reason": reason})
    return {"agent_name": name, "archived": True, "archived_at": now, "reason": reason,
            "capacity": entitlements.get_entitlements(org_id, meters=("agents",))["usage"]}


def archive_destination(org_id: str, kind: str, destination_id: str, actor: str, reason: str) -> dict[str, Any]:
    if kind not in DESTINATION_TABLES:
        raise ArchiveError("Unknown destination kind.")
    reason = _reason(reason)
    table = DESTINATION_TABLES[kind]
    now = _now()
    with sqlite3.connect(database.database_path) as connection:
        row = connection.execute(f"SELECT name, archived_at FROM {table} WHERE destination_id = ? AND org_id = ?",
                                 (destination_id, org_id)).fetchone()
        if row is None:
            raise KeyError("Destination not found.")
        if row[1]:
            raise ArchiveError("This destination is already archived.")
        connection.execute(
            f"UPDATE {table} SET enabled = 0, archived_at = ?, archived_by = ?, archive_reason = ? WHERE destination_id = ? AND org_id = ? AND archived_at IS NULL",
            (now, actor, reason, destination_id, org_id))
    _entitlement_event(org_id, actor, "INTEGRATION_ARCHIVED",
                       {"kind": kind, "destination_id": destination_id, "name": row[0], "reason": reason})
    return {"destination_id": destination_id, "name": row[0], "archived": True, "archived_at": now, "reason": reason,
            "capacity": entitlements.get_entitlements(org_id, meters=("integrations",))["usage"]}
