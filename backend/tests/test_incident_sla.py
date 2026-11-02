"""P7.5 item 5, step 4: incident response targets (SLA) per organization.

Owner decision 2, 2026-10-16: no defaults. "No SLA set" until an organization sets targets; the
suggested values are offered, never applied. Negative authorization and tenant-isolation tests.
"""
from datetime import datetime, timedelta, timezone

import pytest

from fastapi import HTTPException

from backend.app import admin_auth, alerts, api, database, db_compat, incident_sla, organizations, tenant_guard
from backend.tests.test_agent_tenancy import PASSWORD, register, submit, tenants  # noqa: F401  (fixture)
from backend.tests.test_control_graph import database_fingerprint, make_auditor, warmed_client, world  # noqa: F401  (fixture)
from backend.tests.test_incident_workspace import blocked_incident, derive, workspace

OURS = organizations.DEFAULT_ORG_ID
TARGETS = {"CRITICAL": {"acknowledge_minutes": 15, "resolve_minutes": 240}, "HIGH": {"acknowledge_minutes": 60, "resolve_minutes": 1440}}
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def person(role, email):
    created = admin_auth.create_administrator(email, role.title(), role, PASSWORD)
    organizations.ensure_membership(OURS, created["admin_id"], role, "MEMBER")
    return admin_auth.authenticate(email, PASSWORD)["access_token"]


def client(token):
    return warmed_client({"X-Admin-Pin": token}), {"X-Admin-Pin": token}


def put(token, targets, org_id=OURS):
    http, headers = client(token)
    return http.put(f"/organizations/{org_id}/incident-sla", headers=headers, json={"targets": targets})


def get(token, org_id=OURS):
    http, headers = client(token)
    return http.get(f"/organizations/{org_id}/incident-sla", headers=headers)


def stored(org_id=OURS):
    incident_sla.initialize_incident_sla()
    with db_compat.connect(database.database_path) as connection:
        return connection.execute("SELECT severity, acknowledge_minutes, resolve_minutes FROM incident_sla_targets WHERE org_id = ? ORDER BY severity",
                                  (org_id,)).fetchall()


def age(alert_id, minutes):
    """Move an incident's opening back in time (the SLA clock starts there)."""
    opened = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    with db_compat.connect(database.database_path) as connection:
        connection.execute("UPDATE security_alerts SET created_at = ? WHERE alert_id = ? AND org_id = ?", (opened, alert_id, OURS))


def incident(severity="HIGH", status="OPEN", created=NOW - timedelta(minutes=10), org_id=OURS):
    return {"alert_id": "a1", "severity": severity, "status": status, "created_at": created.isoformat(), "org_id": org_id}


def change(minutes_after_open, frm, to, opened=NOW - timedelta(minutes=10)):
    return {"timestamp": (opened + timedelta(minutes=minutes_after_open)).isoformat(), "from": frm, "to": to}


# --- No defaults -----------------------------------------------------------------------------------

def test_nothing_is_set_by_default_and_suggestions_are_never_applied(world):
    alert, _ = blocked_incident(world["ours"])
    response = get(world["ours"])
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False and body["targets"] == {} and body["can_edit"] is True
    assert body["suggestions"] == incident_sla.SUGGESTED
    assert stored() == []  # offered, not applied
    view = workspace(world["ours"], alert["alert_id"])
    assert view["sla"]["text"] == "No SLA set" and view["sla"]["state"] is None
    assert not [entry for entry in view["timeline"]["entries"] if entry["type"] == "SLA_BREACH"]
    listed = next(item for item in derive(world["ours"]) if item["alert_id"] == alert["alert_id"])
    assert listed["sla"]["configured"] is False


# --- Setting targets -------------------------------------------------------------------------------

def test_an_admin_sets_targets_and_the_change_is_attributed(world):
    response = put(world["ours"], TARGETS)
    assert response.status_code == 200, response.text
    body = get(world["ours"]).json()
    assert body["configured"] is True and body["targets"] == TARGETS and body["suggestions"] is None
    assert body["updated_by"] == "ours@greyguard.local"
    assert [tuple(row) for row in stored()] == [("CRITICAL", 15, 240), ("HIGH", 60, 1440)]


