from backend.app import global_search


def test_search_requires_read_permission():
    assert global_search.search_control_plane("agent", [], 10)["results"] == []


def test_search_rejects_short_queries():
    assert global_search.search_control_plane("a", ["read"], 10)["count"] == 0


def test_search_combines_and_limits_sources(monkeypatch):
    monkeypatch.setattr(global_search.main, "agent_states", {"billing-agent": {"agent_status": "ACTIVE", "risk_score": 4}})
    monkeypatch.setattr(global_search.main, "get_agent_identity", lambda _name: {"scopes": ["read_file"], "org_id": "org_default"})
    monkeypatch.setattr(global_search, "get_tool_requests", lambda limit, org_id: [{"request_id": "req_1", "agent_name": "billing-agent", "action": "read_file", "target": "invoice.txt", "approval_status": "NOT_REQUIRED", "execution_status": "SUCCEEDED"}])
    monkeypatch.setattr(global_search, "get_alerts", lambda limit: {"alerts": []})
    monkeypatch.setattr(global_search, "get_administrator_audit_events", lambda limit, org_id: {"events": []})
    result = global_search.search_control_plane("billing", ["read"], 1)
    assert result["count"] == 1
    assert result["results"][0]["kind"] == "AGENT"


def test_search_does_not_return_raw_payloads(monkeypatch):
    monkeypatch.setattr(global_search.main, "agent_states", {})
    monkeypatch.setattr(global_search, "get_tool_requests", lambda limit, org_id: [{"request_id": "req_secret", "agent_name": "safe-agent", "action": "read_file", "target": "report.txt", "approval_status": "NOT_REQUIRED", "execution_status": "SUCCEEDED", "payload": {"secret": "never-return-this"}}])
    monkeypatch.setattr(global_search, "get_alerts", lambda limit: {"alerts": []})
    monkeypatch.setattr(global_search, "get_administrator_audit_events", lambda limit, org_id: {"events": []})
    result = global_search.search_control_plane("report", ["read"], 10)
    assert "never-return-this" not in str(result)


def test_search_only_returns_the_callers_orgs_agents_and_their_requests(monkeypatch):
    owners = {"ours-agent": "org_default", "theirs-agent": "org_other"}
    monkeypatch.setattr(global_search.main, "agent_states", {name: {"agent_status": "ACTIVE", "risk_score": 0} for name in owners})
    monkeypatch.setattr(global_search.main, "get_agent_identity", lambda name: {"scopes": [], "org_id": owners[name]} if name in owners else None)
    # Like the real query, the tool-request source is filtered by org_id in SQL.
    monkeypatch.setattr(global_search, "get_tool_requests", lambda limit, org_id: [
        {"request_id": f"req_{name}", "agent_name": name, "action": "read_file", "target": "agent-file",
         "approval_status": "NOT_REQUIRED", "execution_status": "SUCCEEDED"} for name in owners if owners[name] == org_id])
    monkeypatch.setattr(global_search, "get_alerts", lambda limit: {"alerts": []})
    monkeypatch.setattr(global_search, "get_administrator_audit_events", lambda limit, org_id: {"events": []})
    ids = {item["id"] for item in global_search.search_control_plane("agent", ["read"], 50, "org_default")["results"]}
    assert ids == {"ours-agent", "req_ours-agent"}
    ids = {item["id"] for item in global_search.search_control_plane("agent", ["read"], 50, "org_other")["results"]}
    assert ids == {"theirs-agent", "req_theirs-agent"}
