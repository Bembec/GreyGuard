"""P7.5 batch 4d: time ranges on the evidence lists.

The rules approved on 2026-10-16: a range narrows an org-scoped query and never widens it; open
work (pending approvals, unresolved alerts) stays visible whatever the range; nobody may query past
the 400-day ceiling or past configured retention; a capped list says it is capped.
"""
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend.app import admin_auth, alerts, api, audit_integrity, database, db_compat, main, organizations
from backend.app.time_range import MAX_LOOKBACK_DAYS, parse_time_range
from backend.tests.test_agent_tenancy import PASSWORD, register, submit, tenants  # noqa: F401  (fixture)

NOW = datetime.now(timezone.utc)


def ago(**delta):
    return (NOW - timedelta(**delta)).isoformat()


@pytest.fixture()
def retention(tenants, monkeypatch):  # noqa: F811
    """Point audit integrity at the tenants' database, so retention is read from the same place."""
    monkeypatch.setattr(audit_integrity, "database_path", database.database_path)
    return tenants


def backdate(table, key_column, key, column, when, org_id=organizations.DEFAULT_ORG_ID):
    with db_compat.connect(database.database_path) as connection:
        connection.execute(f"UPDATE {table} SET {column} = ? WHERE {key_column} = ? AND org_id = ?",  # nosec B608  # test-only constants
                           (when, key, org_id))


def rejects(since, until=None, **kwargs):
    with pytest.raises(HTTPException) as error:
        parse_time_range(since, until, org_id=organizations.DEFAULT_ORG_ID, **kwargs)
    assert error.value.status_code == 422
    return error.value.detail


def requests_in(token, since=None, until=None, **filters):
    return api.list_tool_requests(agent_name=filters.get("agent_name"), approval_status=filters.get("approval_status"),
                                  execution_status=None, limit=filters.get("limit", 50), x_admin_pin=token,
                                  since=since, until=until)


# --- Validation -------------------------------------------------------------------------------

def test_no_bounds_means_no_range_and_todays_behaviour(retention):
    assert parse_time_range(None, None, org_id=organizations.DEFAULT_ORG_ID) is None
    assert parse_time_range("", "", org_id=organizations.DEFAULT_ORG_ID) is None


def test_bounds_are_normalized_to_utc_in_the_stored_form(retention):
    parsed = parse_time_range("2026-10-16T12:00:00+02:00", "2026-10-16T13:00:00Z", org_id=organizations.DEFAULT_ORG_ID,
                              now=datetime(2026, 10, 17, tzinfo=timezone.utc))
    assert parsed.since == "2026-10-16T10:00:00+00:00" and parsed.until == "2026-10-16T13:00:00+00:00"


@pytest.mark.parametrize("since, until, fragment", [
    ("yesterday", None, "ISO 8601"),
    ("2026-10-16T10:00:00", None, "timezone"),
    (None, "2026-10-16T10:00:00Z", "needs a since"),
    ("2026-10-16T10:00:00Z", "2026-10-16T10:00:00Z", "after since"),
    ("2026-10-16T10:00:00Z", "2026-10-16T09:00:00Z", "after since"),
    ("2026-10-16T10:00:00Z", "not a date", "ISO 8601"),
    ("1' OR '1'='1", None, "ISO 8601"),
])
def test_malformed_or_inverted_ranges_are_refused(retention, since, until, fragment):
    assert fragment in rejects(since, until, now=datetime(2026, 10, 17, tzinfo=timezone.utc))


def test_a_start_in_the_future_is_refused_but_clock_skew_is_tolerated(retention):
    rejects((NOW + timedelta(hours=1)).isoformat())
    assert parse_time_range((NOW + timedelta(minutes=1)).isoformat(), None, org_id=organizations.DEFAULT_ORG_ID)


def test_the_lookback_never_exceeds_400_days(retention):
    audit_integrity.update_retention(3650, False, "test")
    assert parse_time_range(ago(days=MAX_LOOKBACK_DAYS - 1), None, org_id=organizations.DEFAULT_ORG_ID)
    assert "400 days" in rejects(ago(days=MAX_LOOKBACK_DAYS + 1))


