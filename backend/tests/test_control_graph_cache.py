"""FU-CG-01: the Control Graph's 15-second response cache (closes DEV-001).

Owner requirements, 2026-10-16: keys hold the tenant, the authorization scope, the user, the query
parameters and the data version; nothing is shared across users or tenants; invalidation, bounded
memory and expiry are defined; freshness-critical reads bypass it. Negative tests below.
"""
import hashlib

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import admin_auth, api, control_graph, database, db_compat, main, organizations, policy_control
from backend.tests.test_agent_tenancy import PASSWORD, register, submit, tenants  # noqa: F401  (fixture)
from backend.tests.test_control_graph import make_auditor, publish, world  # noqa: F401  (fixture)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture()
def cache(world, monkeypatch):  # noqa: F811
    clock = Clock()
    fresh = control_graph.GraphCache(clock=clock)
    monkeypatch.setattr(control_graph, "graph_cache", fresh)
    return {"world": world, "clock": clock, "cache": fresh}


def graph(token, agent="ours_agent", **kwargs):
    return api.agent_control_graph(agent, x_admin_pin=token, **{"depth": 2, "limit": 200, "since": None, "until": None, **kwargs})


def node_ids(result):
    return {node["id"] for node in result["nodes"]}


# --- Hits, expiry, bounds ----------------------------------------------------------------------

def test_a_repeat_within_15_seconds_is_served_from_the_cache(cache):
    register(cache["world"]["ours"], "ours_agent")
    submit("ours_agent", "read_file")
    first = graph(cache["world"]["ours"])
    cache["clock"].now += 14.9
    second = graph(cache["world"]["ours"])
    assert first["cache"]["hit"] is False and second["cache"]["hit"] is True
    assert second["nodes"] == first["nodes"]


def test_an_entry_expires_after_15_seconds(cache):
    register(cache["world"]["ours"], "ours_agent")
    graph(cache["world"]["ours"])
    cache["clock"].now += 15.0
    assert graph(cache["world"]["ours"])["cache"]["hit"] is False


def test_memory_is_bounded_and_the_least_recently_used_entry_goes_first():
    clock = Clock()
    bounded = control_graph.GraphCache(max_entries=3, clock=clock)
    for key in ("a", "b", "c"):
        bounded.put((key,), {"key": key})
    assert bounded.get(("a",)) is not None  # a is now the most recently used
    bounded.put(("d",), {"key": "d"})
    assert len(bounded) == 3 and bounded.get(("b",)) is None and bounded.get(("a",)) is not None
    clock.now += 20
    bounded.put(("e",), {"key": "e"})
    assert len(bounded) == 1  # expired entries are dropped, not kept until evicted


# --- Never stale after an application write ----------------------------------------------------

def test_a_new_request_is_shown_at_once(cache):
    register(cache["world"]["ours"], "ours_agent")
    graph(cache["world"]["ours"])
    request = submit("ours_agent", "read_file")
    fresh = graph(cache["world"]["ours"])
    assert fresh["cache"]["hit"] is False and f"request:{request['request_id']}" in node_ids(fresh)


def test_an_approval_in_the_same_second_is_shown_at_once(cache):
    register(cache["world"]["ours"], "ours_agent")
    pending = submit("ours_agent")
    graph(cache["world"]["ours"])
    api.review_tool_request(pending["request_id"], api.ToolApprovalDecision(decision="DENIED"), cache["world"]["ours"])
    fresh = graph(cache["world"]["ours"])
    assert fresh["cache"]["hit"] is False and fresh["counts"].get("approval") == 1


def test_an_incident_status_change_is_shown_at_once(cache):
    register(cache["world"]["ours"], "ours_agent")
    submit("ours_agent", "send_email")
    # Incidents are derived from evidence by the alert list (the graph itself never writes).
    api.administrator_alerts(status=None, severity=None, agent_name=None, limit=100, x_admin_pin=cache["world"]["ours"])
    alert = next(node for node in graph(cache["world"]["ours"])["nodes"] if node["type"] == "incident")
    api.administrator_update_alert(alert["id"].split(":", 1)[1], api.AlertUpdateRequest(status="INVESTIGATING", note="on it"),
                                   cache["world"]["ours"])
    fresh = graph(cache["world"]["ours"])
    assert fresh["cache"]["hit"] is False
    assert next(node for node in fresh["nodes"] if node["id"] == alert["id"])["status"] == "INVESTIGATING"


