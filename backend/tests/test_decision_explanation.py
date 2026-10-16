"""P7.5 item 6: decision explainability, authentication assurance and secret-value redaction.

Owner decisions, 2026-10-16: explanations come from the exact decision record (or say plainly they
are inferred), use fixed sentences with no confidence score, record how the agent authenticated on
new decisions, redact values that look like secrets for every role, and explain why something is
unavailable from the viewer's own role only.
"""
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import api, database, db_compat, decision_provenance, main, organizations, policy_control
from backend.tests.test_agent_tenancy import register, submit, tenants  # noqa: F401  (fixture)
from backend.tests.test_control_graph import make_auditor, publish, world  # noqa: F401  (fixture)


def explain(token, request_id):
    return api.request_explanation(request_id, x_admin_pin=token)


@pytest.mark.parametrize("action, decision, rule_type, fragment", [
    ("read_file", "ALLOW", "PERMISSION", "Allowed because policy v1 allows read_file"),
    ("write_note", "ASK", "PERMISSION", "Held for human approval because policy v1 requires a reviewer for write_note"),
    ("send_email", "BLOCK", "PERMISSION", "Blocked because policy v1 does not allow send_email"),
    ("launch_rockets", "BLOCK", "DEFAULT_RULE", "launch_rockets is not listed in policy v1, and anything not listed is blocked"),
])
def test_policy_decisions_are_explained_exactly(world, action, decision, rule_type, fragment):
    register(world["ours"], "ours_agent")
    request = main.submit_tool_request("ours_agent", action, "x.txt", {"content": "x"})
    result = explain(world["ours"], request["request_id"])
    assert result["decision"] == decision and result["basis"] == "recorded"
    assert fragment in result["reason"]
    assert result["matched_rule"]["type"] == rule_type
    assert result["policy"]["basis"] == "recorded" and result["policy"]["version_number"] == 1
    assert result["integrity"] == {"record_intact": True, "policy_unchanged": True}
    assert "confidence" not in json.dumps(result).lower()


def test_an_emergency_refusal_is_not_called_a_policy_decision(world):
    register(world["ours"], "ours_agent")
    policy_control.update_emergency_controls(False, [], ["read_file"], [], "test", org_id=organizations.DEFAULT_ORG_ID)
    result = explain(world["ours"], submit("ours_agent", "read_file")["request_id"])
    assert result["reason"] == "Refused because an emergency control was on: Emergency: read_file disabled."
    assert "policy" not in result["reason"].lower()
    assert result["next_step"]["text"].startswith("An emergency control is on")


def test_a_suspended_agent_refusal_says_so(world):
    register(world["ours"], "ours_agent")
    with db_compat.connect(database.database_path) as connection:
        connection.execute("UPDATE agent_runtime_states SET agent_status = 'SUSPENDED' WHERE agent_name = ? AND org_id = ?",
                           ("ours_agent", organizations.DEFAULT_ORG_ID))
    result = explain(world["ours"], submit("ours_agent", "read_file")["request_id"])
    assert result["reason"] == "Refused because the agent was suspended when it asked."


def test_a_request_without_a_record_is_explained_as_inferred(world):
    register(world["ours"], "ours_agent")
    request = submit("ours_agent", "read_file")
    with db_compat.connect(database.database_path) as connection:
        connection.execute("DELETE FROM decision_records WHERE request_id = ? AND org_id = ?", (request["request_id"], organizations.DEFAULT_ORG_ID))
    result = explain(world["ours"], request["request_id"])
    assert result["basis"] == "inferred" and result["policy"]["basis"] == "inferred" and result["matched_rule"] is None
    assert "predates exact decision records" in result["reason"]
    assert "inferred" in {item["id"] for item in result["limitations"]}
    assert result["integrity"] == {"record_intact": None, "policy_unchanged": None}


