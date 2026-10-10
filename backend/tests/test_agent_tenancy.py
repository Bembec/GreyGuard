"""P2.2 agent scoping, batch A: every agent belongs to one org, and administrators can only see or
manage their own org's agents.

Agent names stay a global namespace (agents authenticate by name before any org is known), so
ownership is checked explicitly. Before this batch, rotate/revoke/scopes looked agents up by
name alone: one org's PLATFORM_ADMIN could rotate another org's agent credential and receive the
new credential - a cross-tenant agent takeover.
"""
import hashlib
import sqlite3

import pytest
from fastapi import HTTPException

from backend.app import admin_auth, api, database, main, organizations

PASSWORD = "SecureDemo!123"


@pytest.fixture()
def tenants(tmp_path, monkeypatch):
    path = tmp_path / "tenancy.db"
    for module in (admin_auth, organizations, database):
        monkeypatch.setattr(module, "database_path", path)
    monkeypatch.setattr(main, "state_path", tmp_path / "state.json")
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_PASSWORD", raising=False)
    main.initialize_greyguard()
    admin_auth.initialize_admin_auth()
    organizations.initialize_organizations()

    ours = admin_auth.create_administrator("ours@greyguard.local", "Ours", "PLATFORM_ADMIN", PASSWORD)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, ours["admin_id"], "PLATFORM_ADMIN", "OWNER")
    theirs = admin_auth.create_administrator("theirs@greyguard.local", "Theirs", "PLATFORM_ADMIN", PASSWORD)
    other_org = organizations.create_organization("Other", theirs["admin_id"])
    theirs_token = admin_auth.authenticate(theirs["email"], PASSWORD)["access_token"]
    organizations.switch_active_org(theirs["admin_id"], other_org["org_id"],
                                    hashlib.sha256(theirs_token.encode()).hexdigest())
    return {
        "ours": admin_auth.authenticate(ours["email"], PASSWORD)["access_token"],
        "theirs": theirs_token,
        "other_org": other_org["org_id"],
    }


def register(token, name):
    return api.register_agent_identity(api.AgentRegistration(agent_name=name, scopes=["read_file"]), token)


def not_found(call):
    with pytest.raises(HTTPException) as error:
        call()
    return error.value.status_code == 404


def test_an_agent_is_registered_into_the_registering_administrators_org(tenants):
    register(tenants["ours"], "ours_agent")
    register(tenants["theirs"], "theirs_agent")
    assert main.agent_org_id("ours_agent") == organizations.DEFAULT_ORG_ID
    assert main.agent_org_id("theirs_agent") == tenants["other_org"]
    ours = {agent["agent_name"] for agent in api.list_agents(tenants["ours"])}
    theirs = {agent["agent_name"] for agent in api.list_agents(tenants["theirs"])}
    assert "ours_agent" in ours and "theirs_agent" not in ours
    assert theirs == {"theirs_agent"}


def test_another_orgs_admin_cannot_take_over_an_agent_by_rotating_its_credential(tenants):
    issued = register(tenants["ours"], "ours_agent")
    assert not_found(lambda: api.rotate_credential("ours_agent", tenants["theirs"]))
    # The original credential still authenticates: nothing was rotated.
    assert main.authenticate_agent("ours_agent", issued["credential"], "read_file")["agent_name"] == "ours_agent"


@pytest.mark.parametrize("route", [
    "get", "scopes", "revoke", "credential history", "authentication events", "reset", "investigation",
])
def test_every_admin_agent_route_treats_another_orgs_agent_as_missing(tenants, route):
    register(tenants["ours"], "ours_agent")
    token = tenants["theirs"]
    calls = {
        "get": lambda: api.get_agent("ours_agent", token),
        "scopes": lambda: api.update_agent_scopes("ours_agent", api.ScopeUpdate(scopes=["delete_file"]), token),
        "revoke": lambda: api.revoke_credential("ours_agent", token),
        "credential history": lambda: api.agent_credential_history("ours_agent", limit=20, offset=0, x_admin_pin=token),
        "authentication events": lambda: api.authentication_events("ours_agent", limit=20, x_admin_pin=token),
        "reset": lambda: api.reset_agent("ours_agent", token),
        "investigation": lambda: api.agent_investigation("ours_agent", limit=100, x_admin_pin=token),
    }
    assert not_found(calls[route])
    identity = main.get_public_agent_identity("ours_agent")
    assert identity["scopes"] == ["read_file"] and identity["credential_status"] == "ACTIVE"


def test_the_owning_org_still_manages_its_agent(tenants):
    register(tenants["ours"], "ours_agent")
    token = tenants["ours"]
    assert api.get_agent("ours_agent", token)["agent_name"] == "ours_agent"
    assert api.update_agent_scopes("ours_agent", api.ScopeUpdate(scopes=["list_files"]), token)["updated"]
    assert api.rotate_credential("ours_agent", token)["credential"]
    history = api.agent_credential_history("ours_agent", limit=20, offset=0, x_admin_pin=token)
    assert [event["event_type"] for event in history["events"]] == ["ROTATED", "ISSUED"]


def test_names_are_a_global_namespace_without_revealing_the_owner(tenants):
    register(tenants["ours"], "shared_name")
    with pytest.raises(HTTPException) as error:
        register(tenants["theirs"], "shared_name")
    assert error.value.status_code == 400 and "unavailable" in error.value.detail
    assert "exists" not in error.value.detail


def test_pre_org_agent_states_belong_to_the_default_org(tenants):
    # default_agent is the identity-less runtime state every install starts with.
    assert "default_agent" in main.agent_states
    assert main.agent_org_id("default_agent") == organizations.DEFAULT_ORG_ID
    with pytest.raises(HTTPException) as error:
        register(tenants["theirs"], "default_agent")
    assert "unavailable" in error.value.detail
    assert "default_agent" not in {agent["agent_name"] for agent in api.list_agents(tenants["theirs"])}


def test_credential_history_is_recorded_under_the_agents_org(tenants):
    register(tenants["theirs"], "theirs_agent")
    with sqlite3.connect(database.database_path) as connection:
        rows = connection.execute("SELECT org_id FROM agent_credential_events WHERE agent_name='theirs_agent'").fetchall()
    assert rows == [(tenants["other_org"],)]


def test_legacy_identities_are_backfilled_to_the_default_org(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE agent_identities (agent_name TEXT PRIMARY KEY,
            credential_salt TEXT NOT NULL, credential_hash TEXT NOT NULL, scopes_json TEXT NOT NULL,
            credential_status TEXT NOT NULL DEFAULT 'ACTIVE', created_at TEXT NOT NULL,
            rotated_at TEXT, revoked_at TEXT)""")
        connection.execute("""CREATE TABLE agent_credential_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL, timestamp TEXT NOT NULL, event_type TEXT NOT NULL, actor TEXT NOT NULL)""")
        connection.execute("INSERT INTO agent_identities VALUES('legacy_bot','00','00','[]','ACTIVE','2026-01-01',NULL,NULL)")
        connection.execute("INSERT INTO agent_credential_events(agent_name,timestamp,event_type,actor) VALUES('legacy_bot','2026-01-01','ISSUED','owner')")
    monkeypatch.setattr(database, "database_path", path)
    database.initialize_database()
    assert database.get_agent_identity("legacy_bot")["org_id"] == "org_default"
    assert database.get_credential_history("legacy_bot", org_id="org_default")["total"] == 1
    assert database.get_credential_history("legacy_bot", org_id="org_other")["total"] == 0
