"""P7.5 Control Graph: exact decision provenance, the read-only graph, and the impact preview.

Owner decisions of 2026-10-16 these tests hold the code to:
1. 30 days by default; other ranges only within retained data.
2. Every new request records its exact policy version, a stable matched rule id, the rule's name and
   type, the outcome, and fingerprints to verify it later. Older requests stay "inferred".
3. Auditors may use the impact preview, only for their own org's records, and can change nothing.
Plus: tenant isolation on every node, and evidence immutability and retention not weakened.
"""
import hashlib
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import (
    admin_auth, alerts, api, audit_integrity, control_graph, database, db_compat, decision_provenance, main,
    organizations, policy_control,
)
from backend.tests.test_agent_tenancy import PASSWORD, register, submit, tenants  # noqa: F401  (fixture)


@pytest.fixture()
def world(tenants, monkeypatch):  # noqa: F811
    for module in (audit_integrity, decision_provenance, control_graph):
        monkeypatch.setattr(module, "database_path", database.database_path)
    decision_provenance.initialize_decision_provenance()
    alerts.initialize_alert_database()  # as the API's startup does
    return tenants


def records(org_id=organizations.DEFAULT_ORG_ID):
    with db_compat.connect(database.database_path) as connection:
        connection.row_factory = db_compat.Row
        return {row["request_id"]: dict(row) for row in connection.execute("SELECT * FROM decision_records WHERE org_id = ?", (org_id,))}


def graph(token, agent="ours_agent", **kwargs):
    params = {"depth": 2, "limit": 200, "since": None, "until": None, **kwargs}
    return api.agent_control_graph(agent, x_admin_pin=token, **params)


def preview(token, change, target=None, agent="ours_agent"):
    return api.agent_impact_preview(agent, change=change, target=target, x_admin_pin=token)


def make_auditor(org_id=organizations.DEFAULT_ORG_ID):
    auditor = admin_auth.create_administrator("auditor@greyguard.local", "Auditor", "AUDITOR", PASSWORD)
    organizations.ensure_membership(org_id, auditor["admin_id"], "AUDITOR", "MEMBER")
    return admin_auth.authenticate(auditor["email"], PASSWORD)["access_token"]


def publish(permissions_change, org_id=organizations.DEFAULT_ORG_ID):
    current = policy_control.get_published_policy(org_id=org_id)
    draft = policy_control.create_policy_draft(
        {**current["permissions"], **permissions_change}, current["risk_weights"], current["max_blocked_attempts"],
        current["max_risk_score"], "test change", "author", org_id=org_id)
    policy_control.submit_policy(draft["policy_id"], "author", org_id=org_id)
    return policy_control.approve_policy(draft["policy_id"], "reviewer", org_id=org_id)


def edge_for(result, request_id, kind="decided_by"):
    return next(edge for edge in result["edges"] if edge["from"] == f"request:{request_id}" and edge["kind"] == kind)


# --- Exact provenance ------------------------------------------------------------------------------

def test_every_new_request_records_the_exact_policy_version_and_rule(world):
    register(world["ours"], "ours_agent")
    published = policy_control.get_published_policy(org_id=organizations.DEFAULT_ORG_ID)
    allowed, asked, blocked = submit("ours_agent", "read_file"), submit("ours_agent"), submit("ours_agent", "send_email")
    stored = records()
    for request, outcome in ((allowed, "ALLOW"), (asked, "ASK"), (blocked, "BLOCK")):
        record = stored[request["request_id"]]
        assert record["outcome"] == outcome == request["policy_decision"]
        assert record["policy_source"] == "PUBLISHED"
        assert record["policy_version_id"] == published["policy_id"]
        assert record["policy_version_number"] == published["version_number"]
        assert record["matched_rule_id"] == f"permission:{request['action']}"
        assert record["rule_type"] == "PERMISSION"
        assert json.loads(record["rule_snapshot_json"])["decision"] == outcome
        assert record["policy_fingerprint"] == decision_provenance.policy_fingerprint(published)
        assert record["record_fingerprint"] == decision_provenance.record_fingerprint(record)


