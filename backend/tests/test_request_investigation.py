from backend.app import request_investigation


def test_request_bundle_redacts_secrets(monkeypatch):
    monkeypatch.setattr(request_investigation, "get_tool_request_details", lambda _id: {
        "request_id": "req_1", "agent_name": "agent", "timestamp": "2026-01-01", "updated_at": "2026-01-01",
        "action": "read_file", "target": "report.txt", "dry_run": False, "policy_decision": "ALLOW",
        "approval_status": "NOT_REQUIRED", "execution_status": "SUCCEEDED", "risk_added": 0, "risk_score": 0,
        "executed_at": "2026-01-01", "payload": {"api_key": "secret-value"}, "result": {},
        "approval_events": [], "execution_events": [],
    })
    result = request_investigation.build_request_investigation("req_1")
    assert result["redacted_evidence"]["payload"]["api_key"] == "[REDACTED]"
    assert "secret-value" not in str(result)


def test_blocked_decision_has_explanation():
    assert "prevented execution" in request_investigation.explain_decision("BLOCK", "NOT_REQUIRED", "BLOCKED")
