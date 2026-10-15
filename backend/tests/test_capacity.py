"""P4 decision D6: only active agents and enabled integrations consume capacity; archiving frees
capacity without destroying evidence; soft-limit warnings reach the caller; a hard limit blocks
only new growth; plans are explicit (no unlimited default); Dedicated limits come from the
contract; and the migration preserves existing installs."""
import hashlib
import sqlite3 as raw_sqlite

import pytest
from fastapi.testclient import TestClient

from backend.app import (
    admin_auth, api, database, entitlements, main, notification_delivery, organizations, security_exports,
)
from backend.tests.test_org_lifecycle import PASSWORD, install, join, tenant  # noqa: F401 - fixture reuse


@pytest.fixture()
def org(install):
    org = tenant(install, "Capacity", plan="FOUNDATION")  # 20/25 agents, 3/5 integrations
    return {**org, "client": TestClient(api.app), "h": {"X-Admin-Pin": org["owner"]}}


def agent(org, name):
    return org["client"].post("/agents", headers=org["h"], json={"agent_name": name, "scopes": ["read_file"]})


def destination(org, name, enabled=True):
    return org["client"].post("/notification-delivery/destinations", headers=org["h"], json={
        "name": name, "channel": "EMAIL", "endpoint_reference": "SECOPS_EMAIL", "enabled": enabled})


def usage(org):
    return org["client"].get("/entitlements", headers=org["h"]).json()["usage"]


def override(org, key, value):
    api.add_entitlement_override(org["org_id"], api.EntitlementOverrideRequest(
        key=key, value=value, reason="Narrow limits for this capacity test"), org["operator"])


# --- Metering ------------------------------------------------------------------------------------

def test_only_active_agents_and_enabled_integrations_consume_capacity(org):
    override(org, "limit:agents:hard", 2)
    assert agent(org, "cap_one").status_code == 201 and agent(org, "cap_two").status_code == 201
    assert agent(org, "cap_three").status_code == 403
    org["client"].post("/agents/cap_one/credential/revoke", headers=org["h"])
    assert usage(org)["agents"] == 1
    assert agent(org, "cap_three").status_code == 201
    # Re-issuing a revoked agent's credential reactivates it, which is growth.
    org["client"].post("/agents/cap_two/credential/revoke", headers=org["h"])
    assert agent(org, "cap_four").status_code == 201
    refused = org["client"].post("/agents/cap_one/credential/rotate", headers=org["h"])
    assert refused.status_code == 403 and refused.json()["reason"] == "ENTITLEMENT"
    # Rotating an active agent is not growth.
    assert org["client"].post("/agents/cap_three/credential/rotate", headers=org["h"]).status_code == 200


def test_disabled_integrations_are_free_and_enabling_one_is_growth(org):
    override(org, "limit:integrations:hard", 1)
    assert destination(org, "Pager").status_code == 201
    assert destination(org, "Spare", enabled=False).status_code == 201  # disabled: no capacity used
    assert usage(org)["integrations"] == 1
    assert destination(org, "Spare", enabled=True).status_code == 403    # enabling it is growth
    assert destination(org, "Pager", enabled=False).status_code == 201   # disabling frees the slot
    assert destination(org, "Spare", enabled=True).status_code == 201


# --- Archiving -----------------------------------------------------------------------------------

def test_archiving_an_agent_frees_capacity_and_keeps_its_evidence(org):
    override(org, "limit:agents:hard", 1)
    issued = agent(org, "retiring_agent").json()
    main.submit_tool_request("retiring_agent", "read_file", "notes.txt")
    archived = org["client"].post("/agents/retiring_agent/archive", headers=org["h"],
                                  json={"reason": "Decommissioned with the old pipeline"})
    assert archived.status_code == 200 and archived.json()["capacity"]["agents"] == 0
    assert agent(org, "replacement_agent").status_code == 201
    # The record and its evidence stay; the agent can never come back.
    with pytest.raises(main.AgentAuthenticationError):
        main.authenticate_agent("retiring_agent", issued["credential"], "read_file")
    history = org["client"].get("/agents/retiring_agent/credential-history", headers=org["h"]).json()
    assert "ARCHIVED" in str(history)
    assert "retiring_agent" in org["client"].get("/audit-events", headers=org["h"]).text
    # The console sees the archive state (it hides the credential controls of an archived agent).
    listed = {a["agent_name"]: a for a in org["client"].get("/agents", headers=org["h"]).json()}
    assert listed["retiring_agent"]["identity"]["archived_at"] == archived.json()["archived_at"]
    assert listed["replacement_agent"]["identity"]["archived_at"] is None
    assert org["client"].post("/agents/retiring_agent/credential/rotate", headers=org["h"]).status_code == 409
    assert org["client"].post("/agents/retiring_agent/archive", headers=org["h"],
                              json={"reason": "Archiving it a second time"}).status_code == 409
    events = api.organization_entitlements(org["org_id"], org["operator"])["history"]
    assert any(e["event_type"] == "AGENT_ARCHIVED" and e["detail"]["reason"] == "Decommissioned with the old pipeline" for e in events)


