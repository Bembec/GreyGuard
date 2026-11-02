"""P7.5 item 5, step 3: containment from an incident, and the exportable incident package.

Owner decisions, 2026-10-16: containment from the workspace uses the same guard as each action's own
route, a typed confirmation and a recorded reason; auditors may export packages, and every export is
recorded. Negative authorization and tenant-isolation tests throughout.
"""
import hashlib
import json

import pytest

from backend.app import admin_auth, api, database, db_compat, decision_provenance, incident_workspace, main, organizations, policy_control
from backend.tests.test_agent_tenancy import PASSWORD, register, submit, tenants  # noqa: F401  (fixture)
from backend.tests.test_control_graph import database_fingerprint, make_auditor, warmed_client, world  # noqa: F401  (fixture)
from backend.tests.test_incident_workspace import blocked_incident, derive, events


def person(world, role, email):
    created = admin_auth.create_administrator(email, role.title(), role, PASSWORD)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, created["admin_id"], role, "MEMBER")
    return admin_auth.authenticate(email, PASSWORD)["access_token"]


def act(token, alert_id, action, confirm, reason="contain the agent now"):
    client = warmed_client({"X-Admin-Pin": token})
    return client.post(f"/incidents/{alert_id}/actions", headers={"X-Admin-Pin": token},
                       json={"action": action, "reason": reason, "confirm": confirm})


def containment(alert_id):
    return [event for event in events(alert_id) if event["event_type"] == "CONTAINMENT"]


# --- Permission mapping ----------------------------------------------------------------------------

def test_the_permission_layer_maps_the_new_routes_explicitly():
    assert admin_auth.required_permission("POST", "/incidents/a1/package") == "read"
    assert admin_auth.required_permission("POST", "/incidents/a1/actions") == "incident:manage"
    assert admin_auth.required_permission("POST", "/incidents/a1/anything-else") == "admin:manage"
    assert api.OFFBOARDING_ALLOWED.match("/incidents/a1/actions") and api.OFFBOARDING_ALLOWED.match("/incidents/a1/package")
    assert not api.OFFBOARDING_ALLOWED.match("/incidents/a1/other")


# --- Containment -----------------------------------------------------------------------------------

def test_an_admin_revokes_the_agents_credential_with_confirmation_and_reason(world):
    alert, _ = blocked_incident(world["ours"])
    response = act(world["ours"], alert["alert_id"], "revoke_credential", "ours_agent")
    assert response.status_code == 200, response.text
    assert main.get_public_agent_identity("ours_agent")["credential_status"] == "REVOKED"
    [event] = containment(alert["alert_id"])
    assert event["actor"] == "ours@greyguard.local"
    assert event["detail"] == {"action": "revoke_credential", "target": "ours_agent", "reason": "contain the agent now",
                               "summary": "revoked the credential of ours_agent"}


@pytest.mark.parametrize("action, confirm, check", [
    ("disable_agent", "ours_agent", lambda controls: "ours_agent" in controls["disabled_agents"]),
    ("disable_tool", "send_email", lambda controls: "send_email" in controls["disabled_tools"]),
])
def test_an_admin_emergency_disables_the_agent_or_the_tool(world, action, confirm, check):
    alert, _ = blocked_incident(world["ours"])
    assert act(world["ours"], alert["alert_id"], action, confirm).status_code == 200
    assert check(policy_control.get_emergency_controls(org_id=organizations.DEFAULT_ORG_ID))
    assert containment(alert["alert_id"])[0]["detail"]["target"] == confirm


def test_terminating_isolation_needs_the_word_terminate(world, monkeypatch):
    from backend.app import execution_isolation
    calls = []
    monkeypatch.setattr(execution_isolation, "emergency_terminate", lambda actor, org_id: calls.append(org_id) or {"terminated": 0})
    alert, _ = blocked_incident(world["ours"])
    assert act(world["ours"], alert["alert_id"], "terminate_isolation", "terminate").status_code == 400
    assert calls == []
    assert act(world["ours"], alert["alert_id"], "terminate_isolation", "TERMINATE").status_code == 200
    assert calls == [organizations.DEFAULT_ORG_ID]


