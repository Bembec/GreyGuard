"""Security and reliability tests for the GreyGuard Python SDK."""

import pytest

from backend.app import main
from sdk.python.greyguard_sdk import (
    GreyGuardClient,
    RequestError,
    ScopeValidationError,
    ToolRequest,
    redact,
)


def test_client_repr_and_structured_logs_redact_credentials():
    client = GreyGuardClient(
        "http://greyguard.test",
        "agent-one",
        "gg_super_secret",
    )

    assert "gg_super_secret" not in repr(client)
    assert "[REDACTED]" in repr(client)
    assert redact(
        {
            "credential": "value",
            "nested": {"api_token": "token", "safe": "visible"},
        }
    ) == {
        "credential": "[REDACTED]",
        "nested": {"api_token": "[REDACTED]", "safe": "visible"},
    }


def test_declared_scope_blocks_request_before_transport():
    calls = []

    def transport(*args):
        calls.append(args)
        return 200, {}

    client = GreyGuardClient(
        "http://greyguard.test",
        "agent-one",
        "credential",
        scopes={"read_file"},
        transport=transport,
    )

    with pytest.raises(ScopeValidationError):
        client.submit(ToolRequest(action="delete_file"))

    assert calls == []


def test_submission_retry_reuses_one_idempotency_key(monkeypatch):
    calls = []

    def transport(method, url, headers, body, timeout):
        calls.append(headers.copy())
        if len(calls) == 1:
            return 503, {"detail": "temporarily unavailable"}
        return 201, {
            "request_id": "request-1",
            "action": "read_file",
            "execution_status": "COMPLETED",
        }

    monkeypatch.setattr(GreyGuardClient, "_backoff", staticmethod(lambda attempt: None))
    client = GreyGuardClient(
        "http://greyguard.test",
        "agent-one",
        "credential",
        transport=transport,
    )

    result = client.submit(ToolRequest(action="read_file"))

    assert result.request_id == "request-1"
    assert len(calls) == 2
    assert calls[0]["Idempotency-Key"] == calls[1]["Idempotency-Key"]


def test_policy_evaluation_is_not_retried():
    calls = []

    def transport(*args):
        calls.append(args)
        return 503, {"detail": "temporarily unavailable"}

    client = GreyGuardClient(
        "http://greyguard.test",
        "agent-one",
        "credential",
        max_retries=4,
        transport=transport,
    )

    with pytest.raises(RequestError):
        client.evaluate("read_file")

    assert len(calls) == 1


def test_existing_idempotent_request_skips_policy_evaluation(monkeypatch):
    existing = {
        "request_id": "idem_existing",
        "action": "read_file",
        "execution_status": "COMPLETED",
    }
    monkeypatch.setattr(main, "get_tool_request_details", lambda request_id, org_id: existing)

    def unexpected_evaluation(*args, **kwargs):
        raise AssertionError("duplicate request must not be evaluated again")

    monkeypatch.setattr(main, "evaluate_action", unexpected_evaluation)

    result = main.submit_tool_request(
        agent_name="agent-one",
        action="read_file",
        request_id="idem_existing",
    )

    assert result == existing
