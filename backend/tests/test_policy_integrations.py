import pytest

from backend.app import policy_control, policy_integrations


@pytest.fixture
def integration_database(tmp_path, monkeypatch):
    database = tmp_path / "integrations.db"
    monkeypatch.setattr(policy_control, "database_path", database)
    monkeypatch.setattr(policy_integrations, "database_path", database)
    policy_control.initialize_policy_control({"read_file": "ALLOW"}, {"read_file": 0}, 3, 100)
    policy_integrations.initialize_policy_integrations()
    return policy_control.get_published_policy()


def test_adapters_are_disabled_by_default(integration_database):
    adapters = policy_integrations.list_policy_adapters()
    assert {item["adapter_type"] for item in adapters} == {"OPA", "CEDAR", "CERBOS"}
    assert all(item["enabled"] is False for item in adapters)
    assert all(item["credentials_stored"] is False for item in adapters)


def test_enabled_adapter_requires_https_owner_and_purpose(integration_database):
    with pytest.raises(ValueError, match="HTTPS"):
        policy_integrations.configure_policy_adapter("OPA", True, "http://opa", "owner", "policy checks", "admin")
    configured = policy_integrations.configure_policy_adapter("OPA", True, "https://opa.example.test", "security", "policy checks", "admin")
    assert configured["enabled"] is True


def test_signed_bundle_detects_tampering(integration_database, monkeypatch):
    monkeypatch.setenv("GREYGUARD_POLICY_SIGNING_KEY", "a-secure-development-key-of-at-least-32-characters")
    bundle = policy_integrations.export_signed_policy_bundle(integration_database["policy_id"])
    assert policy_integrations.verify_signed_policy_bundle(bundle)["valid"] is True
    bundle["document"]["policy"]["max_risk_score"] = 999
    assert policy_integrations.verify_signed_policy_bundle(bundle)["valid"] is False


def test_staged_rollout_is_deterministic_and_allowlisted(integration_database):
    draft = policy_control.create_policy_draft({"read_file": "BLOCK"}, {"read_file": 20}, 3, 100, "Staged deny", "analyst")
    policy_control.submit_policy(draft["policy_id"], "analyst")
    rollout = policy_integrations.create_rollout(draft["policy_id"], 0, ["agent-a"], "owner")
    assert rollout["status"] == "ACTIVE"
    assert policy_integrations.effective_rollout_policy("agent-a")["policy_id"] == draft["policy_id"]
    assert policy_integrations.effective_rollout_policy("agent-b") is None
    updated = policy_integrations.update_rollout(rollout["rollout_id"], "PAUSED", 0, "owner")
    assert updated["status"] == "PAUSED"