def test_a_changed_policy_record_is_stated_as_a_limitation(world):
    register(world["ours"], "ours_agent")
    v1 = policy_control.get_published_policy(org_id=organizations.DEFAULT_ORG_ID)
    request = submit("ours_agent", "read_file")
    with db_compat.connect(database.database_path) as connection:
        connection.execute("UPDATE policy_versions SET permissions_json = ? WHERE policy_id = ? AND org_id = ?",
                           (json.dumps({**v1["permissions"], "read_file": "BLOCK"}), v1["policy_id"], organizations.DEFAULT_ORG_ID))
    result = explain(world["ours"], request["request_id"])
    assert result["decision"] == "ALLOW" and result["policy"]["unchanged_since_decision"] is False
    assert "policy_changed" in {item["id"] for item in result["limitations"]}


# --- Authentication assurance (decision records version 2) ---------------------------------------

def test_an_api_request_records_that_the_agent_used_its_key(world):
    issued = register(world["ours"], "ours_agent")
    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post("/tool-requests", json={"action": "read_file", "target": "a.txt", "payload": {}},
                           headers={"X-Agent-Name": "ours_agent", "X-Agent-Key": issued["credential"]})
    assert response.status_code == 201
    result = explain(world["ours"], response.json()["request_id"])
    assert result["authentication"]["method"] == "AGENT_KEY"
    assert result["authentication"]["summary"] == "The agent authenticated with its agent key."


def test_a_direct_call_says_authentication_was_not_recorded(world):
    register(world["ours"], "ours_agent")
    result = explain(world["ours"], submit("ours_agent", "read_file")["request_id"])
    assert result["authentication"]["method"] == "NOT_RECORDED"


