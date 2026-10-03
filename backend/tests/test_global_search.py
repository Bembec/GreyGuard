from backend.app import global_search


def test_search_requires_read_permission():
    assert global_search.search_control_plane("agent", [], 10)["results"] == []


def test_search_rejects_short_queries():
    assert global_search.search_control_plane("a", ["read"], 10)["count"] == 0


def test_search_combines_and_limits_sources(monkeypatch):
    monkeypatch.setattr(global_search.main, "agent_states", {"billing-agent": {"agent_status": "ACTIVE", "risk_score": 4}})
    monkeypatch.setattr(global_search.main, "get_agent_identity", lambda _name: {"scopes": ["read_file"]})
    monkeypatch.setattr(global_search, "get_tool_requests", lambda limit: [{"request_id": "req_1", "agent_name": "billing-agent", "action": "read_file", "target": "invoice.txt", "approval_status": "NOT_REQUIRED", "execution_status": "SUCCEEDED"}])
    monkeypatch.setattr(global_search, "get_alerts", lambda limit: {"alerts": []})
    monkeypatch.setattr(global_search, "get_administrator_audit_events", lambda limit: {"events": []})
    result = global_search.search_control_plane("billing", ["read"], 1)
    assert result["count"] == 1
    assert result["results"][0]["kind"] == "AGENT"


def test_search_does_not_return_raw_payloads(monkeypatch):
    monkeypatch.setattr(global_search.main, "agent_states", {})
    monkeypatch.setattr(global_search, "get_tool_requests", lambda limit: [{"request_id": "req_secret", "agent_name": "safe-agent", "action": "read_file", "target": "report.txt", "approval_status": "NOT_REQUIRED", "execution_status": "SUCCEEDED", "payload": {"secret": "never-return-this"}}])
    monkeypatch.setattr(global_search, "get_alerts", lambda limit: {"alerts": []})
    monkeypatch.setattr(global_search, "get_administrator_audit_events", lambda limit: {"events": []})
    result = global_search.search_control_plane("report", ["read"], 10)
    assert "never-return-this" not in str(result)
