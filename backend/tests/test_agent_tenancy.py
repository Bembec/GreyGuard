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

from backend.app import admin_auth, alerts, api, database, main, notifications, organizations

PASSWORD = "SecureDemo!123"


@pytest.fixture()
def tenants(tmp_path, monkeypatch):
    path = tmp_path / "tenancy.db"
    for module in (admin_auth, organizations, database, alerts, notifications):
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


# --- P2.2 agent scoping, batch B: agent evidence (tool requests, approvals, executions, audit) --

def list_requests(token):
    # Route functions called directly: pass every Query parameter explicitly.
    return api.list_tool_requests(agent_name=None, approval_status=None, execution_status=None, limit=50, x_admin_pin=token)


def submit(agent, action="write_note"):
    # write_note is ASK by default, so the request waits for an administrator's approval.
    return main.submit_tool_request(agent, action, "note.txt", {"content": "x"})


def test_tool_requests_and_their_evidence_belong_to_the_agents_org(tenants):
    register(tenants["theirs"], "theirs_agent")
    pending = submit("theirs_agent")
    assert pending["org_id"] == tenants["other_org"] and pending["approval_status"] == "PENDING"
    assert [r["request_id"] for r in list_requests(tenants["theirs"])["requests"]] == [pending["request_id"]]
    assert list_requests(tenants["ours"])["requests"] == []


def test_another_orgs_admin_cannot_approve_a_pending_request(tenants):
    register(tenants["theirs"], "theirs_agent")
    pending = submit("theirs_agent")
    with pytest.raises(HTTPException) as error:
        api.review_tool_request(pending["request_id"], api.ToolApprovalDecision(decision="APPROVED"), tenants["ours"])
    assert error.value.status_code == 404
    assert database.get_tool_request(pending["request_id"], org_id=tenants["other_org"])["approval_status"] == "PENDING"
    # The owning org's decision is recorded, with its approval evidence in the same org.
    decided = api.review_tool_request(pending["request_id"], api.ToolApprovalDecision(decision="DENIED"), tenants["theirs"])
    assert decided["approval_status"] == "DENIED"
    assert [e["org_id"] for e in decided["approval_events"]] == [tenants["other_org"]]


def test_the_evidence_timeline_is_scoped_and_every_event_names_its_org(tenants):
    register(tenants["ours"], "ours_agent")
    register(tenants["theirs"], "theirs_agent")
    submit("ours_agent", "read_file")
    submit("theirs_agent", "read_file")
    ours = database.get_administrator_audit_events(limit=500, org_id=organizations.DEFAULT_ORG_ID)["events"]
    theirs = database.get_administrator_audit_events(limit=500, org_id=tenants["other_org"])["events"]
    assert ours and {e["agent_name"] for e in ours} == {"ours_agent"}
    assert {e["org_id"] for e in ours} == {organizations.DEFAULT_ORG_ID}
    assert theirs and {e["agent_name"] for e in theirs} == {"theirs_agent"}
    every = database.get_administrator_audit_events(limit=500, org_id=database.ALL_ORGS)["events"]
    assert {e["agent_name"] for e in every} >= {"ours_agent", "theirs_agent"}
    # The administrator-facing route uses the caller's own org.
    routed = api.administrator_audit_events(event_type=None, agent_name=None, limit=500, x_admin_pin=tenants["theirs"])["events"]
    assert {e["agent_name"] for e in routed} == {"theirs_agent"}


def test_an_orgs_compliance_evidence_excludes_other_orgs_agents(tenants):
    from backend.app import compliance_reports
    register(tenants["ours"], "ours_agent")
    register(tenants["theirs"], "theirs_agent")
    submit("ours_agent", "read_file")
    submit("theirs_agent", "read_file")
    evidence = compliance_reports.build_evidence({}, tenants["other_org"])
    assert {e["agent_name"] for e in evidence["audit_events"]} == {"theirs_agent"}


def test_an_agent_reads_its_own_request_and_cannot_probe_another_orgs(tenants):
    from fastapi.testclient import TestClient
    ours = register(tenants["ours"], "ours_agent")
    theirs = register(tenants["theirs"], "theirs_agent")
    their_request = submit("theirs_agent", "read_file")
    client = TestClient(api.app, raise_server_exceptions=False)
    own = client.get(f"/tool-requests/{their_request['request_id']}",
                     headers={"X-Agent-Name": "theirs_agent", "X-Agent-Key": theirs["credential"]})
    # Before batch B this route failed with a 500 for every existing request.
    assert own.status_code == 200 and own.json()["request_id"] == their_request["request_id"]
    probe = client.get(f"/tool-requests/{their_request['request_id']}",
                       headers={"X-Agent-Name": "ours_agent", "X-Agent-Key": ours["credential"]})
    assert probe.status_code == 404
    unauthenticated = client.get(f"/tool-requests/{their_request['request_id']}",
                                 headers={"X-Agent-Name": "theirs_agent", "X-Agent-Key": "gg_wrong"})
    assert unauthenticated.status_code == 401