def test_an_unlisted_action_records_the_default_rule(world):
    register(world["ours"], "ours_agent")
    request = main.submit_tool_request("ours_agent", "launch_rockets", "", {})
    record = records()[request["request_id"]]
    assert (record["outcome"], record["matched_rule_id"], record["rule_type"]) == ("BLOCK", "default:unlisted_action", "DEFAULT_RULE")


@pytest.mark.parametrize("control, rule_id", [
    ({"global_deny": True}, "emergency:global_deny"),
    ({"disabled_tools": ["read_file"]}, "emergency:disabled_tool:read_file"),
    ({"disabled_agents": ["ours_agent"]}, "emergency:disabled_agent:ours_agent"),
])
def test_emergency_refusals_record_the_control_not_a_policy(world, control, rule_id):
    register(world["ours"], "ours_agent")
    policy_control.update_emergency_controls(control.get("global_deny", False), control.get("disabled_agents", []),
                                             control.get("disabled_tools", []), [], "test", org_id=organizations.DEFAULT_ORG_ID)
    request = submit("ours_agent", "read_file")
    record = records()[request["request_id"]]
    assert (record["outcome"], record["rule_type"], record["matched_rule_id"]) == ("REFUSED", "EMERGENCY_CONTROL", rule_id)
    assert record["policy_version_id"] is None and record["policy_fingerprint"] is None


def test_agents_never_receive_policy_internals(world):
    register(world["ours"], "ours_agent")
    result = main.evaluate_action("ours_agent", "read_file")
    assert not {"matched_rule_id", "policy_fingerprint", "policy_version_id", "rule_snapshot"} & set(result)


def test_decision_records_are_append_only_but_deletable_for_retention(world):
    register(world["ours"], "ours_agent")
    request = submit("ours_agent", "read_file")
    with pytest.raises(Exception, match="append-only"):
        with db_compat.connect(database.database_path) as connection:
            connection.execute("UPDATE decision_records SET outcome = 'ALLOW' WHERE request_id = ? AND org_id = ?",
                               (request["request_id"], organizations.DEFAULT_ORG_ID))
    assert records()[request["request_id"]]["outcome"] == "ALLOW"
    with db_compat.connect(database.database_path) as connection:
        connection.execute("DELETE FROM decision_records WHERE request_id = ? AND org_id = ?",
                           (request["request_id"], organizations.DEFAULT_ORG_ID))
    assert request["request_id"] not in records()


def test_the_audit_chain_still_verifies_after_requests_are_recorded(world):
    register(world["ours"], "ours_agent")
    audit_integrity.initialize_audit_integrity()
    submit("ours_agent", "read_file")
    audit_integrity.seal_audit_events()
    submit("ours_agent", "send_email")
    audit_integrity.seal_audit_events()
    assert audit_integrity.verify_integrity("test")["valid"] is True


# --- Historical evidence ---------------------------------------------------------------------------

def test_an_old_decision_still_points_at_the_version_that_made_it(world):
    register(world["ours"], "ours_agent")
    v1 = policy_control.get_published_policy(org_id=organizations.DEFAULT_ORG_ID)
    before = submit("ours_agent", "read_file")
    v2 = publish({"read_file": "BLOCK"})
    after = submit("ours_agent", "read_file")
    result = graph(world["ours"])
    old, new = edge_for(result, before["request_id"]), edge_for(result, after["request_id"])
    assert old["to"] == f"policy:{v1['policy_id']}" and old["basis"] == "recorded" and old["outcome"] == "ALLOW"
    assert new["to"] == f"policy:{v2['policy_id']}" and new["basis"] == "recorded" and new["outcome"] == "BLOCK"
    assert old["record_intact"] and old["policy_matches"] is True


def test_a_changed_policy_record_no_longer_matches_the_decision_fingerprint(world):
    register(world["ours"], "ours_agent")
    v1 = policy_control.get_published_policy(org_id=organizations.DEFAULT_ORG_ID)
    request = submit("ours_agent", "read_file")
    # Someone with database access rewrites the stored policy after the fact.
    with db_compat.connect(database.database_path) as connection:
        connection.execute("UPDATE policy_versions SET permissions_json = ? WHERE policy_id = ? AND org_id = ?",
                           (json.dumps({**v1["permissions"], "read_file": "BLOCK"}), v1["policy_id"], organizations.DEFAULT_ORG_ID))
    edge = edge_for(graph(world["ours"]), request["request_id"])
    assert edge["basis"] == "recorded" and edge["outcome"] == "ALLOW"
    assert edge["record_intact"] is True and edge["policy_matches"] is False


