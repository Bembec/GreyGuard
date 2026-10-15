import pytest

from backend.app import adapter_control


@pytest.fixture()
def adapters(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter_control, "database_path", tmp_path / "adapters.db")
    adapter_control.AVAILABLE_ACTIONS = set()
    adapter_control.initialize_adapter_control(["read_file", "write_note"])
    return adapter_control


def test_adapters_are_disabled_by_default(adapters):
    records = adapters.list_adapters("org_default")
    assert {item["adapter_id"] for item in records} == {
        "generic_webhook", "agentguard_legacy", "mcp_gateway", "langchain",
        "langgraph", "crewai", "autogen",
    }
    assert all(item["enabled"] is False for item in records)
    assert all(item["manifest"]["network_egress"] is False for item in records)


def test_kill_switch_blocks_translation(adapters):
    with pytest.raises(PermissionError, match="kill switch"):
        adapters.translate_request("generic_webhook", {"action": "read_file"}, "org_default")


def test_enabled_adapter_requires_owner_and_purpose(adapters):
    with pytest.raises(ValueError, match="named owner"):
        adapters.configure_adapter(
            "generic_webhook", True, "", "short", ["read_file"], "admin", "org_default"
        )


def test_manifest_rejects_unavailable_action(adapters):
    with pytest.raises(ValueError, match="subset"):
        adapters.configure_adapter(
            "generic_webhook", False, "owner", "Approved inbound integration",
            ["send_email"], "admin", "org_default",
        )


def test_translation_redacts_sensitive_fields(adapters):
    adapters.configure_adapter(
        "generic_webhook", True, "Security Team",
        "Controlled inbound read requests", ["read_file"], "admin", "org_default",
    )
    translated = adapters.translate_request("generic_webhook", {
        "action": "read_file", "target": "report.txt",
        "payload": {"api_key": "exposed", "safe": "visible"},
        "dry_run": True,
    }, "org_default")
    assert translated["payload"] == {"api_key": "[REDACTED]", "safe": "visible"}
    assert translated["dry_run"] is True


def test_test_environment_has_no_side_effects(adapters):
    result = adapters.test_adapter("agentguard_legacy", "org_default")
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
        ["read_file"], "admin", "org_default",
    )
    translated = adapters.translate_request(adapter_id, payload, "org_default")
    assert translated["action"] == "read_file"
    assert isinstance(translated["payload"], dict)


def test_every_adapter_isolated_test_is_side_effect_free(adapters):
    for adapter in adapters.list_adapters("org_default"):
        result = adapters.test_adapter(adapter["adapter_id"], "org_default")
        assert result["simulated"] is True
        assert result["network_used"] is False
        assert result["request_persisted"] is False


def test_autogen_rejects_malformed_argument_json(adapters):
    adapters.configure_adapter(
        "autogen", True, "Security Team", "Approved AutoGen integration",
        ["read_file"], "admin", "org_default",
    )
    with pytest.raises(ValueError, match="valid JSON"):
        adapters.translate_request("autogen", {
            "function_call": {"name": "read_file", "arguments": "not-json"}
        }, "org_default")


def test_adapters_are_isolated_per_organization(adapters):
    adapters.configure_adapter(
        "generic_webhook", True, "Security Team", "Approved inbound integration",
        ["read_file"], "admin", "org_a",
    )
    assert adapters.get_adapter("generic_webhook", "org_a")["enabled"] is True
    assert adapters.get_adapter("generic_webhook", "org_default")["enabled"] is False


def test_a_new_org_gets_the_installs_actions_and_can_configure_and_test_adapters(adapters):
    """Orgs other than the default were seeded with no allowed actions, so their adapters could
    never be configured, and testing one crashed."""
    org = "org_tenant"
    assert all(item["allowed_actions"] == ["read_file", "write_note"] for item in adapters.list_adapters(org))
    adapters.configure_adapter("generic_webhook", True, "Security", "Inbound webhook for the pilot", ["read_file"], "admin", org)
    assert adapters.test_adapter("generic_webhook", org)


def test_orgs_seeded_before_the_fix_are_repaired_without_touching_configured_adapters(adapters):
    with adapters.sqlite3.connect(adapters.database_path) as connection:
        connection.execute("UPDATE adapter_configs SET allowed_actions_json='[]', org_id='org_old' WHERE adapter_id='langchain' AND org_id='org_default'")
    adapters.configure_adapter("crewai", False, "", "", ["write_note"], "admin", "org_default")
    adapters.initialize_adapter_control(["read_file", "write_note"])
    assert adapters.get_adapter("langchain", "org_old")["allowed_actions"] == ["read_file", "write_note"]
    assert adapters.get_adapter("crewai", "org_default")["allowed_actions"] == ["write_note"]
    # Testing an adapter that somehow has no actions is a clear 400-style error, not a crash.
    with adapters.sqlite3.connect(adapters.database_path) as connection:
        connection.execute("UPDATE adapter_configs SET allowed_actions_json='[]', updated_by='admin' WHERE adapter_id='autogen' AND org_id='org_default'")
    with pytest.raises(ValueError, match="no allowed actions"):
        adapters.test_adapter("autogen", "org_default")