def test_the_lookback_never_exceeds_configured_retention(retention):
    audit_integrity.update_retention(30, False, "test")
    assert parse_time_range(ago(days=29), None, org_id=organizations.DEFAULT_ORG_ID)
    assert "30 days" in rejects(ago(days=31))


# --- Tool requests ----------------------------------------------------------------------------

def test_a_range_returns_only_the_callers_org_and_only_in_range(retention):
    register(retention["ours"], "ours_agent")
    register(retention["theirs"], "theirs_agent")
    recent = submit("ours_agent", "read_file")
    old = submit("ours_agent", "read_file")
    backdate("tool_requests", "request_id", old["request_id"], "timestamp", ago(days=10))
    submit("theirs_agent", "read_file")

    listed = requests_in(retention["ours"], since=ago(days=1))
    assert [r["request_id"] for r in listed["requests"]] == [recent["request_id"]]
    assert listed["range"]["since"] and listed["truncated"] is False
    # The other org's request is in range too, and still never appears.
    assert {r["org_id"] for r in listed["requests"]} == {organizations.DEFAULT_ORG_ID}
    theirs = requests_in(retention["theirs"], since=ago(days=1))["requests"]
    assert {r["agent_name"] for r in theirs} == {"theirs_agent"}


def test_until_is_exclusive_and_bounds_the_end(retention):
    register(retention["ours"], "ours_agent")
    request = submit("ours_agent", "read_file")
    at = ago(days=3)
    backdate("tool_requests", "request_id", request["request_id"], "timestamp", at)
    assert requests_in(retention["ours"], since=ago(days=4), until=at)["requests"] == []
    assert len(requests_in(retention["ours"], since=ago(days=4), until=ago(days=2))["requests"]) == 1


def test_pending_requests_stay_visible_whatever_the_range(retention):
    register(retention["ours"], "ours_agent")
    pending = submit("ours_agent")  # write_note: ASK, so PENDING
    backdate("tool_requests", "request_id", pending["request_id"], "timestamp", ago(days=30))
    listed = requests_in(retention["ours"], since=ago(hours=24))["requests"]
    assert [r["request_id"] for r in listed] == [pending["request_id"]]
    # A status filter still applies: asking for decided requests does not drag pending ones in.
    assert requests_in(retention["ours"], since=ago(hours=24), approval_status="APPROVED")["requests"] == []


def test_another_orgs_pending_requests_are_never_pulled_in_by_the_open_rule(retention):
    register(retention["theirs"], "theirs_agent")
    submit("theirs_agent")
    assert requests_in(retention["ours"], since=ago(hours=24))["requests"] == []


def test_pending_requests_sort_first_so_the_limit_cannot_crowd_them_out(retention):
    register(retention["ours"], "ours_agent")
    pending = submit("ours_agent")
    backdate("tool_requests", "request_id", pending["request_id"], "timestamp", ago(days=5))
    for _ in range(3):
        submit("ours_agent", "read_file")
    listed = requests_in(retention["ours"], since=ago(days=7), limit=2)
    assert listed["requests"][0]["request_id"] == pending["request_id"]
    assert listed["truncated"] is True and listed["count"] == 2


def test_a_list_that_fits_is_not_marked_truncated(retention):
    register(retention["ours"], "ours_agent")
    submit("ours_agent", "read_file")
    assert requests_in(retention["ours"], since=ago(days=1), limit=1)["truncated"] is False
    assert requests_in(retention["ours"], limit=1)["truncated"] is False


# --- Audit timeline ---------------------------------------------------------------------------

def timeline(token, since=None, until=None, event_type=None, limit=100):
    return api.administrator_audit_events(event_type=event_type, agent_name=None, limit=limit, x_admin_pin=token,
                                          since=since, until=until)


def test_the_audit_timeline_is_ranged_within_the_callers_org(retention):
    register(retention["ours"], "ours_agent")
    register(retention["theirs"], "theirs_agent")
    submit("ours_agent", "read_file")
    submit("theirs_agent", "read_file")
    with db_compat.connect(database.database_path) as connection:
        connection.execute("UPDATE audit_events SET timestamp = ? WHERE org_id = ?", (ago(days=20), organizations.DEFAULT_ORG_ID))
    ranged = timeline(retention["ours"], since=ago(days=7), event_type="POLICY")
    assert ranged["events"] == [] and ranged["range"]["since"]
    assert timeline(retention["ours"], since=ago(days=30), event_type="POLICY")["events"]
    theirs = timeline(retention["theirs"], since=ago(days=7))["events"]
    assert theirs and {e["org_id"] for e in theirs} == {retention["other_org"]}