def test_archiving_a_destination_frees_capacity_and_it_can_never_be_reused(org):
    override(org, "limit:integrations:hard", 1)
    created = destination(org, "Old pager").json()
    archived = org["client"].post(f"/integrations/notification/{created['destination_id']}/archive", headers=org["h"],
                                  json={"reason": "Moved to the new on-call tool"})
    assert archived.status_code == 200 and archived.json()["capacity"]["integrations"] == 0
    assert destination(org, "New pager").status_code == 201
    # The archived record stays, disabled; its name cannot be reused or re-enabled.
    reuse = destination(org, "Old pager")
    assert reuse.status_code == 409 and "archived" in reuse.json()["detail"]
    with notification_delivery.sqlite3.connect(notification_delivery.database_path) as connection:
        row = connection.execute("SELECT enabled, archived_at, archive_reason FROM notification_destinations WHERE destination_id = ? AND org_id = ?",
                                 (created["destination_id"], org["org_id"])).fetchone()
    assert row[0] == 0 and row[1] and row[2] == "Moved to the new on-call tool"


def test_every_destination_list_reports_archive_state(install):
    """The console shows archived destinations as ARCHIVED, with no archive control, on all three
    integration pages, so each list must carry archived_at."""
    org = tenant(install, "Archive lists", plan="ENTERPRISE")
    client, h = TestClient(api.app), {"X-Admin-Pin": org["owner"]}
    created = {
        "security_export": client.post("/security-exports/destinations", headers=h, json={
            "name": "SIEM", "destination_type": "SPLUNK", "endpoint": "https://siem.example.com/ingest", "enabled": False,
            "minimization_profile": "STANDARD", "rate_limit_per_minute": 60, "max_attempts": 3}),
        "incident": client.post("/incident-integrations/destinations", headers=h, json={
            "name": "Tickets", "system_type": "JIRA", "endpoint": "https://jira.example.com", "credential_reference": "JIRA_TOKEN",
            "project_or_table": "SEC", "enabled": False}),
        "notification": client.post("/notification-delivery/destinations", headers=h, json={
            "name": "Pager", "channel": "EMAIL", "endpoint_reference": "SECOPS_EMAIL", "enabled": False}),
    }
    lists = {"security_export": "/security-exports", "incident": "/incident-integrations", "notification": "/notification-delivery"}
    for kind, response in created.items():
        assert response.status_code in (200, 201), (kind, response.text)
        destination_id = response.json()["destination_id"]
        archived = client.post(f"/integrations/{kind}/{destination_id}/archive", headers=h,
                               json={"reason": "Retired in the archive-list test"}).json()
        listed = {d["destination_id"]: d for d in client.get(lists[kind], headers=h).json()["destinations"]}
        assert listed[destination_id]["archived_at"] == archived["archived_at"], kind
        assert listed[destination_id]["enabled"] in (False, 0), kind


