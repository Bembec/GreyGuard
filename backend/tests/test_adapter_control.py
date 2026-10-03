import pytest

from backend.app import adapter_control


@pytest.fixture()
def adapters(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter_control, "database_path", tmp_path / "adapters.db")
    adapter_control.AVAILABLE_ACTIONS = set()
    adapter_control.initialize_adapter_control(["read_file", "write_note"])
    return adapter_control


def test_adapters_are_disabled_by_default(adapters):
    records = adapters.list_adapters()
    assert {item["adapter_id"] for item in records} == {
        "generic_webhook", "agentguard_legacy", "mcp_gateway", "langchain",
        "langgraph", "crewai", "autogen",
    }
    assert all(item["enabled"] is False for item in records)
    assert all(item["manifest"]["network_egress"] is False for item in records)


def test_kill_switch_blocks_translation(adapters):
    with pytest.raises(PermissionError, match="kill switch"):
        adapters.translate_request("generic_webhook", {"action": "read_file"})


def test_enabled_adapter_requires_owner_and_purpose(adapters):
    with pytest.raises(ValueError, match="named owner"):
        adapters.configure_adapter(
            "generic_webhook", True, "", "short", ["read_file"], "admin"
        )


def test_manifest_rejects_unavailable_action(adapters):
    with pytest.raises(ValueError, match="subset"):
        adapters.configure_adapter(
            "generic_webhook", False, "owner", "Approved inbound integration",
            ["send_email"], "admin",
        )


def test_translation_redacts_sensitive_fields(adapters):
    adapters.configure_adapter(
        "generic_webhook", True, "Security Team",
        "Controlled inbound read requests", ["read_file"], "admin",
    )
    translated = adapters.translate_request("generic_webhook", {
        "action": "read_file", "target": "report.txt",
        "payload": {"api_key": "exposed", "safe": "visible"},
        "dry_run": True,
    })
    assert translated["payload"] == {"api_key": "[REDACTED]", "safe": "visible"}
    assert translated["dry_run"] is True


def test_test_environment_has_no_side_effects(adapters):
    result = adapters.test_adapter("agentguard_legacy")
    assert result["status"] == "PASSED"
    assert result["simulated"] is True
    assert result["network_used"] is False
    assert result["request_persisted"] is False


@pytest.mark.parametrize(("adapter_id", "payload"), [
    ("mcp_gateway", {"name": "read_file", "arguments": {"target": "report.txt"}}),
    ("langchain", {"tool": "read_file", "input": {"query": "report"}}),
    ("langgraph", {"action": "read_file", "state": {"step": 1}}),
    ("crewai", {"tool": "read_file", "arguments": {"delegated": False}}),
    ("autogen", {"function_call": {"name": "read_file", "arguments": "{\"safe\": true}"}}),
])
def test_framework_translation(adapters, adapter_id, payload):
    adapters.configure_adapter(
        adapter_id, True, "Security Team", "Approved framework test adapter",
        ["read_file"], "admin",
    )
    translated = adapters.translate_request(adapter_id, payload)
    assert translated["action"] == "read_file"
    assert isinstance(translated["payload"], dict)


def test_every_adapter_isolated_test_is_side_effect_free(adapters):
    for adapter in adapters.list_adapters():
        result = adapters.test_adapter(adapter["adapter_id"])
        assert result["simulated"] is True
        assert result["network_used"] is False
        assert result["request_persisted"] is False


def test_autogen_rejects_malformed_argument_json(adapters):
    adapters.configure_adapter(
        "autogen", True, "Security Team", "Approved AutoGen integration",
        ["read_file"], "admin",
    )
    with pytest.raises(ValueError, match="valid JSON"):
        adapters.translate_request("autogen", {
            "function_call": {"name": "read_file", "arguments": "not-json"}
        })