@pytest.mark.parametrize("change", ["emergency", "revoke", "scopes", "publish", "suspend"])
def test_security_relevant_changes_are_shown_at_once(cache, change):
    token = cache["world"]["ours"]
    register(token, "ours_agent")
    before = graph(token)
    if change == "emergency":
        policy_control.update_emergency_controls(True, [], [], [], "test", org_id=organizations.DEFAULT_ORG_ID)
    elif change == "revoke":
        api.revoke_credential("ours_agent", token)
    elif change == "scopes":
        api.update_agent_scopes("ours_agent", api.ScopeUpdate(scopes=["list_files"]), token)
    elif change == "publish":
        publish({"read_file": "BLOCK"})
    else:
        with db_compat.connect(database.database_path) as connection:
            connection.execute("UPDATE agent_runtime_states SET agent_status = 'SUSPENDED' WHERE agent_name = ? AND org_id = ?",
                               ("ours_agent", organizations.DEFAULT_ORG_ID))
    after = graph(token)
    assert after["cache"]["hit"] is False
    assert after["nodes"] != before["nodes"]


def test_a_retention_change_is_shown_at_once(cache):
    from backend.app import audit_integrity
    register(cache["world"]["ours"], "ours_agent")
    audit_integrity.update_retention(365, False, "test")
    before = graph(cache["world"]["ours"])
    audit_integrity.update_retention(30, False, "test")
    after = graph(cache["world"]["ours"])
    assert after["cache"]["hit"] is False
    assert after["window"]["retained_from"] > before["window"]["retained_from"]


# --- Never shared across people or tenants; authorization never cached --------------------------

def test_two_people_in_the_same_org_never_share_an_entry(cache):
    register(cache["world"]["ours"], "ours_agent")
    graph(cache["world"]["ours"])
    auditor = make_auditor()
    assert graph(auditor)["cache"]["hit"] is False
    assert len(cache["cache"]) == 2


def test_an_install_operators_graph_is_never_served_to_a_tenant(cache):
    register(cache["world"]["ours"], "ours_agent")
    with db_compat.connect(database.database_path) as connection:
        connection.execute(
            "INSERT INTO security_alerts (alert_id, source_event_id, created_at, updated_at, agent_name, request_id, event_type, outcome, "
            "severity, status, title, summary, evidence_json, org_id) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL)",
            ("alert_install", "src_install", main.current_timestamp(), main.current_timestamp(), "ours_agent", "AUTHENTICATION",
             "AUTHENTICATION_FAILED", "HIGH", "OPEN", "Install-level alert", "x", "{}"))
    operator = admin_auth.create_administrator("op@greyguard.local", "Op", "PLATFORM_ADMIN", PASSWORD, install_operator=True)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, operator["admin_id"], "PLATFORM_ADMIN", "OWNER")
    operator_view = graph(admin_auth.authenticate(operator["email"], PASSWORD)["access_token"])
    assert "incident:alert_install" in node_ids(operator_view)
    tenant_view = graph(make_auditor())
    assert tenant_view["cache"]["hit"] is False
    assert "incident:alert_install" not in node_ids(tenant_view) and tenant_view["withheld"]["install_level"] == 1


def test_two_people_with_the_same_role_never_share_an_entry(cache):
    register(cache["world"]["ours"], "ours_agent")
    graph(cache["world"]["ours"])
    second = admin_auth.create_administrator("second@greyguard.local", "Second", "PLATFORM_ADMIN", PASSWORD)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, second["admin_id"], "PLATFORM_ADMIN", "MEMBER")
    assert graph(admin_auth.authenticate(second["email"], PASSWORD)["access_token"])["cache"]["hit"] is False
    assert len(cache["cache"]) == 2


def install_level_alert():
    with db_compat.connect(database.database_path) as connection:
        connection.execute(
            "INSERT INTO security_alerts (alert_id, source_event_id, created_at, updated_at, agent_name, request_id, event_type, outcome, "
            "severity, status, title, summary, evidence_json, org_id) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL)",
            ("alert_install", "src_install", main.current_timestamp(), main.current_timestamp(), "ours_agent", "AUTHENTICATION",
             "AUTHENTICATION_FAILED", "HIGH", "OPEN", "Install-level alert", "x", "{}"))


