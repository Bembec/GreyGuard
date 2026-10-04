import pytest

from backend.app import policy_control


@pytest.fixture
def policy_database(tmp_path, monkeypatch):
    database = tmp_path / "policy.db"
    monkeypatch.setattr(policy_control, "database_path", database)
    policy_control.initialize_policy_control(
        {"read_file": "ALLOW", "delete_file": "ASK", "send_email": "BLOCK"},
        {"read_file": 0, "delete_file": 20, "send_email": 40},
        3,
        100,
    )
    return policy_control.get_published_policy()


def test_policy_simulation_has_no_side_effects(policy_database):
    result = policy_control.simulate_policy(policy_database["policy_id"], "delete_file", current_risk=10)
    assert result["decision"] == "ASK"
    assert result["projected_risk"] == 30
    assert result["simulated"] is True
    assert result["side_effects"] is False


def test_unknown_action_fails_closed(policy_database):
    result = policy_control.simulate_policy(policy_database["policy_id"], "unknown_tool")
    assert result["decision"] == "BLOCK"
    assert result["risk_added"] == 40


def test_policy_test_cases_execute(policy_database):
    policy_control.add_policy_test_case(policy_database["policy_id"], "Delete asks", "delete_file", "ASK")
    policy_control.add_policy_test_case(policy_database["policy_id"], "Suspended refused", "read_file", "REFUSED", suspended=True)
    result = policy_control.run_policy_tests(policy_database["policy_id"])
    assert result["passed"] is True
    assert result["total"] == 2


def test_four_eyes_approval_blocks_creator(policy_database):
    draft = policy_control.create_policy_draft(
        policy_database["permissions"], policy_database["risk_weights"], 3, 100,
        "Require separate approval", "admin-one",
    )
    policy_control.submit_policy(draft["policy_id"], "admin-one")
    with pytest.raises(ValueError, match="Four-eyes"):
        policy_control.approve_policy(draft["policy_id"], "admin-one")
    approved = policy_control.approve_policy(draft["policy_id"], "admin-two")
    assert approved["status"] == "PUBLISHED"


def test_conflicts_and_emergency_controls(policy_database):
    draft = policy_control.create_policy_draft(
        {"read_file": "ALLOW", "dangerous": "ALLOW"},
        {"read_file": 0, "dangerous": 80}, 3, 100,
        "Conflict test", "analyst",
    )
    conflicts = policy_control.detect_policy_conflicts(draft["policy_id"])
    assert conflicts["conflict_count"] == 1
    state = policy_control.update_emergency_controls(True, ["agent-a"], ["dangerous"], ["webhook"], "owner")
    assert state["global_deny"] is True
    assert state["disabled_agents"] == ["agent-a"]