def test_legacy_agent_evidence_is_backfilled_to_the_default_org(tmp_path, monkeypatch):
    path = tmp_path / "legacy-evidence.db"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE tool_requests (request_id TEXT PRIMARY KEY, agent_name TEXT NOT NULL,
            timestamp TEXT NOT NULL, updated_at TEXT NOT NULL, action TEXT NOT NULL, target TEXT,
            payload_json TEXT NOT NULL, dry_run INTEGER NOT NULL DEFAULT 0, policy_decision TEXT NOT NULL,
            approval_status TEXT NOT NULL, execution_status TEXT NOT NULL, risk_added INTEGER NOT NULL,
            risk_score INTEGER NOT NULL, result_json TEXT, executed_at TEXT)""")
        connection.execute("""CREATE TABLE approval_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL, timestamp TEXT NOT NULL, actor TEXT NOT NULL, decision TEXT NOT NULL,
            note TEXT, FOREIGN KEY (request_id) REFERENCES tool_requests(request_id))""")
        connection.execute("INSERT INTO tool_requests VALUES('req_legacy','legacy_bot','2026-01-01','2026-01-01',"
                           "'write_note','n','{}',0,'ASK','APPROVED','SUCCEEDED',10,10,NULL,NULL)")
        connection.execute("INSERT INTO approval_events(request_id,timestamp,actor,decision) VALUES('req_legacy','2026-01-01','owner','APPROVED')")
    monkeypatch.setattr(database, "database_path", path)
    database.initialize_database()
    details = database.get_tool_request_details("req_legacy", org_id="org_default")
    assert details["org_id"] == "org_default" and [e["org_id"] for e in details["approval_events"]] == ["org_default"]
    assert database.get_tool_request_details("req_legacy", org_id="org_other") is None



# --- P2.2 agent scoping, batch C: alerts, alert notes, notifications, notification retention ----

def alert_list(token):
    return api.administrator_alerts(status=None, severity=None, agent_name=None, limit=100, x_admin_pin=token)["alerts"]


def inbox(token):
    return api.administrator_notifications(unread_only=False, severity=None, limit=100, x_admin_pin=token)["notifications"]


def blocked_activity(tenants):
    # send_email is BLOCK by default policy: HIGH-severity evidence, so it raises an alert.
    register(tenants["ours"], "ours_agent")
    register(tenants["theirs"], "theirs_agent")
    submit("ours_agent", "send_email")
    submit("theirs_agent", "send_email")


def test_alerts_belong_to_the_org_of_their_evidence(tenants):
    blocked_activity(tenants)
    ours, theirs = alert_list(tenants["ours"]), alert_list(tenants["theirs"])
    assert ours and {a["agent_name"] for a in ours} == {"ours_agent"}
    assert {a["org_id"] for a in ours} == {organizations.DEFAULT_ORG_ID}
    assert theirs and {a["agent_name"] for a in theirs} == {"theirs_agent"}
    summary = api.administrator_alert_summary(tenants["theirs"])
    assert summary["total"] == len(theirs)


def test_another_orgs_alert_cannot_be_read_updated_or_annotated(tenants):
    blocked_activity(tenants)
    their_alert = alert_list(tenants["theirs"])[0]
    token = tenants["ours"]
    assert not_found(lambda: api.administrator_alert(their_alert["alert_id"], token))
    assert not_found(lambda: api.administrator_update_alert(
        their_alert["alert_id"], api.AlertUpdateRequest(status="DISMISSED", note="not ours"), token))
    assert not_found(lambda: api.administrator_add_alert_note(
        their_alert["alert_id"], api.AlertNoteRequest(note="probe"), token))
    untouched = api.administrator_alert(their_alert["alert_id"], tenants["theirs"])
    assert untouched["status"] == "OPEN" and untouched["notes"] == []
    noted = api.administrator_add_alert_note(their_alert["alert_id"], api.AlertNoteRequest(note="triage"), tenants["theirs"])
    assert noted["note"] == "triage"
    assert [n["note"] for n in api.administrator_alert(their_alert["alert_id"], tenants["theirs"])["notes"]] == ["triage"]


def test_install_level_alerts_are_visible_only_to_install_operators(tenants):
    # Repeated failures against an agent name that exists in no org belong to no tenant.
    main.record_authentication_event(claimed_agent_name="ghost_agent", authenticated_agent_name=None,
                                     action="read_file", outcome="AUTHENTICATION_FAILED", reason="Unknown agent.")
    operator = admin_auth.create_administrator("op@greyguard.local", "Op", "PLATFORM_ADMIN", PASSWORD, install_operator=True)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, operator["admin_id"], "PLATFORM_ADMIN", "OWNER")
    operator_token = admin_auth.authenticate(operator["email"], PASSWORD)["access_token"]
    ghost_alerts = [a for a in alert_list(operator_token) if a["agent_name"] == "ghost_agent"]
    assert ghost_alerts and ghost_alerts[0]["org_id"] is None
    assert "ghost_agent" not in {a["agent_name"] for a in alert_list(tenants["ours"])}
    assert "ghost_agent" not in {a["agent_name"] for a in alert_list(tenants["theirs"])}
    # The operator's inbox carries the install-level notification too; a tenant's does not.
    assert any(n["org_id"] is None for n in inbox(operator_token))
    assert all(n["org_id"] == organizations.DEFAULT_ORG_ID for n in inbox(tenants["ours"]))


def test_notifications_and_retention_are_per_org(tenants):
    blocked_activity(tenants)
    ours, theirs = inbox(tenants["ours"]), inbox(tenants["theirs"])
    assert ours and {n["org_id"] for n in ours} == {organizations.DEFAULT_ORG_ID}
    assert theirs and {n["org_id"] for n in theirs} == {tenants["other_org"]}
    # Age every notification, then apply only the other org's (shortest) policy.
    with sqlite3.connect(database.database_path) as connection:
        connection.execute("UPDATE security_notifications SET created_at = '2020-01-01T00:00:00+00:00'")
    api.administrator_update_notification_retention(api.NotificationRetentionUpdate(retention_days=7), tenants["theirs"])
    assert api.administrator_cleanup_notifications(tenants["theirs"])["deleted"] == len(theirs)
    with sqlite3.connect(database.database_path) as connection:
        remaining = {row[0] for row in connection.execute("SELECT DISTINCT org_id FROM security_notifications")}
    assert remaining == {organizations.DEFAULT_ORG_ID}
    assert api.administrator_notification_retention(tenants["ours"])["policy"]["retention_days"] == notifications.DEFAULT_RETENTION_DAYS
    assert api.administrator_notification_retention(tenants["theirs"])["policy"]["retention_days"] == 7
    assert api.administrator_notification_retention(tenants["ours"])["history"] == []


def test_legacy_retention_singleton_and_alerts_move_to_the_default_org(tmp_path, monkeypatch):
    path = tmp_path / "legacy-alerts.db"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE notification_retention_policy (id INTEGER PRIMARY KEY CHECK (id = 1),
            retention_days INTEGER NOT NULL, updated_at TEXT NOT NULL, updated_by TEXT NOT NULL)""")
        connection.execute("INSERT INTO notification_retention_policy VALUES(1, 30, '2026-01-01', 'owner')")
        connection.execute("""CREATE TABLE security_alerts (alert_id TEXT PRIMARY KEY, source_event_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, agent_name TEXT, request_id TEXT, event_type TEXT NOT NULL,
            action TEXT, outcome TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN', title TEXT NOT NULL,
            summary TEXT NOT NULL, assigned_to TEXT, resolution_note TEXT, evidence_json TEXT NOT NULL)""")
        connection.execute("INSERT INTO security_alerts(alert_id,source_event_id,created_at,updated_at,event_type,outcome,severity,title,summary,evidence_json)"
                           " VALUES('alr_legacy','policy-1','2026-01-01','2026-01-01','POLICY','BLOCK','HIGH','t','s','{}')")
    for module in (alerts, notifications):
        monkeypatch.setattr(module, "database_path", path)
    alerts.initialize_alert_database()
    notifications.initialize_notification_database()
    assert notifications.get_retention_policy("org_default")["retention_days"] == 30
    assert notifications.get_retention_policy("org_other")["retention_days"] == notifications.DEFAULT_RETENTION_DAYS
    assert alerts.get_alert("alr_legacy", org_id="org_default")["org_id"] == "org_default"
    assert alerts.get_alert("alr_legacy", org_id="org_other") is None