def test_the_audit_timeline_reports_truncation(retention):
    register(retention["ours"], "ours_agent")
    for _ in range(3):
        submit("ours_agent", "read_file")
    assert timeline(retention["ours"], since=ago(days=1), event_type="POLICY", limit=2)["truncated"] is True
    assert timeline(retention["ours"], since=ago(days=1), event_type="POLICY", limit=50)["truncated"] is False


# --- Alerts -----------------------------------------------------------------------------------

def alert_list(token, since=None):
    return api.administrator_alerts(status=None, severity=None, agent_name=None, limit=100, x_admin_pin=token,
                                    since=since, until=None)


def test_unresolved_alerts_stay_visible_and_resolved_ones_follow_the_range(retention):
    register(retention["ours"], "ours_agent")
    register(retention["theirs"], "theirs_agent")
    submit("ours_agent", "send_email")
    submit("ours_agent", "send_email")
    submit("theirs_agent", "send_email")
    first, second = alert_list(retention["ours"])["alerts"][:2]
    api.administrator_update_alert(second["alert_id"], api.AlertUpdateRequest(status="RESOLVED", note="done"), retention["ours"])
    for alert in (first, second):
        backdate("security_alerts", "alert_id", alert["alert_id"], "created_at", ago(days=30))

    ranged = alert_list(retention["ours"], since=ago(days=7))
    ids = {a["alert_id"] for a in ranged["alerts"]}
    assert first["alert_id"] in ids and second["alert_id"] not in ids
    assert {a["org_id"] for a in ranged["alerts"]} == {organizations.DEFAULT_ORG_ID}
    # The other org's open alert is open too, and is still never shown to us.
    assert all(a["agent_name"] == "theirs_agent" for a in alert_list(retention["theirs"], since=ago(days=7))["alerts"])


# --- Authorization and HTTP -------------------------------------------------------------------

@pytest.fixture()
def client(retention):
    from fastapi.testclient import TestClient
    return TestClient(api.app, raise_server_exceptions=False)


@pytest.mark.parametrize("path", ["/tool-requests", "/audit-events", "/alerts"])
def test_unauthenticated_callers_get_401_before_any_range_validation(client, path):
    response = client.get(path, params={"since": "garbage"})
    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/tool-requests", "/audit-events", "/alerts"])
def test_bad_ranges_are_422_over_http(retention, client, path):
    headers = {"X-Admin-Pin": retention["ours"]}
    assert client.get(path, params={"since": "garbage"}, headers=headers).status_code == 422
    assert client.get(path, params={"since": "x" * 65}, headers=headers).status_code == 422
    assert client.get(path, params={"until": "2026-10-16T00:00:00Z"}, headers=headers).status_code == 422
    assert client.get(path, params={"since": ago(days=MAX_LOOKBACK_DAYS + 5)}, headers=headers).status_code == 422
    ok = client.get(path, params={"since": ago(days=1)}, headers=headers)
    assert ok.status_code == 200 and ok.json()["range"]["since"]


def test_an_auditor_reads_ranged_evidence_for_their_own_org_only(retention):
    register(retention["ours"], "ours_agent")
    register(retention["theirs"], "theirs_agent")
    submit("ours_agent", "read_file")
    submit("theirs_agent", "read_file")
    auditor = admin_auth.create_administrator("auditor@greyguard.local", "Auditor", "AUDITOR", PASSWORD)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, auditor["admin_id"], "AUDITOR", "MEMBER")
    token = admin_auth.authenticate(auditor["email"], PASSWORD)["access_token"]
    listed = requests_in(token, since=ago(days=1))["requests"]
    assert listed and {r["agent_name"] for r in listed} == {"ours_agent"}
    events = timeline(token, since=ago(days=1))["events"]
    assert events and {e["org_id"] for e in events} == {organizations.DEFAULT_ORG_ID}
