"""P7.5 item 5: the investigation workspace (step 2: the full action record and the read view).

Holds the code to the approved design: same visibility as /alerts/{id}; everything read under the
incident's org; read-only; every status change, assignment and note recorded append-only; actions
the viewer may not take explained from their own role only; sections that fail on their own.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend.app import admin_auth, api, database, db_compat, incident_workspace, main, organizations
from backend.tests.test_agent_tenancy import PASSWORD, register, submit, tenants  # noqa: F401  (fixture)
from backend.tests.test_control_graph import database_fingerprint, make_auditor, warmed_client, world  # noqa: F401  (fixture)


def derive(token):
    """Incidents are derived from evidence by the alert list (as the console does)."""
    return api.administrator_alerts(status=None, severity=None, agent_name=None, limit=100, x_admin_pin=token)["alerts"]


def blocked_incident(token, agent="ours_agent"):
    register(token, agent)
    request = submit(agent, "send_email")
    alert = next(item for item in derive(token) if item["request_id"] == request["request_id"])
    return alert, request


def workspace(token, alert_id):
    return api.incident_workspace_view(alert_id, x_admin_pin=token)


def events(alert_id, org_id=organizations.DEFAULT_ORG_ID):
    return incident_workspace.incident_events(alert_id, org_id)


# --- The read view ---------------------------------------------------------------------------------

def test_the_workspace_brings_the_incident_its_decision_and_its_timeline_together(world):
    alert, request = blocked_incident(world["ours"])
    result = workspace(world["ours"], alert["alert_id"])
    assert result["incident"]["alert_id"] == alert["alert_id"] and result["incident"]["install_level"] is False
    assert result["explanation"]["basis"] == "recorded" and result["explanation"]["decision"] == "BLOCK"
    types = [entry["type"] for entry in result["timeline"]["entries"]]
    assert {"INCIDENT_OPENED", "REQUEST", "DECISION"} <= set(types)
    stamps = [datetime.fromisoformat(entry["timestamp"]) for entry in result["timeline"]["entries"]]
    assert stamps == sorted(stamps, reverse=True)
    assert result["agent"]["agent_name"] == "ours_agent" and result["agent"]["graph_path"].endswith("tab=relationships")
    assert result["sla"] == {"configured": False, "text": "No SLA set"}
    assert result["integrity"]["decision_record_intact"] is True


def test_the_timeline_holds_only_this_agents_evidence(world):
    alert, _ = blocked_incident(world["ours"])
    register(world["ours"], "ours_agent_two")
    submit("ours_agent_two", "list_files")  # "ours_agent" is a substring of this name
    entries = workspace(world["ours"], alert["alert_id"])["timeline"]["entries"]
    assert all(entry["actor"] != "ours_agent_two" for entry in entries)
    assert not any("list_files" in entry["text"] for entry in entries)


def test_related_incidents_are_this_agents_other_incidents_in_this_org(world):
    first, _ = blocked_incident(world["ours"])
    submit("ours_agent", "send_email")
    derive(world["ours"])
    register(world["theirs"], "theirs_agent")
    submit("theirs_agent", "send_email")
    derive(world["theirs"])
    related = workspace(world["ours"], first["alert_id"])["related"]
    assert related and all(item["alert_id"] != first["alert_id"] for item in related)
    assert all(item["path"].startswith("/incidents/") for item in related)
    theirs = {item["alert_id"] for item in derive(world["theirs"])}
    assert not theirs & {item["alert_id"] for item in related}


def test_the_window_never_reaches_past_retention(world):
    from backend.app import audit_integrity
    audit_integrity.update_retention(30, False, "test")
    alert, _ = blocked_incident(world["ours"])
    with db_compat.connect(database.database_path) as connection:
        connection.execute("UPDATE security_alerts SET created_at = ? WHERE alert_id = ? AND org_id = ?",
                           ((datetime.now(timezone.utc) - timedelta(days=45)).isoformat(), alert["alert_id"], organizations.DEFAULT_ORG_ID))
    since = datetime.fromisoformat(workspace(world["ours"], alert["alert_id"])["timeline"]["window"]["since"])
    assert since >= datetime.now(timezone.utc) - timedelta(days=30, minutes=1)


def test_a_failing_section_does_not_take_the_workspace_down(world, monkeypatch):
    alert, _ = blocked_incident(world["ours"])
    monkeypatch.setattr(incident_workspace, "_related", lambda *args, **kwargs: 1 / 0)
    result = workspace(world["ours"], alert["alert_id"])
    assert result["related"] == {"error": "The related incidents could not be loaded. Try again."}
    assert result["timeline"]["entries"] and result["explanation"]["basis"] == "recorded"


# --- The full action record -----------------------------------------------------------------------

def test_every_status_change_assignment_and_note_is_recorded(world):
    alert, _ = blocked_incident(world["ours"])
    api.administrator_update_alert(alert["alert_id"], api.AlertUpdateRequest(status="ACKNOWLEDGED"), world["ours"])
    api.administrator_update_alert(alert["alert_id"], api.AlertUpdateRequest(status="INVESTIGATING", assigned_to="ours@greyguard.local"), world["ours"])
    api.administrator_add_alert_note(alert["alert_id"], api.AlertNoteRequest(note="checking the agent"), world["ours"])
    api.administrator_update_alert(alert["alert_id"], api.AlertUpdateRequest(status="RESOLVED", assigned_to="ours@greyguard.local", note="false alarm"), world["ours"])
    recorded = [(event["event_type"], event["detail"]) for event in events(alert["alert_id"])]
    assert recorded == [
        ("STATUS_CHANGED", {"from": "OPEN", "to": "ACKNOWLEDGED", "with_note": False}),  # before, unrecorded without a note
        ("STATUS_CHANGED", {"from": "ACKNOWLEDGED", "to": "INVESTIGATING", "with_note": False}),
        ("ASSIGNED", {"from": None, "to": "ours@greyguard.local"}),
        ("NOTE_ADDED", {"note": "checking the agent"}),
        ("STATUS_CHANGED", {"from": "INVESTIGATING", "to": "RESOLVED", "with_note": True}),
        ("NOTE_ADDED", {"note": "false alarm"}),
    ]
    timeline = [entry for entry in workspace(world["ours"], alert["alert_id"])["timeline"]["entries"] if entry.get("action_record")]
    assert len(timeline) == 6 and timeline[0]["text"] == "Note: false alarm"
    # The record names the person, not just "administrator".
    assert {event["actor"] for event in events(alert["alert_id"])} == {"ours@greyguard.local"}


def test_the_action_record_is_append_only_but_deletable_with_its_org(world):
    alert, _ = blocked_incident(world["ours"])
    api.administrator_update_alert(alert["alert_id"], api.AlertUpdateRequest(status="ACKNOWLEDGED"), world["ours"])
    with pytest.raises(Exception, match="append-only"):
        with db_compat.connect(database.database_path) as connection:
            connection.execute("UPDATE incident_events SET actor = 'someone else' WHERE alert_id = ? AND org_id = ?",
                               (alert["alert_id"], organizations.DEFAULT_ORG_ID))
    with db_compat.connect(database.database_path) as connection:
        connection.execute("DELETE FROM incident_events WHERE alert_id = ? AND org_id = ?", (alert["alert_id"], organizations.DEFAULT_ORG_ID))
    assert events(alert["alert_id"]) == []


def test_an_unknown_event_type_is_refused(world):
    from backend.app import alerts
    with pytest.raises(ValueError):
        with db_compat.connect(database.database_path) as connection:
            alerts.record_incident_event(connection, "a", "org", "me", "DELETED_EVERYTHING", {})


# --- Tenant isolation, install level, roles ----------------------------------------------------------

def test_another_orgs_incident_is_a_404(world):
    register(world["theirs"], "theirs_agent")
    submit("theirs_agent", "send_email")
    theirs = derive(world["theirs"])[0]
    with pytest.raises(HTTPException) as error:
        workspace(world["ours"], theirs["alert_id"])
    assert error.value.status_code == 404


def test_another_orgs_events_naming_our_incident_are_never_shown(world):
    alert, _ = blocked_incident(world["ours"])
    with db_compat.connect(database.database_path) as connection:
        connection.execute("INSERT INTO incident_events (alert_id, org_id, timestamp, actor, event_type, detail_json) VALUES (?, ?, ?, ?, ?, ?)",
                           (alert["alert_id"], world["other_org"], datetime.now(timezone.utc).isoformat(), "intruder", "NOTE_ADDED", json.dumps({"note": "x"})))
    assert "intruder" not in json.dumps(workspace(world["ours"], alert["alert_id"]))


def test_install_level_incidents_are_for_install_operators_only(world):
    main.record_authentication_event(claimed_agent_name="ghost_agent", authenticated_agent_name=None, action="read_file",
                                     outcome="AUTHENTICATION_FAILED", reason="Unknown agent.")
    operator = admin_auth.create_administrator("op@greyguard.local", "Op", "PLATFORM_ADMIN", PASSWORD, install_operator=True)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, operator["admin_id"], "PLATFORM_ADMIN", "OWNER")
    token = admin_auth.authenticate(operator["email"], PASSWORD)["access_token"]
    ghost = next(item for item in derive(token) if item["agent_name"] == "ghost_agent")
    result = workspace(token, ghost["alert_id"])
    assert result["incident"]["install_level"] is True and result["agent"]["known"] is False
    assert "install operator" in result["why_you_see_this"]
    for tenant in (world["ours"], world["theirs"]):
        with pytest.raises(HTTPException) as error:
            workspace(tenant, ghost["alert_id"])
        assert error.value.status_code == 404


def test_an_auditor_sees_every_action_disabled_with_a_role_only_reason(world):
    alert, _ = blocked_incident(world["ours"])
    actions = workspace(make_auditor(), alert["alert_id"])["actions"]
    assert actions["primary"]["label"] == "Acknowledge" and actions["primary"]["available"] is False
    assert actions["primary"]["unavailable_reason"] == "Your role, Auditor, can view incidents but not change them."
    # Owner decision 4 (step 3): auditors may export the package. Nothing else is open to them.
    assert [action["id"] for action in actions["others"] if action["available"]] == ["export"]
    for action in actions["others"]:
        if action["id"] != "export":
            assert action["available"] is False and "ours_agent" not in action["unavailable_reason"]
    admin = workspace(world["ours"], alert["alert_id"])["actions"]
    assert admin["primary"]["available"] is True and admin["primary"]["unavailable_reason"] is None


def test_an_auditor_reading_the_workspace_changes_nothing(world):
    alert, _ = blocked_incident(world["ours"])
    headers = {"X-Admin-Pin": make_auditor()}
    client = warmed_client(headers)
    before = database_fingerprint()
    assert client.get(f"/incidents/{alert['alert_id']}/workspace", headers=headers).status_code == 200
    assert database_fingerprint() == before


def test_an_auditor_cannot_change_an_incident_through_the_api(world):
    alert, _ = blocked_incident(world["ours"])
    headers = {"X-Admin-Pin": make_auditor()}
    client = warmed_client(headers)
    assert client.put(f"/alerts/{alert['alert_id']}", headers=headers, json={"status": "RESOLVED", "note": "x"}).status_code == 403
    assert client.post(f"/alerts/{alert['alert_id']}/notes", headers=headers, json={"note": "x"}).status_code == 403
    assert events(alert["alert_id"]) == []


# --- The exact incident-to-request link (decision records version 3) --------------------------------

def test_an_incident_from_a_policy_decision_links_to_its_request_exactly(world):
    alert, request = blocked_incident(world["ours"])  # found by request id, so the link exists
    record = __import__("backend.app.decision_provenance", fromlist=["x"]).get_decision_records(
        [request["request_id"]], org_id=organizations.DEFAULT_ORG_ID)[request["request_id"]]
    assert alert["source_event_id"] == f"policy-{record['audit_event_id']}"
    assert record["schema_version"] == 3


def test_an_older_decision_without_the_link_stays_unlinked_rather_than_guessed(world):
    register(world["ours"], "ours_agent")
    request = submit("ours_agent", "send_email")
    with db_compat.connect(database.database_path) as connection:
        connection.execute("DELETE FROM decision_records WHERE request_id = ? AND org_id = ?", (request["request_id"], organizations.DEFAULT_ORG_ID))
    alert = next(item for item in derive(world["ours"]) if item["event_type"] == "POLICY")
    assert alert["request_id"] is None
    result = workspace(world["ours"], alert["alert_id"])
    assert result["explanation"] is None and "REQUEST" not in {entry["type"] for entry in result["timeline"]["entries"]}


def test_another_orgs_decision_record_can_never_supply_the_link(world):
    register(world["ours"], "ours_agent")
    request = submit("ours_agent", "send_email")
    with db_compat.connect(database.database_path) as connection:
        row = connection.execute("SELECT audit_event_id FROM decision_records WHERE request_id = ? AND org_id = ?",
                                 (request["request_id"], organizations.DEFAULT_ORG_ID)).fetchone()
        connection.execute("DELETE FROM decision_records WHERE request_id = ? AND org_id = ?", (request["request_id"], organizations.DEFAULT_ORG_ID))
        connection.execute(
            "INSERT INTO decision_records (request_id, org_id, agent_name, action, decided_at, outcome, policy_source, matched_rule_id, "
            "rule_type, rule_name, rule_snapshot_json, record_fingerprint, schema_version, audit_event_id) "
            "VALUES ('theirs_req', ?, 'theirs_agent', 'send_email', 't', 'BLOCK', 'PUBLISHED', 'r', 'PERMISSION', 'r', '{}', 'f', 3, ?)",
            (world["other_org"], row[0]))
    alert = next(item for item in derive(world["ours"]) if item["event_type"] == "POLICY")
    assert alert["request_id"] is None


# --- Owner: a member of the incident's org, never free text ----------------------------------------

def test_an_owner_must_be_an_active_member_of_the_incidents_org(world):
    alert, _ = blocked_incident(world["ours"])
    for owner in ("Ada", "theirs@greyguard.local"):  # free text, and a member of another org
        with pytest.raises(HTTPException) as error:
            api.administrator_update_alert(alert["alert_id"], api.AlertUpdateRequest(status="ACKNOWLEDGED", assigned_to=owner), world["ours"])
        assert error.value.status_code == 400
    assert events(alert["alert_id"]) == []
    owner = workspace(world["ours"], alert["alert_id"])["owner"]
    assert owner["kind"] is None and [c["email"] for c in owner["candidates"]] == ["ours@greyguard.local"]


def test_a_legacy_free_text_owner_is_kept_and_labelled_but_never_newly_typed(world):
    alert, _ = blocked_incident(world["ours"])
    with db_compat.connect(database.database_path) as connection:
        connection.execute("UPDATE security_alerts SET assigned_to = 'night shift' WHERE alert_id = ? AND org_id = ?",
                           (alert["alert_id"], organizations.DEFAULT_ORG_ID))
    assert workspace(world["ours"], alert["alert_id"])["owner"] == {
        "name": "night shift", "email": None, "kind": "free_text", "candidates": [{"email": "ours@greyguard.local", "display_name": "Ours"}]}
    # A status change that keeps the legacy owner is allowed.
    api.administrator_update_alert(alert["alert_id"], api.AlertUpdateRequest(status="ACKNOWLEDGED", assigned_to="night shift"), world["ours"])


def test_auditors_get_no_owner_candidates(world):
    alert, _ = blocked_incident(world["ours"])
    assert "candidates" not in workspace(make_auditor(), alert["alert_id"])["owner"]