def test_an_empty_set_returns_to_no_sla(world):
    put(world["ours"], TARGETS)
    assert put(world["ours"], {}).status_code == 200
    assert stored() == [] and get(world["ours"]).json()["configured"] is False


def test_a_severity_with_only_one_time_keeps_the_other_unset(world):
    assert put(world["ours"], {"HIGH": {"resolve_minutes": 120}}).status_code == 200
    assert get(world["ours"]).json()["targets"] == {"HIGH": {"acknowledge_minutes": None, "resolve_minutes": 120}}


@pytest.mark.parametrize("targets, status", [
    ({"HIGH": {"acknowledge_minutes": 120, "resolve_minutes": 60}}, 400),   # resolve before acknowledge
    ({"HIGH": {"acknowledge_minutes": 0}}, 422),
    ({"HIGH": {"acknowledge_minutes": incident_sla.MAX_MINUTES + 1}}, 422),
    ({"LOW": {"acknowledge_minutes": 10}}, 422),                            # incidents are CRITICAL or HIGH only
    ({"HIGH": {"acknowledge_minutes": "soon"}}, 422),
    ({"HIGH": {"acknowledge_minutes": 10, "extra": 1}}, 200),               # unknown fields are dropped by the model
])
def test_invalid_targets_are_refused_and_change_nothing(world, targets, status):
    put(world["ours"], TARGETS)
    response = put(world["ours"], targets)
    assert response.status_code == status, response.text
    if status != 200:
        assert [tuple(row) for row in stored()] == [("CRITICAL", 15, 240), ("HIGH", 60, 1440)]


def test_the_module_refuses_what_the_api_model_would_also_refuse():
    with pytest.raises(ValueError):
        incident_sla.set_targets(OURS, {"LOW": {"acknowledge_minutes": 5}}, "x")
    with pytest.raises(ValueError):
        incident_sla.set_targets(OURS, {"HIGH": {"acknowledge_minutes": True}}, "x")


# --- Authorization ---------------------------------------------------------------------------------

def test_the_permission_layer_requires_admin_manage_to_change_targets():
    assert admin_auth.required_permission("PUT", "/organizations/o1/incident-sla") == "admin:manage"
    assert admin_auth.required_permission("GET", "/organizations/o1/incident-sla") == "read"


@pytest.mark.parametrize("role", ["AUDITOR", "SECURITY_ANALYST"])
def test_only_an_admin_can_change_targets_and_a_refusal_changes_nothing(world, role):
    put(world["ours"], TARGETS)
    token = make_auditor() if role == "AUDITOR" else person(role, "analyst@greyguard.local")
    warmed_client({"X-Admin-Pin": token})
    before = database_fingerprint()
    assert put(token, {}).status_code == 403
    assert database_fingerprint() == before
    readable = get(token)
    assert readable.status_code == 200 and readable.json()["can_edit"] is False and readable.json()["targets"] == TARGETS


# --- Tenant isolation ------------------------------------------------------------------------------

def test_another_orgs_targets_are_the_same_404_as_a_missing_org(world):
    put(world["theirs"], {"HIGH": {"acknowledge_minutes": 5}}, org_id=world["other_org"])
    for response in (get(world["ours"], world["other_org"]), get(world["ours"], "no-such-org"),
                     put(world["ours"], TARGETS, world["other_org"]), put(world["ours"], TARGETS, "no-such-org")):
        assert response.status_code == 404 and response.json()["detail"] == "Organization not found."
    assert [tuple(row) for row in stored(world["other_org"])] == [("HIGH", 5, None)]


def test_one_orgs_targets_never_measure_another_orgs_incidents(world):
    put(world["ours"], {"HIGH": {"acknowledge_minutes": 1}})
    register(world["theirs"], "theirs_agent")
    submit("theirs_agent", "send_email")
    theirs = derive(world["theirs"])[0]
    assert theirs["sla"]["configured"] is False and theirs["sla"]["text"] == "No SLA set"
    assert workspace(world["theirs"], theirs["alert_id"])["sla"]["state"] is None


