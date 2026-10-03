import sqlite3

import pytest

from backend.app import notifications


@pytest.fixture
def notification_database(tmp_path, monkeypatch):
    path = tmp_path / "notifications.db"
    monkeypatch.setattr(notifications, "database_path", path)
    notifications.initialize_notification_database()
    return path


def insert_notification(path, notification_id="ntf_one", severity="HIGH"):
    with sqlite3.connect(path) as connection:
        connection.execute("""
            INSERT INTO security_notifications (
                notification_id, source_alert_id, created_at, severity,
                title, message, resource_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            notification_id, "alert_" + notification_id,
            "2026-10-02T12:00:00+00:00", severity,
            "Policy violation", "A blocked action requires review.",
            "/incidents",
        ))


def test_notification_list_returns_unread_items(notification_database, monkeypatch):
    monkeypatch.setattr(notifications, "sync_notifications", lambda: 0)
    insert_notification(notification_database)
    result = notifications.list_notifications(unread_only=True)
    assert result["count"] == 1
    assert result["notifications"][0]["is_read"] is False


def test_notification_can_be_marked_read(notification_database):
    insert_notification(notification_database)
    result = notifications.mark_notification_read("ntf_one", "security@example.com")
    assert result["is_read"] is True
    assert result["read_by"] == "security@example.com"
    assert result["read_at"]


def test_mark_all_only_counts_unread_notifications(notification_database):
    insert_notification(notification_database, "ntf_one")
    insert_notification(notification_database, "ntf_two", "CRITICAL")
    notifications.mark_notification_read("ntf_one", "analyst")
    assert notifications.mark_all_notifications_read("analyst") == 1


def test_summary_groups_unread_severity(notification_database, monkeypatch):
    monkeypatch.setattr(notifications, "sync_notifications", lambda: 0)
    insert_notification(notification_database, "ntf_high")
    insert_notification(notification_database, "ntf_critical", "CRITICAL")
    summary = notifications.notification_summary()
    assert summary == {"total": 2, "unread": 2, "unread_critical": 1, "unread_high": 1}


def test_missing_notification_is_rejected(notification_database):
    with pytest.raises(KeyError, match="not found"):
        notifications.mark_notification_read("missing", "analyst")


def test_retention_policy_can_be_updated(notification_database):
    result = notifications.update_retention_policy(180, "admin@example.com")
    assert result["retention_days"] == 180
    assert result["updated_by"] == "admin@example.com"
    assert notifications.retention_history()[0]["action"] == "POLICY_UPDATED"


def test_retention_policy_rejects_unsafe_range(notification_database):
    with pytest.raises(ValueError, match="between 7 and 3650"):
        notifications.update_retention_policy(1, "admin@example.com")


def test_cleanup_removes_expired_notifications_and_records_evidence(notification_database):
    insert_notification(notification_database, "ntf_expired")
    with sqlite3.connect(notification_database) as connection:
        connection.execute(
            "UPDATE security_notifications SET created_at = '2020-01-01T00:00:00+00:00'"
        )
    result = notifications.cleanup_expired_notifications("admin@example.com")
    assert result["deleted"] == 1
    assert notifications.retention_history()[0]["deleted_count"] == 1


def test_expired_alert_is_not_recreated(notification_database, monkeypatch):
    insert_notification(notification_database, "ntf_expired")
    with sqlite3.connect(notification_database) as connection:
        connection.execute(
            "UPDATE security_notifications SET created_at = '2020-01-01T00:00:00+00:00'"
        )
    notifications.cleanup_expired_notifications("admin@example.com")
    monkeypatch.setattr("backend.app.alerts.get_alerts", lambda limit: {"alerts": [{
        "alert_id": "alert_ntf_expired", "created_at": "2020-01-01T00:00:00+00:00",
        "severity": "HIGH", "title": "Expired", "summary": "Expired alert",
    }]})
    assert notifications.sync_notifications() == 0
