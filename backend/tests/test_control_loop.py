"""The core control loop the public site describes: ASK waits for a person, BLOCK adds risk and
counts toward suspension, and a suspended agent is refused everything.

These are the evidence for claims in website/content/claims.json, so each test states one
behaviour a buyer is told about.
"""
from backend.app import api, main
from backend.tests.test_agent_tenancy import register, submit, tenants  # noqa: F401  (fixture)


def test_an_ask_request_waits_for_a_person_and_does_not_run_until_approved(tenants):
    register(tenants["theirs"], "loop_agent")
    pending = submit("loop_agent")  # write_note is ASK by default
    assert pending["policy_decision"] == "ASK"
    assert pending["approval_status"] == "PENDING"
    assert pending["execution_status"] == "NOT_STARTED" and pending["executed_at"] is None

    decided = api.review_tool_request(pending["request_id"], api.ToolApprovalDecision(decision="APPROVED"), tenants["theirs"])
    assert decided["approval_status"] == "APPROVED"
    assert decided["executed_at"] is not None


def test_a_denied_request_never_runs(tenants):
    register(tenants["theirs"], "loop_agent")
    pending = submit("loop_agent")
    decided = api.review_tool_request(pending["request_id"], api.ToolApprovalDecision(decision="DENIED"), tenants["theirs"])
    assert decided["approval_status"] == "DENIED"
    assert decided["executed_at"] is None


def test_blocked_attempts_suspend_the_agent_and_a_suspended_agent_is_refused(tenants):
    register(tenants["theirs"], "loop_agent")
    limit = main.max_blocked_attempts
    for attempt in range(1, limit + 1):
        result = main.evaluate_action("loop_agent", "send_email")  # BLOCK by default
        assert result["policy_decision"] == "BLOCK"
        assert main.get_agent_state("loop_agent")["blocked_attempts"] == attempt
    assert main.get_agent_state("loop_agent")["agent_status"] == "SUSPENDED"
    # Once suspended, even an action policy would allow is refused.
    assert main.evaluate_action("loop_agent", "read_file")["policy_decision"] == "REFUSED"


def test_a_blocked_action_adds_its_risk_weight(tenants):
    register(tenants["theirs"], "loop_agent")
    before = main.get_agent_state("loop_agent")["risk_score"]
    result = main.evaluate_action("loop_agent", "send_email")
    assert result["risk_added"] == main.risk_weights["send_email"] > 0
    assert main.get_agent_state("loop_agent")["risk_score"] == before + result["risk_added"]


def test_an_identity_is_not_a_permission_an_ungranted_scope_is_denied(tenants):
    register(tenants["theirs"], "loop_agent")  # granted only read_file
    identity = {"agent_name": "loop_agent", "scopes": ["read_file"]}
    main.enforce_agent_scope(identity, "read_file")
    try:
        main.enforce_agent_scope(identity, "delete_file")
    except main.AgentScopeError:
        pass
    else:
        raise AssertionError("an action outside the agent's scopes was allowed")


def test_suspension_is_recoverable_by_an_administrator_reset(tenants):
    register(tenants["theirs"], "loop_agent")
    for _ in range(main.max_blocked_attempts):
        main.evaluate_action("loop_agent", "send_email")
    assert main.get_agent_state("loop_agent")["agent_status"] == "SUSPENDED"
    result = main.reset_agent("loop_agent")
    assert result["reset"] is True
    state = main.get_agent_state("loop_agent")
    assert state["agent_status"] == "ACTIVE" and state["risk_score"] == 0 and state["blocked_attempts"] == 0
    assert main.evaluate_action("loop_agent", "read_file")["policy_decision"] == "ALLOW"
