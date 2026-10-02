import pytest

from backend.app import abuse_protection


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    database = tmp_path / "abuse.db"
    monkeypatch.setattr(abuse_protection, "database_path", database)
    abuse_protection.initialize_abuse_protection()
    return database


def test_default_policies_are_created(isolated_database):
    assert {item["category"] for item in abuse_protection.list_policies()} == set(abuse_protection.DEFAULT_POLICIES)


def test_request_limit_applies_temporary_block(isolated_database):
    abuse_protection.update_policy("GENERAL", {"enabled": True, "request_limit": 2, "window_seconds": 60, "block_seconds": 30, "max_failed_attempts": 5}, "admin")
    assert abuse_protection.check_rate_limit("client", "GENERAL")["allowed"]
    assert abuse_protection.check_rate_limit("client", "GENERAL")["allowed"]
    blocked = abuse_protection.check_rate_limit("client", "GENERAL")
    assert blocked["allowed"] is False
    assert blocked["retry_after"] == 30


def test_suspicious_burst_is_recorded_once(isolated_database):
    abuse_protection.update_policy("GENERAL", {"enabled": True, "request_limit": 5, "window_seconds": 60, "block_seconds": 30, "max_failed_attempts": 5}, "admin")
    for _ in range(4): abuse_protection.check_rate_limit("client", "GENERAL")
    events = abuse_protection.list_abuse_events()
    assert [item["event_type"] for item in events].count("SUSPICIOUS_BURST") == 1


def test_failed_authentication_threshold_locks_identity(isolated_database):
    abuse_protection.update_policy("ADMIN_AUTH", {"enabled": True, "request_limit": 20, "window_seconds": 60, "block_seconds": 30, "max_failed_attempts": 2}, "admin")
    assert abuse_protection.record_authentication_failure("user@example.com")["locked"] is False
    assert abuse_protection.record_authentication_failure("user@example.com")["locked"] is True


def test_success_clears_authentication_failures(isolated_database):
    abuse_protection.record_authentication_failure("user@example.com")
    abuse_protection.clear_authentication_failures("user@example.com")
    assert abuse_protection.record_authentication_failure("user@example.com")["failed_attempts"] == 1


def test_disabled_policy_allows_requests(isolated_database):
    abuse_protection.update_policy("GENERAL", {"enabled": False, "request_limit": 1, "window_seconds": 60, "block_seconds": 30, "max_failed_attempts": 2}, "admin")
    assert all(abuse_protection.check_rate_limit("client")["allowed"] for _ in range(4))