def test_a_tampered_record_fails_its_own_fingerprint(world):
    register(world["ours"], "ours_agent")
    request = submit("ours_agent", "read_file")
    record = decision_provenance.get_decision_records([request["request_id"]], org_id=organizations.DEFAULT_ORG_ID)[request["request_id"]]
    assert decision_provenance.verify_record(record, org_id=organizations.DEFAULT_ORG_ID)["record_intact"] is True
    forged = {**record, "outcome": "BLOCK"}
    assert decision_provenance.verify_record(forged, org_id=organizations.DEFAULT_ORG_ID)["record_intact"] is False


def test_requests_without_a_record_are_labelled_inferred_never_recorded(world):
    register(world["ours"], "ours_agent")
    v1 = policy_control.get_published_policy(org_id=organizations.DEFAULT_ORG_ID)
    legacy = submit("ours_agent", "read_file")
    # A request decided before decision records existed has none.
    with db_compat.connect(database.database_path) as connection:
        connection.execute("DELETE FROM decision_records WHERE request_id = ? AND org_id = ?",
                           (legacy["request_id"], organizations.DEFAULT_ORG_ID))
    result = graph(world["ours"])
    edge = edge_for(result, legacy["request_id"])
    assert edge["basis"] == "inferred" and edge["to"] == f"policy:{v1['policy_id']}"
    assert "record_intact" not in edge and "Inferred" in edge["note"]
    assert result["decision_basis"]["inferred"] == 1 and result["decision_basis"]["recorded"] == 0


# --- Tenant isolation ------------------------------------------------------------------------------

def test_another_orgs_agent_is_a_404_for_the_graph_and_the_preview(world):
    register(world["theirs"], "theirs_agent")
    for call in (lambda: graph(world["ours"], agent="theirs_agent"),
                 lambda: preview(world["ours"], "revoke_credential", agent="theirs_agent")):
        with pytest.raises(HTTPException) as error:
            call()
        assert error.value.status_code == 404


def test_no_node_from_another_org_is_ever_joined_in(world):
    register(world["ours"], "ours_agent")
    register(world["theirs"], "theirs_agent")
    ours = submit("ours_agent")  # ASK
    submit("theirs_agent", "send_email")
    # Another org's evidence that names our request id: an approval and an alert.
    with db_compat.connect(database.database_path) as connection:
        connection.execute("INSERT INTO approval_events (request_id, timestamp, actor, decision, note, org_id) VALUES (?, ?, ?, ?, ?, ?)",
                           (ours["request_id"], ours["timestamp"], "intruder", "APPROVED", "x", world["other_org"]))
        connection.execute(
            "INSERT INTO security_alerts (alert_id, source_event_id, created_at, updated_at, agent_name, request_id, event_type, outcome, "
            "severity, status, title, summary, evidence_json, org_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("alert_foreign", "src_foreign", ours["timestamp"], ours["timestamp"], "ours_agent", ours["request_id"], "POLICY",
             "BLOCK", "HIGH", "OPEN", "Foreign alert", "x", "{}", world["other_org"]))
    result = graph(world["ours"])
    labels = json.dumps(result)
    assert "intruder" not in labels and "alert_foreign" not in labels and "theirs_agent" not in labels
    assert result["agent"] == "ours_agent"


def test_install_level_alerts_are_withheld_and_counted_for_tenants(world):
    register(world["ours"], "ours_agent")
    with db_compat.connect(database.database_path) as connection:
        connection.execute(
            "INSERT INTO security_alerts (alert_id, source_event_id, created_at, updated_at, agent_name, request_id, event_type, outcome, "
            "severity, status, title, summary, evidence_json, org_id) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, NULL)",
            ("alert_install", "src_install", main.current_timestamp(), main.current_timestamp(), "ours_agent", "AUTHENTICATION",
             "AUTHENTICATION_FAILED", "HIGH", "OPEN", "Install-level alert", "x", "{}"))
    tenant_view = graph(world["ours"])
    assert tenant_view["withheld"]["install_level"] == 1
    assert "incident:alert_install" not in {node["id"] for node in tenant_view["nodes"]}
    operator = admin_auth.create_administrator("op@greyguard.local", "Op", "PLATFORM_ADMIN", PASSWORD, install_operator=True)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, operator["admin_id"], "PLATFORM_ADMIN", "OWNER")
    operator_view = graph(admin_auth.authenticate(operator["email"], PASSWORD)["access_token"])
    assert "incident:alert_install" in {node["id"] for node in operator_view["nodes"]}
    assert operator_view["withheld"]["install_level"] == 0