@pytest.mark.parametrize("confirm, reason", [("someone_else", "a good reason"), ("ours_agent", "no"), ("", "a good reason")])
def test_a_wrong_confirmation_or_missing_reason_changes_nothing(world, confirm, reason):
    alert, _ = blocked_incident(world["ours"])
    response = act(world["ours"], alert["alert_id"], "revoke_credential", confirm, reason)
    assert response.status_code in (400, 422)
    assert main.get_public_agent_identity("ours_agent")["credential_status"] == "ACTIVE"
    assert containment(alert["alert_id"]) == []


def test_a_security_analyst_gets_exactly_the_guards_of_the_original_routes(world):
    alert, _ = blocked_incident(world["ours"])
    analyst = person(world, "SECURITY_ANALYST", "analyst@greyguard.local")
    for action, confirm in (("revoke_credential", "ours_agent"), ("disable_agent", "ours_agent"), ("disable_tool", "send_email")):
        response = act(analyst, alert["alert_id"], action, confirm)
        assert response.status_code == 403 and response.json()["detail"].startswith("Your role, Security Analyst,")
    assert main.get_public_agent_identity("ours_agent")["credential_status"] == "ACTIVE"
    assert containment(alert["alert_id"]) == []
    # The same person on the original routes is refused the same way.
    client = warmed_client({"X-Admin-Pin": analyst})
    assert client.post("/agents/ours_agent/credential/revoke", headers={"X-Admin-Pin": analyst}).status_code == 403


def test_an_auditor_cannot_contain_and_nothing_changes(world):
    alert, _ = blocked_incident(world["ours"])
    auditor = make_auditor()
    warmed_client({"X-Admin-Pin": auditor})  # one-time pipeline setup on a fresh database is not the call under test
    before = database_fingerprint()
    for action, confirm in (("revoke_credential", "ours_agent"), ("disable_agent", "ours_agent"), ("terminate_isolation", "TERMINATE")):
        assert act(auditor, alert["alert_id"], action, confirm).status_code == 403
    assert database_fingerprint() == before


def test_another_orgs_incident_cannot_be_acted_on(world):
    register(world["theirs"], "theirs_agent")
    submit("theirs_agent", "send_email")
    theirs = derive(world["theirs"])[0]
    response = act(world["ours"], theirs["alert_id"], "revoke_credential", "theirs_agent")
    assert response.status_code == 404
    assert main.get_public_agent_identity("theirs_agent")["credential_status"] == "ACTIVE"
    assert events(theirs["alert_id"], world["other_org"]) == []


def test_an_incident_naming_another_orgs_agent_never_acts_on_it(world):
    """Defence in depth: even if an incident in our org named another org's agent, nothing crosses."""
    register(world["theirs"], "theirs_agent")
    alert, _ = blocked_incident(world["ours"])
    with db_compat.connect(database.database_path) as connection:
        connection.execute("UPDATE security_alerts SET agent_name = ? WHERE alert_id = ? AND org_id = ?",
                           ("theirs_agent", alert["alert_id"], organizations.DEFAULT_ORG_ID))
    for action in ("revoke_credential", "disable_agent"):
        assert act(world["ours"], alert["alert_id"], action, "theirs_agent").status_code == 404
    assert main.get_public_agent_identity("theirs_agent")["credential_status"] == "ACTIVE"
    assert "theirs_agent" not in policy_control.get_emergency_controls(org_id=world["other_org"])["disabled_agents"]
    assert "theirs_agent" not in policy_control.get_emergency_controls(org_id=organizations.DEFAULT_ORG_ID)["disabled_agents"]
    assert containment(alert["alert_id"]) == []