def test_version_1_records_still_verify_and_say_not_recorded(world):
    register(world["ours"], "ours_agent")
    request = submit("ours_agent", "read_file")
    record = decision_provenance.get_decision_records([request["request_id"]], org_id=organizations.DEFAULT_ORG_ID)[request["request_id"]]
    # Rewrite it as the version-1 record it would have been (delete and re-insert: records are never updated).
    v1 = {field: record[field] for field in decision_provenance._FIELDS_V1 if field != "rule_snapshot_json"}
    v1.update({"rule_snapshot_json": decision_provenance.canonical(record["rule_snapshot"]), "schema_version": 1})
    # Computed independently of the module, from the version-1 field list as it was written.
    import hashlib
    v1_fields = ["request_id", "org_id", "agent_name", "action", "decided_at", "outcome", "policy_source", "policy_version_id",
                 "policy_version_number", "matched_rule_id", "rule_type", "rule_name", "rule_snapshot_json", "policy_fingerprint", "schema_version"]
    v1["record_fingerprint"] = hashlib.sha256(json.dumps({field: v1[field] for field in v1_fields}, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
    with db_compat.connect(database.database_path) as connection:
        connection.execute("DELETE FROM decision_records WHERE request_id = ? AND org_id = ?", (request["request_id"], organizations.DEFAULT_ORG_ID))
        connection.execute(f"INSERT INTO decision_records ({', '.join(v1)}) VALUES ({', '.join('?' for _ in v1)})", tuple(v1.values()))  # nosec B608  # test constants
    result = explain(world["ours"], request["request_id"])
    assert result["authentication"]["method"] is None and "predates" in result["authentication"]["summary"]
    assert result["integrity"]["record_intact"] is True


def test_an_unknown_authentication_method_is_refused():
    with pytest.raises(ValueError):
        decision_provenance.record_decision("r", org_id="o", agent_name="a", action="x", decided_at="t", decided={}, authentication_method="PASSWORD")


# --- Roles, next steps, and "why is this unavailable" ---------------------------------------------

def test_the_next_step_follows_the_viewers_permissions_without_naming_anyone(world):
    register(world["ours"], "ours_agent")
    pending = submit("ours_agent")
    admin = explain(world["ours"], pending["request_id"])["next_step"]
    assert admin == {"text": "Review it in Approvals.", "path": "/approvals", "available": True}
    auditor = explain(make_auditor(), pending["request_id"])["next_step"]
    assert auditor["available"] is False and auditor["path"] is None
    assert auditor["unavailable_reason"] == "Your role, Auditor, can view approvals but not decide them."


def test_every_unavailable_step_gives_a_role_only_reason(world):
    register(world["ours"], "ours_agent")
    auditor = make_auditor()
    for action in ("send_email", "launch_rockets"):
        step = explain(auditor, main.submit_tool_request("ours_agent", action, "", {})["request_id"])["next_step"]
        assert step["available"] is False and step["unavailable_reason"].startswith("Your role, Auditor,")
        assert "ours_agent" not in step["unavailable_reason"]


# --- Tenant isolation ------------------------------------------------------------------------------

def test_another_orgs_request_is_a_404_for_the_explanation_and_the_investigation(world):
    register(world["theirs"], "theirs_agent")
    theirs = submit("theirs_agent", "read_file")
    for call in (lambda: explain(world["ours"], theirs["request_id"]),
                 lambda: api.request_investigation(theirs["request_id"], x_admin_pin=world["ours"])):
        with pytest.raises(HTTPException) as error:
            call()
        assert error.value.status_code == 404


def test_the_investigation_carries_the_exact_explanation(world):
    register(world["ours"], "ours_agent")
    policy_control.update_emergency_controls(True, [], [], [], "test", org_id=organizations.DEFAULT_ORG_ID)
    request = submit("ours_agent", "read_file")
    bundle = api.request_investigation(request["request_id"], x_admin_pin=world["ours"])
    # The old generic sentence called this a policy decision; it now says what happened.
    assert bundle["decision_explanation"] == "Refused because an emergency control was on: Emergency global deny."
    assert bundle["explanation"]["basis"] == "recorded"


# --- Redaction -------------------------------------------------------------------------------------

@pytest.mark.parametrize("secret", [
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJlLXZhbHVlLWhlcmU",
    "sk-abcdefghijklmnopqrstuvwx",
    "ghp_abcdefghijklmnopqrstuvwxyz0123",
    "xoxb-1234567890-abcdefghij",
    "AKIAABCDEFGHIJKLMNOP",
    "Bearer abcdefghijklmnopqrstuvwxyz",
    "gga_abcdefghijklmnopqrstuvwx",
    "-----BEGIN RSA PRIVATE KEY-----",
])
def test_values_that_look_like_secrets_are_redacted_for_every_role(world, secret):
    register(world["ours"], "ours_agent")
    request = main.submit_tool_request("ours_agent", "write_note", "n.txt", {"content": f"note {secret} end", "safe": "hello"})
    for token in (world["ours"], make_auditor() if secret.startswith("eyJ") else world["ours"]):
        bundle = api.request_investigation(request["request_id"], x_admin_pin=token)
        text = json.dumps(bundle)
        assert secret not in text
        assert bundle["redacted_evidence"]["payload"] == {"content": "[REDACTED: looks like a secret]", "safe": "hello"}
        assert bundle["redactions"]["count"] >= 1


def test_ordinary_values_are_not_redacted(world):
    register(world["ours"], "ours_agent")
    request = main.submit_tool_request("ours_agent", "write_note", "n.txt", {"content": "quarterly plan, skip-level meeting, task-123"})
    bundle = api.request_investigation(request["request_id"], x_admin_pin=world["ours"])
    assert bundle["redacted_evidence"]["payload"] == {"content": "quarterly plan, skip-level meeting, task-123"}


def test_a_certificate_request_records_the_certificate(world, monkeypatch):
    from backend.app import enterprise_identity
    from backend.tests.test_agent_certificate_auth import FAKE_CERT_A
    monkeypatch.setattr(enterprise_identity, "database_path", database.database_path)
    monkeypatch.setenv("GREYGUARD_TRUST_CLIENT_CERT_HEADERS", "true")
    enterprise_identity.initialize_enterprise_identity()
    register(world["ours"], "ours_agent")
    enterprise_identity.create_workload_identity("adm_test", "Agent certificate", "CN=ours_agent", FAKE_CERT_A, ["read_file"], 90, "ours_agent")
    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post("/tool-requests", json={"action": "read_file", "target": "a.txt", "payload": {}},
                           headers={"X-SSL-Client-Verify": "SUCCESS", "X-SSL-Client-Cert": FAKE_CERT_A.replace("\n", "%0A")})
    assert response.status_code == 201, response.text
    result = explain(world["ours"], response.json()["request_id"])
    assert result["authentication"]["method"] == "CLIENT_CERTIFICATE"
