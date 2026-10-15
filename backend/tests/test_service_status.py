"""P3 public status page: live component checks, incidents, maintenance and measured response."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import api, outbound_worker, service_status
from backend.tests.test_org_lifecycle import install, tenant  # noqa: F401 - fixture reuse


@pytest.fixture()
def status(install, monkeypatch):
    monkeypatch.setenv("GREYGUARD_DISTRIBUTION_SIGNING_KEY", "configured")
    monkeypatch.setenv("GREYGUARD_DELIVERY_WORKER_ENABLED", "true")
    monkeypatch.setattr(outbound_worker, "LAST_TICK", {"at": datetime.now(timezone.utc).isoformat(), "failed": []})
    return {**install, "client": TestClient(api.app), "operator": {"X-Admin-Pin": install["operator"]}}


def test_the_status_page_is_public_and_tenant_free(status, install):
    org = tenant(install, "Tenant Status")
    body = status["client"].get("/status")
    assert body.status_code == 200
    data = body.json()
    assert data["status"] == "OPERATIONAL" and set(data["components"]) == set(service_status.COMPONENTS)
    assert org["org_id"] not in body.text and "Tenant Status" not in body.text
    assert "not a service outage" in data["note"]


def test_live_checks_drive_component_state(status, monkeypatch):
    monkeypatch.setattr(outbound_worker, "LAST_TICK", {"at": datetime.now(timezone.utc).isoformat(), "failed": ["security_exports"]})
    assert status["client"].get("/status").json()["components"]["delivery_worker"] == "DEGRADED"
    monkeypatch.setattr(outbound_worker, "LAST_TICK", {"at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), "failed": []})
    data = status["client"].get("/status").json()
    assert data["components"]["delivery_worker"] == "DEGRADED" and data["status"] == "DEGRADED"
    monkeypatch.delenv("GREYGUARD_DISTRIBUTION_SIGNING_KEY")
    assert status["client"].get("/status").json()["components"]["policy_distribution"] == "NOT_CONFIGURED"


def test_incidents_move_through_states_and_are_measured(status):
    client, operator = status["client"], status["operator"]
    opened = client.post("/status/incidents", headers=operator, json={
        "title": "Delayed SIEM delivery", "severity": "SEV2", "components": ["delivery_worker"], "message": "Investigating delays."})
    assert opened.status_code == 201, opened.text
    incident_id = opened.json()["incident_id"]
    page = client.get("/status").json()
    assert page["status"] == "DEGRADED" and page["incidents"][0]["incident_id"] == incident_id
    assert "created_by" not in page["incidents"][0]
    for state in ("IDENTIFIED", "RESOLVED"):
        assert client.post(f"/status/incidents/{incident_id}/updates", headers=operator,
                           json={"state": state, "message": f"Now {state.lower()}."}).status_code == 200
    assert client.get("/status").json()["incidents"] == []
    assert client.post(f"/status/incidents/{incident_id}/updates", headers=operator,
                       json={"state": "MONITORING", "message": "Reopen attempt"}).status_code == 400
    measured = client.get("/status/history").json()["measured_response"]["SEV2"]
    assert measured["incidents"] == 1 and measured["median_minutes_to_acknowledge"] is not None
    assert measured["median_minutes_to_resolve"] is not None


def test_maintenance_windows_show_and_mark_components(status):
    client, operator = status["client"], status["operator"]
    now = datetime.now(timezone.utc)
    window = client.post("/status/maintenance", headers=operator, json={
        "title": "Database upgrade", "components": ["database"],
        "starts_at": (now - timedelta(minutes=5)).isoformat(), "ends_at": (now + timedelta(hours=1)).isoformat()})
    assert window.status_code == 201, window.text
    page = client.get("/status").json()
    assert page["components"]["database"] == "MAINTENANCE" and page["maintenance"][0]["in_progress"] is True
    too_long = client.post("/status/maintenance", headers=operator, json={
        "title": "Too long", "components": ["api"], "starts_at": now.isoformat(), "ends_at": (now + timedelta(hours=13)).isoformat()})
    assert too_long.status_code == 400


def test_only_install_operators_declare_incidents(status, install):
    org = tenant(install, "Not An Operator")
    response = status["client"].post("/status/incidents", headers={"X-Admin-Pin": org["owner"]}, json={
        "title": "Fake outage", "severity": "SEV1", "components": ["api"], "message": "Not allowed."})
    assert response.status_code == 403
    assert status["client"].get("/status/severities").json()["severities"]["SEV1"]["name"] == "Critical"