def test_archiving_is_authorized_tenant_scoped_and_reasoned(org, install):
    agent(org, "guarded_agent")
    pager = destination(org, "Guarded pager").json()
    analyst = join(org["org_id"], "analyst@capacity.example", "SECURITY_ANALYST", "MEMBER")
    auditor = join(org["org_id"], "auditor@capacity.example", "AUDITOR", "MEMBER")
    other = tenant(install, "Elsewhere")
    client = org["client"]
    body = {"reason": "Attempting to archive this record"}
    for token in (analyst, auditor):
        assert client.post("/agents/guarded_agent/archive", headers={"X-Admin-Pin": token}, json=body).status_code == 403
        assert client.post(f"/integrations/notification/{pager['destination_id']}/archive", headers={"X-Admin-Pin": token},
                           json=body).status_code == 403
    # Another org's administrator cannot see or archive them.
    assert client.post("/agents/guarded_agent/archive", headers={"X-Admin-Pin": other["owner"]}, json=body).status_code == 404
    assert client.post(f"/integrations/notification/{pager['destination_id']}/archive", headers={"X-Admin-Pin": other["owner"]},
                       json=body).status_code == 404
    assert client.post("/agents/guarded_agent/archive", headers=org["h"], json={"reason": "short"}).status_code == 422
    assert usage(org) == {**usage(org), "agents": 1, "integrations": 1}


# --- Warnings and the hard limit -----------------------------------------------------------------

def test_soft_limit_warnings_are_returned_by_the_creation_apis(org):
    override(org, "limit:agents:soft", 1)
    override(org, "limit:integrations:soft", 0)
    assert "capacity_warning" not in agent(org, "first_agent").json()
    warned = agent(org, "second_agent").json()
    assert warned["capacity_warning"]["meter"] == "agents" and "2 of 25" in warned["capacity_warning"]["message"]
    assert destination(org, "Pager").json()["capacity_warning"]["meter"] == "integrations"
    assert "agents" in org["client"].get("/entitlements", headers=org["h"]).json()["soft_limits_exceeded"]


def test_a_hard_limit_never_interrupts_existing_security_operations(org):
    override(org, "limit:agents:hard", 1)
    override(org, "limit:integrations:hard", 1)
    issued = agent(org, "working_agent").json()
    export = org["client"].post("/security-exports/destinations", headers=org["h"], json={
        "name": "SIEM", "destination_type": "SPLUNK", "endpoint": "https://siem.example.com/ingest", "enabled": True,
        "minimization_profile": "STANDARD", "rate_limit_per_minute": 60, "max_attempts": 3})
    assert export.status_code == 403  # Foundation lacks SIEM export - growth refused, nothing else
    pager = destination(org, "Pager").json()
    assert agent(org, "one_too_many").status_code == 403 and destination(org, "Another").status_code == 403
    # Enforcement, monitoring, evidence, exports, emergency controls and delivery all continue.
    assert main.authenticate_agent("working_agent", issued["credential"], "read_file")
    assert main.submit_tool_request("working_agent", "read_file", "a.txt")["policy_decision"] == "ALLOW"
    assert org["client"].get("/audit-events", headers=org["h"]).status_code == 200
    assert org["client"].get("/alerts", headers=org["h"]).status_code == 200
    assert org["client"].post(f"/organizations/{org['org_id']}/export", headers=org["h"]).status_code == 200
    assert org["client"].put("/policy-emergency-controls", headers=org["h"], json={"global_deny": True}).status_code == 200
    assert destination(org, "Pager", enabled=True).status_code == 201  # updating an existing destination
    # Security delivery to an existing destination still goes out at the hard limit.
    queued = notification_delivery.queue_notification(
        pager["destination_id"], {"event_type": "ALERT", "severity": "CRITICAL", "title": "Limit reached", "summary": "test"},
        org_id=org["org_id"])
    sent = []
    notification_delivery.process_deliveries(lambda *args, **kwargs: sent.append(args))
    assert queued and sent


# --- Plans ---------------------------------------------------------------------------------------