# --- Limits, window and content ---------------------------------------------------------------------

def test_depth_and_limit_are_enforced_and_truncation_is_reported(world):
    register(world["ours"], "ours_agent")
    asked = submit("ours_agent")
    api.review_tool_request(asked["request_id"], api.ToolApprovalDecision(decision="DENIED"), world["ours"])
    for _ in range(4):
        submit("ours_agent", "read_file")
    shallow = graph(world["ours"], depth=1)
    assert "approval" not in shallow["counts"] and "incident" not in shallow["counts"]
    assert graph(world["ours"])["counts"].get("approval") == 1
    small = graph(world["ours"], limit=6)
    assert len(small["nodes"]) <= 6 and small["truncated"] is True and small["dropped"]


def test_the_window_defaults_to_30_days_and_never_passes_retention(world):
    register(world["ours"], "ours_agent")
    result = graph(world["ours"])
    from datetime import datetime, timedelta, timezone
    since = datetime.fromisoformat(result["window"]["since"])
    assert timedelta(days=29, hours=23) < datetime.now(timezone.utc) - since < timedelta(days=30, minutes=1)
    audit_integrity.update_retention(30, False, "test")
    with pytest.raises(HTTPException) as error:
        graph(world["ours"], since=(datetime.now(timezone.utc) - timedelta(days=45)).isoformat())
    assert error.value.status_code == 422
    assert datetime.fromisoformat(graph(world["ours"])["window"]["retained_from"]) > datetime.now(timezone.utc) - timedelta(days=31)


def test_payloads_are_never_returned_and_targets_are_shortened(world):
    register(world["ours"], "ours_agent")
    main.submit_tool_request("ours_agent", "write_note", "n" * 300 + ".txt", {"content": "top-secret-payload"})
    text = json.dumps(graph(world["ours"]))
    assert "top-secret-payload" not in text and "n" * 100 not in text


# --- Impact preview --------------------------------------------------------------------------------

def test_the_preview_counts_what_a_change_would_stop(world):
    tokens = world
    api.register_agent_identity(api.AgentRegistration(agent_name="ours_agent", scopes=["read_file", "list_files"]), tokens["ours"])
    for _ in range(2):
        submit("ours_agent", "read_file")
    submit("ours_agent", "send_email")  # BLOCK: already refused, so not counted
    scope = preview(tokens["ours"], "revoke_scope", "read_file")
    assert scope["read_only"] is True and scope["unreachable_tools"] == ["read_file"]
    assert scope["affected_requests"]["count"] == 2 and "list_files" in scope["remaining_tools"]
    credential = preview(tokens["ours"], "revoke_credential")
    assert set(credential["unreachable_tools"]) == {"read_file", "list_files"} and credential["affected_requests"]["count"] == 2


@pytest.mark.parametrize("change, target", [("delete_everything", None), ("revoke_scope", "not_a_scope"), ("disable_tool", "nope")])
def test_the_preview_refuses_unknown_changes_and_targets(world, change, target):
    register(world["ours"], "ours_agent")
    with pytest.raises(HTTPException) as error:
        preview(world["ours"], change, target)
    assert error.value.status_code == 422


# --- Auditors: read-only, proven -------------------------------------------------------------------

def database_fingerprint():
    with db_compat.connect(database.database_path) as connection:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        digest = hashlib.sha256()
        for table in tables:
            if table in ("administrator_sessions", "rate_limit_counters", "observability_spans", "abuse_events", "product_analytics_events"):
                continue  # request bookkeeping that every authenticated call touches, not records
            # Read-only inventory of every table, org-scoped or not, for this test's before/after comparison.
            rows = connection.execute(f"SELECT * FROM {table} /* every org_id: test snapshot */").fetchall()  # nosec B608  # names come from sqlite_master
            digest.update(table.encode())
            digest.update(json.dumps(sorted(json.dumps(list(row), default=str) for row in rows)).encode())
        return digest.hexdigest()