def test_the_targets_table_is_org_scoped_so_export_and_deletion_include_it():
    assert "incident_sla_targets" in tenant_guard.ORG_SCOPED_TABLES


# --- The workspace and Incident Center -------------------------------------------------------------

def test_a_breach_shows_on_the_workspace_its_timeline_and_incident_center(world):
    alert, _ = blocked_incident(world["ours"])
    put(world["ours"], {alert["severity"]: {"acknowledge_minutes": 15, "resolve_minutes": 240}})
    age(alert["alert_id"], 30)
    view = workspace(world["ours"], alert["alert_id"])
    assert view["sla"]["state"] == "breached" and view["sla"]["text"] == "Acknowledge target breached (15 minutes)"
    [breach] = [entry for entry in view["timeline"]["entries"] if entry["type"] == "SLA_BREACH"]
    assert breach["text"] == "SLA breached: not acknowledged within 15 minutes."
    listed = next(item for item in derive(world["ours"]) if item["alert_id"] == alert["alert_id"])
    assert listed["sla"]["state"] == "breached"


def test_acknowledging_completes_the_first_target_from_the_action_record(world):
    alert, _ = blocked_incident(world["ours"])
    put(world["ours"], {alert["severity"]: {"acknowledge_minutes": 15, "resolve_minutes": 240}})
    http, headers = client(world["ours"])
    assert http.put(f"/alerts/{alert['alert_id']}", headers=headers, json={"status": "ACKNOWLEDGED"}).status_code == 200
    phases = {item["phase"]: item for item in workspace(world["ours"], alert["alert_id"])["sla"]["phases"]}
    assert phases["acknowledge"]["state"] == "met" and phases["resolve"]["state"] == "within"


def test_the_package_includes_the_sla_state(world):
    alert, _ = blocked_incident(world["ours"])
    put(world["ours"], TARGETS)
    http, headers = client(world["ours"])
    package = http.post(f"/incidents/{alert['alert_id']}/package", headers=headers).json()
    assert package["parts"]["sla"]["configured"] is True and "sla" in package["manifest"]["parts"]


# --- Evaluation ------------------------------------------------------------------------------------

@pytest.mark.parametrize("minutes_open, state", [(10, "within"), (50, "due_soon"), (61, "breached")])
def test_an_open_incident_is_within_due_soon_or_breached(minutes_open, state):
    opened = NOW - timedelta(minutes=minutes_open)
    result = incident_sla.evaluate(incident(created=opened), TARGETS, [], NOW)
    assert result["state"] == state and result["phases"][0]["phase"] == "acknowledge"
    assert result["deadline"] == (opened + timedelta(minutes=60)).isoformat()


def test_met_and_missed_use_the_recorded_times():
    met = incident_sla.evaluate(incident(status="RESOLVED", created=NOW - timedelta(days=2)), TARGETS,
                                [change(30, "OPEN", "ACKNOWLEDGED", NOW - timedelta(days=2)), change(600, "ACKNOWLEDGED", "RESOLVED", NOW - timedelta(days=2))], NOW)
    assert [item["state"] for item in met["phases"]] == ["met", "met"] and met["breaches"] == []
    missed = incident_sla.evaluate(incident(status="RESOLVED", created=NOW - timedelta(days=3)), TARGETS,
                                   [change(90, "OPEN", "ACKNOWLEDGED", NOW - timedelta(days=3)), change(2000, "ACKNOWLEDGED", "RESOLVED", NOW - timedelta(days=3))], NOW)
    assert [item["state"] for item in missed["phases"]] == ["missed", "missed"] and len(missed["breaches"]) == 2


def test_closing_straight_from_open_also_acknowledges():
    opened = NOW - timedelta(hours=5)
    result = incident_sla.evaluate(incident(status="DISMISSED", created=opened), TARGETS, [change(5, "OPEN", "DISMISSED", opened)], NOW)
    assert [item["state"] for item in result["phases"]] == ["met", "met"]


