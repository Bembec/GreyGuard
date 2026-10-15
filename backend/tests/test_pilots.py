"""P5 pilots (P4 decision D2): template, measured criteria, confirmations and outcomes."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import api, entitlements, main, organizations, pilots
from backend.tests.test_org_lifecycle import install, populate, tenant  # noqa: F401 - fixture reuse


@pytest.fixture()
def pilot(install):
    client = TestClient(api.app)
    operator = {"X-Admin-Pin": install["operator"]}
    onboarded = client.post("/organizations/onboard", headers=operator, json={
        "name": "Pilot Co", "owner_email": "ciso@pilot.example", "pilot": True, "plan": "FOUNDATION"})
    assert onboarded.status_code == 201, onboarded.text
    org_id = onboarded.json()["organization"]["org_id"]
    return {"org_id": org_id, "client": client, "operator": operator, "install": install,
            "pilot": onboarded.json()["pilot"]}


def test_onboarding_a_pilot_applies_the_d2_template(pilot):
    started = pilot["pilot"]
    assert started["status"] == "ACTIVE" and started["template"] == {
        "plan": "ENTERPRISE", "days": 90, "decision_day": 75, "max_extension_days": 30}
    current = entitlements.get_entitlements(pilot["org_id"], meters=())
    assert current["plan"] == "ENTERPRISE" and current["status"] == "TRIAL"  # the pilot flag overrides "plan"
    assert 88 <= started["days_remaining"] <= 90 and started["decision_due"] is False
    assert started["criteria_met"] == 0 and len(started["criteria"]) == 6
    assert not any(word in str(started).lower() for word in ("price", "fee", "amount", "card"))


def test_criteria_are_measured_from_product_data(pilot, install):
    org_id = pilot["org_id"]
    owner = tenant(install, "Unused")  # an unrelated org does not affect this pilot's criteria
    populate(owner, "unused")
    owner_token = install["operator"]
    from backend.app import admin_auth
    member = admin_auth.create_administrator("ops@pilot.example", "Ops", "PLATFORM_ADMIN", "SecureDemo!123")
    organizations.ensure_membership(org_id, member["admin_id"], "PLATFORM_ADMIN", "OWNER")
    token = admin_auth.authenticate("ops@pilot.example", "SecureDemo!123")["access_token"]
    import hashlib
    organizations.switch_active_org(member["admin_id"], org_id, hashlib.sha256(token.encode()).hexdigest())
    headers = {"X-Admin-Pin": token}
    client = pilot["client"]
    client.post("/agents", headers=headers, json={"agent_name": "pilot_agent", "scopes": ["read_file", "write_note"]})
    held = main.submit_tool_request("pilot_agent", "write_note", "pilot-note.txt", {"content": "hello"})
    decided = client.post(f"/tool-requests/{held['request_id']}/decision", headers=headers, json={"decision": "APPROVED", "note": "Reviewed by ops"})
    assert decided.status_code == 200, decided.text
    client.put("/policy-emergency-controls", headers=headers, json={"global_deny": True})
    client.put("/policy-emergency-controls", headers=headers, json={"global_deny": False})
    # Four weeks of use: move the first request back in time.
    from backend.app import database
    with database.sqlite3.connect(database.database_path) as connection:
        connection.execute("UPDATE tool_requests SET timestamp = ? WHERE org_id = ? AND request_id = ?",
                           ((datetime.now(timezone.utc) - timedelta(days=30)).isoformat(), org_id, held["request_id"]))
    main.submit_tool_request("pilot_agent", "read_file", "today.txt")
    criteria = {c["key"]: c for c in client.get(f"/organizations/{org_id}/pilot", headers=headers).json()["pilot"]["criteria"]}
    assert criteria["human_approval"]["met"] and criteria["emergency_exercised"]["met"]
    assert criteria["sustained_use"]["met"], criteria["sustained_use"]
    assert not criteria["evidence_accepted"]["met"] and not criteria["no_service_incident"]["met"]
    assert owner_token  # operator untouched


def test_manual_criteria_need_an_operator_a_note_and_for_evidence_an_export(pilot, install):
    org_id, client, operator = pilot["org_id"], pilot["client"], pilot["operator"]
    other = tenant(install, "Not Operator")
    refused = client.post(f"/organizations/{org_id}/pilot/confirmations", headers={"X-Admin-Pin": other["owner"]},
                          json={"criterion": "no_service_incident", "note": "Trying to confirm my own pilot"})
    assert refused.status_code == 403
    assert client.post(f"/organizations/{org_id}/pilot/confirmations", headers=operator,
                       json={"criterion": "no_service_incident", "note": "short"}).status_code == 422
    confirmed = client.post(f"/organizations/{org_id}/pilot/confirmations", headers=operator, json={
        "criterion": "evidence_accepted", "note": "Head of Internal Audit accepted the export on review"}).json()
    by_key = {c["key"]: c for c in confirmed["criteria"]}
    # Confirmed by an operator, but not met until an export actually exists.
    assert by_key["evidence_accepted"]["confirmation"] and not by_key["evidence_accepted"]["met"]
    client.post(f"/organizations/{org_id}/export", headers=operator)
    by_key = {c["key"]: c for c in client.get(f"/organizations/{org_id}/pilot", headers=operator).json()["pilot"]["criteria"]}
    assert by_key["evidence_accepted"]["met"]


def test_extend_once_then_convert(pilot):
    org_id, client, operator = pilot["org_id"], pilot["client"], pilot["operator"]
    # On day 0 an extension is refused: it belongs at the decision point.
    early = client.post(f"/organizations/{org_id}/pilot/decision", headers=operator,
                        json={"outcome": "EXTEND", "reason": "Asking far too early", "extend_days": 30})
    assert early.status_code == 409 and "near the end" in early.json()["detail"]
    with pilots.sqlite3.connect(pilots.database_path) as connection:
        connection.execute("UPDATE org_pilots SET ends_at = ?, decision_due_at = ? WHERE org_id = ?", (
            (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
            (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), org_id))
    assert client.get(f"/organizations/{org_id}/pilot", headers=operator).json()["pilot"]["decision_due"] is True
    extended = client.post(f"/organizations/{org_id}/pilot/decision", headers=operator,
                           json={"outcome": "EXTEND", "reason": "Waiting on the SIEM integration", "extend_days": 30}).json()
    assert extended["extended"] == 1 and extended["status"] == "ACTIVE" and 43 <= extended["days_remaining"] <= 45
    again = client.post(f"/organizations/{org_id}/pilot/decision", headers=operator,
                        json={"outcome": "EXTEND", "reason": "Asking for a second extension", "extend_days": 10})
    assert again.status_code == 409
    converted = client.post(f"/organizations/{org_id}/pilot/decision", headers=operator,
                            json={"outcome": "CONVERT", "reason": "All criteria met; annual agreement signed"}).json()
    assert converted["status"] == "CONVERTED"
    current = entitlements.get_entitlements(org_id, meters=())
    assert current["plan"] == "ENTERPRISE" and current["status"] == "ACTIVE"
    assert client.post(f"/organizations/{org_id}/pilot/decision", headers=operator,
                       json={"outcome": "OFFBOARD", "reason": "Decided pilots cannot be decided again"}).status_code == 409


def test_offboard_outcome_starts_offboarding(pilot):
    org_id, client, operator = pilot["org_id"], pilot["client"], pilot["operator"]
    decided = client.post(f"/organizations/{org_id}/pilot/decision", headers=operator,
                          json={"outcome": "OFFBOARD", "reason": "Customer chose not to proceed"}).json()
    assert decided["status"] == "OFFBOARDED"
    assert organizations.get_organization(org_id)["status"] == "OFFBOARDING"


def test_only_operators_start_pilots_and_members_can_read_theirs(pilot, install):
    org = tenant(install, "Plain Org")
    client = pilot["client"]
    assert client.post(f"/organizations/{org['org_id']}/pilot", headers={"X-Admin-Pin": org["owner"]}).status_code == 403
    assert client.get(f"/organizations/{org['org_id']}/pilot", headers={"X-Admin-Pin": org["owner"]}).json() == {"pilot": None}
    assert client.get(f"/organizations/{pilot['org_id']}/pilot", headers={"X-Admin-Pin": org["owner"]}).status_code == 403
    assert client.post(f"/organizations/{organizations.DEFAULT_ORG_ID}/pilot", headers=pilot["operator"]).status_code == 409
    assert client.post(f"/organizations/{pilot['org_id']}/pilot", headers=pilot["operator"]).status_code == 409