def test_losing_install_operator_rights_hides_install_level_incidents_at_once(cache):
    register(cache["world"]["ours"], "ours_agent")
    install_level_alert()
    keeper = admin_auth.create_administrator("keeper@greyguard.local", "Keeper", "PLATFORM_ADMIN", PASSWORD, install_operator=True)
    operator = admin_auth.create_administrator("op@greyguard.local", "Op", "PLATFORM_ADMIN", PASSWORD, install_operator=True)
    for person in (keeper, operator):
        organizations.ensure_membership(organizations.DEFAULT_ORG_ID, person["admin_id"], "PLATFORM_ADMIN", "OWNER")
    token = admin_auth.authenticate(operator["email"], PASSWORD)["access_token"]
    assert "incident:alert_install" in node_ids(graph(token))
    # Same person, same role, same data: only the operator flag changes.
    admin_auth.update_administrator(operator["admin_id"], install_operator=False)
    after = graph(token)
    assert after["cache"]["hit"] is False
    assert "incident:alert_install" not in node_ids(after) and after["withheld"]["install_level"] == 1


def test_the_same_viewer_and_agent_under_another_org_never_hit(monkeypatch):
    """Defence in depth: an agent belongs to one org, so no route reaches this, but the key holds the org."""
    monkeypatch.setattr(control_graph, "graph_cache", control_graph.GraphCache(clock=Clock()))
    monkeypatch.setattr(control_graph, "data_version", lambda agent, org: ("same",))
    monkeypatch.setattr(control_graph, "permitted_lookback_days", lambda org: 400)
    built = []
    monkeypatch.setattr(control_graph, "build_control_graph", lambda agent, **kwargs: built.append(kwargs["org_id"]) or {"org": kwargs["org_id"]})
    viewer = {"admin_id": "adm", "role": "AUDITOR", "permissions": ["read"]}
    for org in ("org_a", "org_b"):
        assert control_graph.cached_control_graph("agent", org_id=org, viewer=viewer, window=None, depth=2, limit=200)["org"] == org
    assert built == ["org_a", "org_b"]


def test_another_org_is_refused_even_when_the_graph_is_cached(cache):
    register(cache["world"]["ours"], "ours_agent")
    graph(cache["world"]["ours"])
    with pytest.raises(HTTPException) as error:
        graph(cache["world"]["theirs"])
    assert error.value.status_code == 404


def test_an_auditor_who_moves_org_loses_access_at_once(cache):
    register(cache["world"]["ours"], "ours_agent")
    token = make_auditor()
    assert graph(token)["cache"]["hit"] is False
    assert graph(token)["cache"]["hit"] is True
    admin_id = admin_auth.validate_session(token)["admin_id"]
    organizations.ensure_membership(cache["world"]["other_org"], admin_id, "AUDITOR", "MEMBER")
    organizations.switch_active_org(admin_id, cache["world"]["other_org"], hashlib.sha256(token.encode()).hexdigest())
    with pytest.raises(HTTPException) as error:
        graph(token)
    assert error.value.status_code == 404


def test_a_signed_out_session_is_refused_even_when_the_graph_is_cached(cache):
    register(cache["world"]["ours"], "ours_agent")
    client = TestClient(api.app, raise_server_exceptions=False)
    headers = {"X-Admin-Pin": cache["world"]["ours"]}
    assert client.get("/agents/ours_agent/graph", headers=headers).json()["cache"]["hit"] is False
    assert client.get("/agents/ours_agent/graph", headers=headers).json()["cache"]["hit"] is True
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/agents/ours_agent/graph", headers=headers).status_code == 401


# --- Bypass ------------------------------------------------------------------------------------

def test_no_cache_from_the_client_always_rebuilds(cache):
    register(cache["world"]["ours"], "ours_agent")
    client = TestClient(api.app, raise_server_exceptions=False)
    headers = {"X-Admin-Pin": cache["world"]["ours"]}
    client.get("/agents/ours_agent/graph", headers=headers)
    bypassed = client.get("/agents/ours_agent/graph", headers={**headers, "Cache-Control": "no-cache"}).json()
    assert bypassed["cache"] == {"hit": False, "reason": "bypass requested"}


def test_an_explicit_window_is_never_cached(cache):
    from datetime import datetime, timedelta, timezone
    register(cache["world"]["ours"], "ours_agent")
    since = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    assert graph(cache["world"]["ours"], since=since)["cache"]["reason"] == "explicit window"
    assert len(cache["cache"]) == 0


def test_the_impact_preview_is_never_cached(cache):
    token = cache["world"]["ours"]
    api.register_agent_identity(api.AgentRegistration(agent_name="ours_agent", scopes=["read_file", "list_files"]), token)
    submit("ours_agent", "read_file")
    assert api.agent_impact_preview("ours_agent", change="revoke_scope", target="read_file", x_admin_pin=token)["affected_requests"]["count"] == 1
    submit("ours_agent", "read_file")
    assert api.agent_impact_preview("ours_agent", change="revoke_scope", target="read_file", x_admin_pin=token)["affected_requests"]["count"] == 2
