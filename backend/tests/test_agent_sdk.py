\
from typing import Any

import pytest

from backend.sdk import GreyGuardAdminClient, GreyGuardAgentClient


class RecordingTransport:
    def __init__(self, response: Any = None):
        self.response = {} if response is None else response
        self.calls: list[dict[str, Any]] = []

    def __call__(self, method, url, headers, payload, timeout):
        self.calls.append({
            "method": method, "url": url, "headers": headers,
            "payload": payload, "timeout": timeout,
        })
        return self.response


def test_agent_client_redacts_credential():
    client = GreyGuardAgentClient(
        "http://localhost:8000", "research_agent", "secret-key",
        transport=RecordingTransport(),
    )
    assert "secret-key" not in repr(client)
    assert "<redacted>" in repr(client)


def test_admin_client_redacts_pin():
    client = GreyGuardAdminClient(
        "http://localhost:8000", "2468-secret", transport=RecordingTransport()
    )
    assert "2468-secret" not in repr(client)
    assert "<redacted>" in repr(client)


def test_agent_identity_headers_are_sent():
    transport = RecordingTransport({"policy_decision": "ALLOW"})
    client = GreyGuardAgentClient(
        "http://localhost:8000", "research_agent", "agent-key", transport=transport
    )
    client.evaluate_action("read_file")
    call = transport.calls[0]
    assert call["headers"]["x-agent-name"] == "research_agent"
    assert call["headers"]["x-agent-key"] == "agent-key"
    assert call["payload"]["action"] == "read_file"


def test_tool_request_is_structured_safely():
    transport = RecordingTransport({"request_id": "request-1"})
    client = GreyGuardAgentClient(
        "http://localhost:8000", "notes_agent", "agent-key", transport=transport
    )
    client.request_tool(
        "write_note", "notes/report.txt", {"content": "Safe report"}, True
    )
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/tool-requests")
    assert call["payload"]["dry_run"] is True


def test_admin_registration_uses_admin_identity():
    transport = RecordingTransport({"credential": "issued-once"})
    client = GreyGuardAdminClient(
        "http://localhost:8000", "admin-pin", transport=transport
    )
    result = client.register_agent("new_agent", ["read_file", "list_files"])
    assert transport.calls[0]["headers"]["x-admin-pin"] == "admin-pin"
    assert result["credential"] == "issued-once"


def test_invalid_approval_decision_is_rejected():
    client = GreyGuardAdminClient(
        "http://localhost:8000", "admin-pin", transport=RecordingTransport()
    )
    with pytest.raises(ValueError, match="APPROVED or DENIED"):
        client.decide_tool_request("request-1", "maybe")


def test_empty_agent_credential_is_rejected():
    with pytest.raises(ValueError, match="credential"):
        GreyGuardAgentClient("http://localhost:8000", "agent", "")


def test_request_tool_sends_idempotency_key_header():
    transport = RecordingTransport({"request_id": "request-1"})
    client = GreyGuardAgentClient(
        "http://localhost:8000", "notes_agent", "agent-key", transport=transport
    )
    client.request_tool("write_note", idempotency_key="a-stable-key-123")
    assert transport.calls[0]["headers"]["Idempotency-Key"] == "a-stable-key-123"


def test_request_tool_without_idempotency_key_omits_header():
    transport = RecordingTransport({"request_id": "request-1"})
    client = GreyGuardAgentClient(
        "http://localhost:8000", "notes_agent", "agent-key", transport=transport
    )
    client.request_tool("write_note")
    assert "Idempotency-Key" not in transport.calls[0]["headers"]


def test_request_tool_rejects_short_idempotency_key():
    client = GreyGuardAgentClient(
        "http://localhost:8000", "notes_agent", "agent-key", transport=RecordingTransport()
    )
    with pytest.raises(ValueError, match="idempotency_key"):
        client.request_tool("write_note", idempotency_key="short")