def test_containment_is_not_offered_for_install_level_incidents(world):
    main.record_authentication_event(claimed_agent_name="ghost_agent", authenticated_agent_name=None, action="read_file",
                                     outcome="AUTHENTICATION_FAILED", reason="Unknown agent.")
    operator = admin_auth.create_administrator("op@greyguard.local", "Op", "PLATFORM_ADMIN", PASSWORD, install_operator=True)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, operator["admin_id"], "PLATFORM_ADMIN", "OWNER")
    token = admin_auth.authenticate(operator["email"], PASSWORD)["access_token"]
    ghost = next(item for item in derive(token) if item["agent_name"] == "ghost_agent")
    response = act(token, ghost["alert_id"], "disable_agent", "ghost_agent")
    assert response.status_code == 400 and "install-level" in response.json()["detail"]


def test_the_workspace_lists_containment_with_role_only_reasons(world):
    alert, _ = blocked_incident(world["ours"])
    admin = {a["id"]: a for a in api.incident_workspace_view(alert["alert_id"], x_admin_pin=world["ours"])["actions"]["others"]}
    assert all(admin[name]["available"] for name in ("revoke_credential", "disable_agent", "disable_tool", "terminate_isolation", "export"))
    assert admin["revoke_credential"]["confirm_text"] == "ours_agent"
    analyst = {a["id"]: a for a in api.incident_workspace_view(
        alert["alert_id"], x_admin_pin=person(world, "SECURITY_ANALYST", "analyst2@greyguard.local"))["actions"]["others"]}
    assert analyst["revoke_credential"]["unavailable_reason"] == "Your role, Security Analyst, cannot do this: it needs identity management rights."
    assert analyst["export"]["available"] is True


# --- The incident package ------------------------------------------------------------------------------

def export(token, alert_id):
    client = warmed_client({"X-Admin-Pin": token})
    return client.post(f"/incidents/{alert_id}/package", headers={"X-Admin-Pin": token})


def test_an_admin_and_an_auditor_can_export_and_each_export_is_recorded(world):
    alert, request = blocked_incident(world["ours"])
    for token, email in ((world["ours"], "ours@greyguard.local"), (make_auditor(), "auditor@greyguard.local")):
        response = export(token, alert["alert_id"])
        assert response.status_code == 200, response.text
        package = response.json()
        assert package["format"] == "greyguard.incident-package/1" and package["exported_by"] == email
        assert package["parts"]["decision_records"][0]["request_id"] == request["request_id"]
        assert "candidates" not in package["parts"]["owner"]
    exported = [event for event in events(alert["alert_id"]) if event["event_type"] == "EXPORTED"]
    assert [event["actor"] for event in exported] == ["ours@greyguard.local", "auditor@greyguard.local"]


def test_the_package_manifest_verifies_every_part(world):
    alert, _ = blocked_incident(world["ours"])
    package = export(world["ours"], alert["alert_id"]).json()
    canonical = lambda value: json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)  # noqa: E731
    for name, part in package["parts"].items():
        assert hashlib.sha256(canonical(part).encode()).hexdigest() == package["manifest"]["parts"][name], name
    assert hashlib.sha256(canonical(package["manifest"]["parts"]).encode()).hexdigest() == package["manifest"]["package"]
    exported = [event for event in events(alert["alert_id"]) if event["event_type"] == "EXPORTED"]
    assert exported[0]["detail"] == {"package_sha256": package["manifest"]["package"]}


def test_another_orgs_incident_cannot_be_exported(world):
    register(world["theirs"], "theirs_agent")
    submit("theirs_agent", "send_email")
    theirs = derive(world["theirs"])[0]
    assert export(world["ours"], theirs["alert_id"]).status_code == 404
    assert events(theirs["alert_id"], world["other_org"]) == []


def test_the_package_holds_redacted_evidence_only(world):
    register(world["ours"], "ours_agent")
    main.submit_tool_request("ours_agent", "send_email", "ops@example.com", {"body": "token sk-abcdefghijklmnopqrstuvwx"})
    alert = next(item for item in derive(world["ours"]) if item["request_id"])
    text = export(world["ours"], alert["alert_id"]).text
    assert "sk-abcdefghijklmnopqrstuvwx" not in text