def test_changes_from_before_the_action_record_are_not_measurable_never_guessed():
    closed = incident_sla.evaluate(incident(status="RESOLVED", created=NOW - timedelta(days=9)), TARGETS, [], NOW)
    assert [item["state"] for item in closed["phases"]] == ["not_measurable", "not_measurable"] and closed["breaches"] == []
    # Acknowledged without a record, still open: only the acknowledgement is unknown; resolution is still measured.
    acknowledged = incident_sla.evaluate(incident(status="ACKNOWLEDGED", created=NOW - timedelta(minutes=30)), TARGETS, [], NOW)
    assert [item["state"] for item in acknowledged["phases"]] == ["not_measurable", "within"]


def test_no_target_for_this_severity_and_install_level_incidents():
    only_critical = {"CRITICAL": TARGETS["CRITICAL"]}
    assert incident_sla.evaluate(incident(severity="HIGH"), only_critical, [], NOW)["text"] == "No SLA set for high incidents"
    install = incident_sla.evaluate(incident(org_id=None), TARGETS, [], NOW)
    assert install["configured"] is False and install["state"] is None


def test_evaluate_many_never_applies_the_callers_targets_to_another_org(world):
    put(world["ours"], {"HIGH": {"acknowledge_minutes": 1}})
    foreign = {**incident(), "alert_id": "f1", "org_id": world["other_org"]}
    own = {**incident(), "alert_id": "o1"}
    states = incident_sla.evaluate_many([foreign, own], OURS, NOW)
    assert states["f1"]["configured"] is False and states["o1"]["state"] == "breached"


def test_saving_one_orgs_targets_never_touches_anothers(world):
    assert put(world["theirs"], {"HIGH": {"acknowledge_minutes": 5}}, org_id=world["other_org"]).status_code == 200
    assert put(world["ours"], TARGETS).status_code == 200
    assert put(world["ours"], {}).status_code == 200
    assert [tuple(row) for row in stored(world["other_org"])] == [("HIGH", 5, None)]


def test_a_member_of_both_orgs_reaches_only_the_active_one(world):
    http, headers = client(world["ours"])
    me = http.get("/auth/me", headers=headers).json()
    organizations.ensure_membership(world["other_org"], me["admin_id"], "PLATFORM_ADMIN", "MEMBER")
    for response in (get(world["ours"], world["other_org"]), put(world["ours"], TARGETS, world["other_org"])):
        assert response.status_code == 404
    assert stored(world["other_org"]) == []


def test_the_route_itself_refuses_a_non_admin_even_past_the_permission_layer(world):
    auditor = make_auditor()
    with pytest.raises(HTTPException) as error:
        api.put_incident_sla(OURS, api.IncidentSlaRequest(targets={}), x_admin_pin=auditor)
    assert error.value.status_code == 403


def test_another_orgs_events_never_complete_this_incidents_targets(world):
    alert, _ = blocked_incident(world["ours"])
    put(world["ours"], {alert["severity"]: {"acknowledge_minutes": 15}})
    age(alert["alert_id"], 30)
    with db_compat.connect(database.database_path) as connection:  # a planted event under another org
        alerts.record_incident_event(connection, alert["alert_id"], world["other_org"], "intruder", "STATUS_CHANGED",
                                     {"from": "OPEN", "to": "ACKNOWLEDGED", "with_note": False})
    assert workspace(world["ours"], alert["alert_id"])["sla"]["state"] == "breached"


def test_a_recorded_close_never_stands_in_for_an_unrecorded_acknowledgement():
    opened = NOW - timedelta(hours=5)
    result = incident_sla.evaluate(incident(status="RESOLVED", created=opened), TARGETS, [change(5, "ACKNOWLEDGED", "RESOLVED", opened)], NOW)
    assert [item["state"] for item in result["phases"]] == ["not_measurable", "met"]