def test_transitional_is_never_assignable_and_dedicated_needs_a_contract(org):
    operator = {"X-Admin-Pin": org["operator"]}
    client = org["client"]
    assert client.put(f"/entitlements/{org['org_id']}", headers=operator, json={"plan": "TRANSITIONAL"}).status_code == 422
    with pytest.raises(ValueError, match="cannot be assigned"):
        entitlements.assign_plan(org["org_id"], "TRANSITIONAL", "ACTIVE", "test")
    assert client.put(f"/entitlements/{org['org_id']}", headers=operator, json={"plan": "DEDICATED"}).status_code == 400
    bad = client.put(f"/entitlements/{org['org_id']}", headers=operator, json={
        "plan": "DEDICATED", "contract_limits": {"agents": {"soft": 50, "hard": 10}, "integrations": {"soft": 1, "hard": 2}}})
    assert bad.status_code == 400
    good = client.put(f"/entitlements/{org['org_id']}", headers=operator, json={
        "plan": "DEDICATED", "contract_limits": {"agents": {"soft": 400, "hard": 500}, "integrations": {"soft": 40, "hard": 60}}})
    assert good.status_code == 200
    limits = good.json()["limits"]
    assert limits["agents"] == {"soft": 400, "hard": 500} and limits["integrations"] == {"soft": 40, "hard": 60}
    assert client.put(f"/entitlements/{org['org_id']}", headers=operator, json={
        "plan": "ENTERPRISE", "contract_limits": {"agents": {"soft": 1, "hard": 2}, "integrations": {"soft": 1, "hard": 2}}}).status_code == 400
    # Operators keep reasoned, expiring, audited overrides on top of the contract.
    override(org, "limit:agents:hard", 501)
    assert client.get("/entitlements", headers=org["h"]).json()["limits"]["agents"]["hard"] == 501
    assert client.put(f"/entitlements/{org['org_id']}", headers={"X-Admin-Pin": org["owner"]}, json={
        "plan": "DEDICATED", "contract_limits": {"agents": {"soft": 1, "hard": 9999}, "integrations": {"soft": 1, "hard": 9999}}}).status_code == 403


def test_a_new_org_after_migration_starts_without_capacity(install):
    org = tenant(install, "Brand New", plan=None)
    current = entitlements.get_entitlements(org["org_id"], meters=())
    assert current["plan"] == "UNASSIGNED" and current["plan_required"] and current["limits"]["agents"] == {"soft": 0, "hard": 0}


# --- Migration -----------------------------------------------------------------------------------

def _legacy_install(path):
    """An install from before D6: orgs and agents, no plans, no marks, no archive columns."""
    with raw_sqlite.connect(path) as connection:
        connection.execute("CREATE TABLE organizations (org_id TEXT PRIMARY KEY, name TEXT, slug TEXT, status TEXT, created_at TEXT)")
        connection.executemany("INSERT INTO organizations VALUES (?, ?, ?, 'ACTIVE', 'now')",
                               [("org_default", "Default", "default"), ("org_old", "Old Co", "old-co")])
        connection.execute("CREATE TABLE agent_identities (agent_name TEXT PRIMARY KEY, credential_salt TEXT, credential_hash TEXT,"
                           " scopes_json TEXT, credential_status TEXT DEFAULT 'ACTIVE', created_at TEXT, rotated_at TEXT,"
                           " revoked_at TEXT, org_id TEXT NOT NULL DEFAULT 'org_default')")
        connection.execute("INSERT INTO agent_identities (agent_name, credential_salt, credential_hash, scopes_json, created_at, org_id)"
                           " VALUES ('old_agent', 's', 'h', '[]', 'now', 'org_old')")


def test_migration_preserves_existing_orgs_explicitly_once(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    _legacy_install(path)
    for module in (database, entitlements, organizations):
        monkeypatch.setattr(module, "database_path", path)
    database.initialize_database()
    entitlements.initialize_entitlements()
    for org_id in ("org_default", "org_old"):
        assignment = entitlements.get_entitlements(org_id, meters=())
        assert assignment["plan"] == "TRANSITIONAL" and assignment["transitional"] and assignment["features"]
    assert entitlements.entitlement_history("org_old")[0]["actor"] == "migration:d6"
    # The existing agent keeps counting as usage, and its org can keep growing until a plan is chosen.
    assert entitlements.require_capacity("org_old", "agents")["usage"] == 2
    # The migration never runs again: an org created afterwards needs a plan.
    with raw_sqlite.connect(path) as connection:
        connection.execute("INSERT INTO organizations VALUES ('org_new', 'New', 'new', 'ACTIVE', 'now')")
    entitlements.initialize_entitlements()
    assert entitlements.get_entitlements("org_new", meters=())["plan"] == "UNASSIGNED"


def test_a_fresh_install_has_nothing_to_preserve(tmp_path, monkeypatch):
    path = tmp_path / "fresh.db"
    for module in (database, entitlements, organizations, admin_auth):
        monkeypatch.setattr(module, "database_path", path)
    organizations.initialize_organizations()
    database.initialize_database()
    entitlements.initialize_entitlements()
    assert entitlements.get_entitlements(organizations.DEFAULT_ORG_ID, meters=())["plan"] == "UNASSIGNED"