def test_an_auditor_reads_the_graph_and_the_preview_and_changes_nothing(world):
    register(world["ours"], "ours_agent")
    submit("ours_agent", "read_file")
    submit("ours_agent")
    token = make_auditor()
    before = database_fingerprint()
    client = TestClient(api.app, raise_server_exceptions=False)
    headers = {"X-Admin-Pin": token}
    assert client.get("/agents/ours_agent/graph", headers=headers).status_code == 200
    for query in ("change=revoke_scope&target=read_file", "change=revoke_credential", "change=disable_tool&target=read_file"):
        response = client.get(f"/agents/ours_agent/impact-preview?{query}", headers=headers)
        assert response.status_code == 200 and response.json()["read_only"] is True
    assert database_fingerprint() == before


def test_an_auditor_cannot_mutate_through_direct_api_calls(world):
    register(world["ours"], "ours_agent")
    pending = submit("ours_agent")
    published = policy_control.get_published_policy(org_id=organizations.DEFAULT_ORG_ID)
    token = make_auditor()
    client = TestClient(api.app, raise_server_exceptions=False)
    headers = {"X-Admin-Pin": token}
    before = database_fingerprint()
    attempts = [
        ("post", "/policy-versions/drafts", {"permissions": published["permissions"], "risk_weights": published["risk_weights"],
                                            "max_blocked_attempts": 3, "max_risk_score": 100, "change_summary": "x"}),
        ("post", f"/policy-versions/{published['policy_id']}/approve", None),
        ("post", f"/policy-versions/{published['policy_id']}/rollback", None),
        ("post", f"/tool-requests/{pending['request_id']}/decision", {"decision": "APPROVED"}),
        ("post", "/agents/ours_agent/credential/revoke", None),
        ("put", "/policy-emergency-controls", {"global_deny": True, "disabled_agents": [], "disabled_tools": [], "disabled_integrations": []}),
        ("post", "/agents/ours_agent/graph", None),
        ("post", "/agents/ours_agent/impact-preview?change=revoke_credential", None),
    ]
    for method, path, body in attempts:
        response = getattr(client, method)(path, headers=headers, json=body)
        assert response.status_code in (403, 405), (path, response.status_code)
    assert database_fingerprint() == before
    assert database.get_tool_request(pending["request_id"], org_id=organizations.DEFAULT_ORG_ID)["approval_status"] == "PENDING"


def test_an_auditor_in_another_org_cannot_preview_our_agent(world):
    register(world["ours"], "ours_agent")
    token = make_auditor(world["other_org"])
    admin = admin_auth.get_administrator(admin_auth.validate_session(token)["admin_id"])
    organizations.switch_active_org(admin["admin_id"], world["other_org"], hashlib.sha256(token.encode()).hexdigest())
    client = TestClient(api.app, raise_server_exceptions=False)
    for path in ("/agents/ours_agent/graph", "/agents/ours_agent/impact-preview?change=revoke_credential"):
        assert client.get(path, headers={"X-Admin-Pin": token}).status_code == 404


def test_inference_compares_instants_at_the_requests_one_second_precision():
    versions = {
        "v1": {"policy_id": "v1", "version_number": 1, "status": "ARCHIVED", "published_at": "2026-10-16T09:00:00.100000+00:00"},
        "v2": {"policy_id": "v2", "version_number": 2, "status": "PUBLISHED", "published_at": "2026-10-16T10:00:00.900000+00:00"},
        "v3": {"policy_id": "v3", "version_number": 3, "status": "DRAFT", "published_at": None},
    }
    # The request's local time is 12:00:00+02:00 = 10:00:00 UTC, the same second v2 was published.
    assert control_graph._inferred_version(versions, "2026-10-16T12:00:00+02:00")["policy_id"] == "v2"
    assert control_graph._inferred_version(versions, "2026-10-16T11:59:59+02:00")["policy_id"] == "v1"
    assert control_graph._inferred_version(versions, "2026-10-16T08:59:59+00:00") is None
