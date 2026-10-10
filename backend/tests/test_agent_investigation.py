import pytest

from backend.app import agent_investigation


def test_investigation_curates_evidence_and_redacts_payloads(monkeypatch):
    monkeypatch.setattr(agent_investigation.main, "normalize_agent_name", lambda value: value.lower())
    monkeypatch.setattr(agent_investigation.main, "get_agent_state", lambda _name: {"agent_status": "ACTIVE", "risk_score": 12, "blocked_attempts": 1})
    monkeypatch.setattr(agent_investigation.main, "get_risk_level", lambda _score: "MEDIUM")
    monkeypatch.setattr(agent_investigation.main, "get_public_agent_identity", lambda _name: {"credential_status": "ACTIVE", "scopes": ["read_file"]})
    monkeypatch.setattr(agent_investigation, "get_administrator_audit_events", lambda **_kwargs: {"events": [{"event_id": "policy-1", "event_type": "POLICY", "timestamp": "now", "action": "read_file", "outcome": "ALLOW", "severity": "INFO", "summary": "Allowed", "details": {"risk_added": 2, "risk_score": 12, "risk_level": "MEDIUM", "secret": "hidden"}}]})
    monkeypatch.setattr(agent_investigation, "get_tool_requests", lambda **_kwargs: [{"request_id": "req_1", "timestamp": "now", "action": "read_file", "target": "report.txt", "policy_decision": "ALLOW", "approval_status": "NOT_REQUIRED", "execution_status": "SUCCEEDED", "risk_added": 2, "risk_score": 12, "payload_json": {"secret": "hidden"}}])
    result = agent_investigation.build_agent_investigation("Research-Agent", org_id="org_default")
    assert result["agent"]["agent_name"] == "research-agent"
    assert result["summary"]["requests"] == 1
    assert "hidden" not in str(result)


def test_investigation_preserves_missing_agent_failure(monkeypatch):
    monkeypatch.setattr(agent_investigation.main, "normalize_agent_name", lambda value: value)
    monkeypatch.setattr(agent_investigation.main, "get_agent_state", lambda _name: (_ for _ in ()).throw(KeyError("missing")))
    with pytest.raises(KeyError):
        agent_investigation.build_agent_investigation("missing", org_id="org_default")
