import pytest

from backend.app import alerts


@pytest.fixture
def isolated_alert_database(tmp_path, monkeypatch):
    database = tmp_path / "alerts.db"
    monkeypatch.setattr(alerts, "database_path", database)
    alerts.initialize_alert_database()
    return database


def high_event(event_id="policy-1"):
    return {
        "event_id": event_id,
        "event_type": "POLICY",
        "timestamp": "2026-10-02T12:00:00+03:00",
        "agent_name": "test_agent",
        "action": "send_email",
        "outcome": "BLOCK",
        "severity": "HIGH",
        "request_id": None,
        "summary": "Blocked action.",
        "details": {"risk_score": 40},
    }


def test_high_event_creates_alert(isolated_alert_database):
    assert alerts.sync_alerts_from_events([high_event()]) == 1
    result = alerts.get_alerts(limit=10, sync_existing=False)
    assert result["count"] == 1
    assert result["alerts"][0]["status"] == "OPEN"


def test_alert_creation_is_deduplicated(isolated_alert_database):
    event = high_event()
    assert alerts.sync_alerts_from_events([event]) == 1
    assert alerts.sync_alerts_from_events([event]) == 0


def test_info_event_does_not_create_alert(isolated_alert_database):
    event = high_event("policy-2")
    event["severity"] = "INFO"
    assert alerts.sync_alerts_from_events([event]) == 0


def test_alert_workflow_and_note(isolated_alert_database):
    alerts.sync_alerts_from_events([high_event()])
    alert_id = alerts.get_alerts(sync_existing=False)["alerts"][0]["alert_id"]
    updated = alerts.update_alert(
        alert_id, "INVESTIGATING", "administrator", "security-team", "Review started."
    )
    assert updated["status"] == "INVESTIGATING"
    assert updated["assigned_to"] == "security-team"
    assert updated["notes"][0]["note"] == "Review started."


def test_invalid_status_is_rejected(isolated_alert_database):
    with pytest.raises(ValueError, match="Unsupported"):
        alerts.update_alert("missing", "MAYBE", "administrator")
