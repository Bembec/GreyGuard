"""P2.5 organization lifecycle - onboarding, export, offboarding and deletion - through the real
routes, with every backend module pointed at one throwaway database."""
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import (
    admin_auth, api, audit_integrity, billing, entitlements, isolation_operations, main, org_lifecycle,
    organizations, service_accounts, tenant_guard,
)

PASSWORD = "SecureDemo!123"


@pytest.fixture()
def install(tmp_path, monkeypatch):
    path = tmp_path / "lifecycle.db"
    for name, module in list(sys.modules.items()):
        if name.startswith("backend.app.") and isinstance(getattr(module, "database_path", None), Path):
            monkeypatch.setattr(module, "database_path", path)
    monkeypatch.setattr(main, "state_path", tmp_path / "state.json")
    monkeypatch.setattr(isolation_operations, "workspace_root", (tmp_path / "workspaces").resolve())
    monkeypatch.setattr(isolation_operations, "quarantine_root", (tmp_path / "quarantine").resolve())
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.setenv("GREYGUARD_BILLING_PROVIDER", "mock")
    monkeypatch.setenv("GREYGUARD_BILLING_WEBHOOK_SECRET", "lifecycle-test-webhook-secret-0123456789")
    with TestClient(api.app):  # the real startup initializes every module against the tmp database
        pass
    operator = admin_auth.create_administrator("op@greyguard.local", "Op", "PLATFORM_ADMIN", PASSWORD, install_operator=True)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, operator["admin_id"], "PLATFORM_ADMIN", "OWNER")
    return {"operator": admin_auth.authenticate(operator["email"], PASSWORD)["access_token"], "path": path}


def join(org_id, email, role="PLATFORM_ADMIN", governance="OWNER", mfa=False):
    person = admin_auth.create_administrator(email, email.split("@")[0], role, PASSWORD)
    organizations.ensure_membership(org_id, person["admin_id"], role, governance)
    if mfa:
        with admin_auth.sqlite3.connect(admin_auth.database_path) as connection:
            connection.execute("UPDATE administrators SET mfa_enabled = 1 WHERE admin_id = ?", (person["admin_id"],))
    token = admin_auth.authenticate(email, PASSWORD)["access_token"] if not mfa else None
    if token:
        organizations.switch_active_org(person["admin_id"], org_id, hashlib.sha256(token.encode()).hexdigest())
    return token


def tenant(install, name):
    org = organizations.create_organization(name, "system", creator_is_owner=False)
    return {"org_id": org["org_id"], "slug": org["slug"], "owner": join(org["org_id"], f"owner@{org['slug']}.example"),
            **install}


def populate(org, prefix):
    """Real data across many org-scoped tables, through the same functions the routes use."""
    owner = org["owner"]
    issued = api.register_agent_identity(api.AgentRegistration(agent_name=f"{prefix}_agent", scopes=["read_file"]), owner)
    main.submit_tool_request(f"{prefix}_agent", "read_file", "a.txt")
    api.configure_security_export_destination(api.ExportDestinationRequest(
        name="SIEM", destination_type="SPLUNK", endpoint="https://siem.example.com/ingest", enabled=True,
        minimization_profile="STANDARD", rate_limit_per_minute=60, max_attempts=3), owner)
    api.configure_notification_destination(api.NotificationDestinationRequest(
        name="Pager", channel="EMAIL", endpoint_reference="SECOPS_EMAIL", enabled=True), owner)
    api.schedule_security_report(api.ReportScheduleRequest(
        title="Weekly", frequency="WEEKLY", next_run_at="2099-01-01T00:00:00+00:00"), owner)
    api.generate_compliance_report(api.ComplianceReportRequest(title="Evidence"), owner)
    service_accounts.create_service_account(f"{prefix} exporter", "Exports", ["audit:read"], None, "test", org["org_id"])
    workspace = isolation_operations.create_workspace(f"{prefix}_agent", org["org_id"])
    (Path(workspace["path"]) / "notes.txt").write_text("workspace file")
    isolation_operations.write_and_quarantine_artifact(workspace["workspace_id"], "sample.bin", b"opaque", org["org_id"])
    return issued


def scoped_counts(org_id):
    with org_lifecycle.sqlite3.connect(org_lifecycle.database_path) as connection:
        return {table: connection.execute(f"SELECT COUNT(*) FROM {table} WHERE org_id = ?", (org_id,)).fetchone()[0]
                for table in org_lifecycle._scoped_tables(connection)}


def offboard(org, retention_days=0, token=None):
    return api.start_organization_offboarding(org["org_id"], api.OffboardingRequest(
        reason="Customer contract ended on schedule", retention_days=retention_days), token or org["owner"])


def delete(org, slug=None):
    return api.delete_organization_route(org["org_id"], api.OrganizationDeletionRequest(
        confirm_slug=slug or org["slug"]), org["operator"])


# --- Onboarding ----------------------------------------------------------------------------------

def test_onboarding_creates_the_org_without_the_operator_and_invites_its_owner(install):
    result = api.onboard_organization(api.OrganizationOnboardRequest(
        name="Acme Corp", owner_email="CISO@acme.example", plan="ENTERPRISE", trial_days=30), install["operator"])
    org_id = result["organization"]["org_id"]
    assert organizations.list_members(org_id) == []
    assert result["owner_invitation"]["email"] == "ciso@acme.example"
    current = entitlements.get_entitlements(org_id, meters=())
    assert current["plan"] == "ENTERPRISE" and current["status"] == "TRIAL"
    ciso = admin_auth.create_administrator("ciso@acme.example", "CISO", "SECURITY_ANALYST", PASSWORD)
    membership = organizations.accept_invitation(result["owner_invitation"]["token"], ciso["admin_id"], ciso["email"])
    assert membership["governance_role"] == "OWNER" and membership["operational_role"] == "PLATFORM_ADMIN"
    assert api.organization_lifecycle(org_id, install["operator"])["history"][0]["event_type"] == "ONBOARDED"
    with pytest.raises(HTTPException) as error:
        api.onboard_organization(api.OrganizationOnboardRequest(name="X", owner_email="a@b.example"), result["owner_invitation"]["token"])
    assert error.value.status_code == 401


def test_the_checklist_is_computed_from_real_data(install):
    org = tenant(install, "Checklist")
    done = lambda: {item["key"] for item in api.organization_lifecycle(org["org_id"], org["owner"])["checklist"] if item["done"]}
    assert done() == {"owner_active", "plan_assigned"} - {"plan_assigned"}
    api.register_agent_identity(api.AgentRegistration(agent_name="check_agent", scopes=["read_file"]), org["owner"])
    join(org["org_id"], "auditor@checklist.example", "AUDITOR", "MEMBER")
    api.export_organization_data(org["org_id"], org["owner"])
    assert done() == {"owner_active", "separation_of_duties", "auditor_assigned", "first_agent", "export_tested"}
    with organizations.sqlite3.connect(organizations.database_path) as connection:
        connection.execute("UPDATE administrators SET mfa_enabled = 1")
    assert "mfa_everyone" in done()


# --- Export --------------------------------------------------------------------------------------

def test_export_contains_only_the_orgs_own_rows_with_credentials_redacted(install):
    a, b = tenant(install, "Alpha"), tenant(install, "Bravo")
    issued = populate(a, "alpha")
    populate(b, "bravo")
    response = api.export_organization_data(a["org_id"], a["owner"])
    assert "attachment" in response.headers["content-disposition"]
    bundle = json.loads(response.body)
    serialized = json.dumps(bundle)
    assert "bravo" not in serialized.lower() and b["org_id"] not in serialized
    assert issued["credential"] not in serialized
    assert bundle["tables"]["agent_identities"][0]["credential_hash"] == org_lifecycle.REDACTED
    assert "service_account_keys" in bundle["redacted_columns"]
    for table, rows in bundle["tables"].items():
        assert all(row["org_id"] == a["org_id"] for row in rows)
        assert bundle["manifest"][table]["rows"] == len(rows)
        assert bundle["manifest"][table]["sha256"] == hashlib.sha256(org_lifecycle._canonical(rows)).hexdigest()
    assert {t for t, m in bundle["manifest"].items() if m["rows"]} >= {
        "agent_identities", "tool_requests", "audit_events", "export_destinations", "notification_destinations",
        "report_schedules", "compliance_reports", "service_accounts", "service_account_keys", "isolated_workspaces",
        "quarantined_artifacts"}


def test_every_secret_looking_column_has_an_export_decision():
    """Like the tenant-scoping registry: a new credential column cannot reach an export unredacted
    without someone deciding it is not a secret."""
    root = Path(__file__).resolve().parents[1]
    source = "\n".join(p.read_text() for p in (root / "migrations" / "versions").glob("*.py"))
    source += "\n".join(p.read_text() for p in (root / "app").glob("*.py"))
    columns = set(re.findall(r"\b(\w+)\s+(?:text|TEXT|bytea|BLOB|integer|INTEGER)\b", source))
    undecided = {c for c in columns if org_lifecycle.SECRET_LOOKING.search(c)} - org_lifecycle.REDACTED_COLUMNS \
        - org_lifecycle.EVIDENCE_COLUMNS
    assert undecided == set(), f"Columns with no export decision: {undecided}"


def test_export_permissions(install):
    org = tenant(install, "Perms")
    member = join(org["org_id"], "analyst@perms.example", "PLATFORM_ADMIN", "MEMBER")
    for token in (member, tenant(install, "Other")["owner"]):
        with pytest.raises(HTTPException) as error:
            api.export_organization_data(org["org_id"], token)
        assert error.value.status_code == 403
    assert api.export_organization_data(org["org_id"], install["operator"]).status_code == 200


# --- Offboarding ---------------------------------------------------------------------------------

def test_offboarding_closes_every_door_but_keeps_evidence_and_export(install):
    org = tenant(install, "Leaving")
    issued = populate(org, "leaving")
    billing.link_account(org["org_id"], "ENTERPRISE", "ap@leaving.example", "test")
    invitation = organizations.issue_invitation(org["org_id"], "late@leaving.example", "AUDITOR", "MEMBER", "test")
    state = offboard(org, retention_days=30)
    assert state["status"] == "OFFBOARDING"
    actions = state["offboarding"]["actions"]
    assert actions["agent_credentials_revoked"] == 1 and actions["service_accounts_revoked"] == 1
    assert actions["export_destinations_disabled"] == 1 and actions["notification_destinations_disabled"] == 1
    assert actions["report_schedules_disabled"] == 1 and actions["invitations_revoked"] == 1
    assert actions["billing"] == "cancelled"
    assert not any(isinstance(value, dict) and "error" in value for value in actions.values())
    with pytest.raises(main.AgentAuthenticationError):
        main.authenticate_agent("leaving_agent", issued["credential"], "read_file")
    # Growth is refused by the engine, whatever route is used.
    assert "offboarding" in str(pytest.raises(entitlements.EntitlementError, lambda: api.register_agent_identity(
        api.AgentRegistration(agent_name="new_agent", scopes=["read_file"]), org["owner"])).value)
    # The org is read-only over HTTP, apart from export, evidence and emergency controls.
    client = TestClient(api.app)
    headers = {"X-Admin-Pin": org["owner"]}
    response = client.put("/agents/leaving_agent/scopes", headers=headers, json={"scopes": ["read_file"]})
    assert response.status_code == 403 and response.json()["reason"] == "OFFBOARDING"
    assert client.post("/notification-delivery/destinations", headers=headers, json={
        "name": "Pager", "channel": "EMAIL", "endpoint_reference": "SECOPS_EMAIL", "enabled": True}).json()["reason"] == "OFFBOARDING"
    assert client.get("/audit-events", headers=headers).status_code == 200
    assert client.post(f"/organizations/{org['org_id']}/export", headers=headers).status_code == 200
    assert client.post("/compliance-reports", headers=headers, json={"title": "Exit evidence"}).status_code in (200, 201)
    assert client.put("/policy-emergency-controls", headers=headers, json={"global_deny": True}).status_code == 200
    late = admin_auth.create_administrator("late@leaving.example", "Late", "AUDITOR", PASSWORD)
    with pytest.raises(ValueError, match="revoked"):
        organizations.accept_invitation(invitation["token"], late["admin_id"], late["email"])
    # Even an invitation issued afterwards cannot bring anyone into an offboarding org.
    after = organizations.issue_invitation(org["org_id"], "late@leaving.example", "AUDITOR", "MEMBER", "test")
    with pytest.raises(ValueError, match="no longer accepting"):
        organizations.accept_invitation(after["token"], late["admin_id"], late["email"])
    # Deletion must wait for the retention period.
    with pytest.raises(HTTPException) as error:
        delete(org)
    assert error.value.status_code == 409 and "Deletion is possible from" in error.value.detail


def test_offboarding_rules(install):
    org = tenant(install, "Rules")
    member = join(org["org_id"], "member@rules.example", "PLATFORM_ADMIN", "MEMBER")
    for token in (member, tenant(install, "Elsewhere")["owner"]):
        with pytest.raises(HTTPException) as error:
            offboard(org, token=token)
        assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        api.start_organization_offboarding(organizations.DEFAULT_ORG_ID, api.OffboardingRequest(
            reason="Trying to offboard the default org"), install["operator"])
    assert error.value.status_code == 409
    offboard(org)
    with pytest.raises(HTTPException) as error:
        offboard(org)
    assert error.value.status_code == 409
    # Only an operator can cancel; the org is active again, but credentials stay revoked.
    with pytest.raises(HTTPException) as error:
        api.cancel_organization_offboarding(org["org_id"], org["owner"])
    assert error.value.status_code == 403
    assert api.cancel_organization_offboarding(org["org_id"], install["operator"])["status"] == "ACTIVE"
    assert entitlements.get_entitlements(org["org_id"], meters=())["restricted"] is False


# --- Deletion ------------------------------------------------------------------------------------

def test_deletion_removes_every_row_and_file_and_nothing_of_any_other_org(install):
    a, b = tenant(install, "Doomed"), tenant(install, "Neighbour")
    populate(a, "doomed")
    populate(b, "neighbour")
    api.export_organization_data(a["org_id"], a["owner"])
    before_b, before_default = scoped_counts(b["org_id"]), scoped_counts(organizations.DEFAULT_ORG_ID)
    assert sum(scoped_counts(a["org_id"]).values()) >= 20
    workspace = isolation_operations.workspace_root / a["org_id"]
    quarantined = list(isolation_operations.quarantine_root.iterdir())
    assert workspace.exists() and len(quarantined) == 2
    offboard(a)
    with pytest.raises(HTTPException) as error:
        delete(a, slug="wrong-slug")
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        api.delete_organization_route(a["org_id"], api.OrganizationDeletionRequest(confirm_slug=a["slug"]), a["owner"])
    assert error.value.status_code == 403
    certificate = delete(a)
    assert set(scoped_counts(a["org_id"]).values()) == {0}
    assert scoped_counts(b["org_id"]) == before_b
    assert scoped_counts(organizations.DEFAULT_ORG_ID) == before_default
    assert not workspace.exists() and len(list(isolation_operations.quarantine_root.iterdir())) == 1
    assert (isolation_operations.workspace_root / b["org_id"]).exists()
    assert "doomed_agent" not in main.agent_states and "neighbour_agent" in main.agent_states
    assert organizations.list_members(a["org_id"]) == []
    # The certificate is kept, verifies, and records what was removed and the export taken.
    assert certificate["total_rows_deleted"] == sum(certificate["rows_deleted"].values()) >= 20
    assert certificate["agents_removed"] == ["doomed_agent"] and certificate["files_removed"] == 2
    assert len(certificate["export_digests"]) == 1
    stored = api.organization_deletion_certificate(a["org_id"], install["operator"])
    assert stored["verified"] is True and stored["certificate_sha256"] == certificate["certificate_sha256"]
    assert org_lifecycle.verify_certificate({**certificate, "total_rows_deleted": 0}) is False
    # The tombstone frees the slug, and nothing more can happen to the org.
    assert organizations.get_organization(a["org_id"])["status"] == "DELETED"
    assert organizations.create_organization("Doomed", "system", creator_is_owner=False)["slug"] == "doomed"
    for call in (lambda: api.export_organization_data(a["org_id"], install["operator"]), lambda: delete(a)):
        with pytest.raises(HTTPException):
            call()


def test_deletion_keeps_the_audit_integrity_chain_verifiable(install):
    a, b = tenant(install, "Chain"), tenant(install, "Other")
    populate(a, "chain")
    populate(b, "other")
    assert audit_integrity.verify_integrity()["valid"] is True
    offboard(a)
    certificate = delete(a)
    verification = audit_integrity.verify_integrity()
    assert verification["valid"] is True and verification["records_erased"] == certificate["audit_events_erased"] > 0
    # An unrecorded deletion is still detected.
    with audit_integrity.sqlite3.connect(audit_integrity.database_path) as connection:
        connection.execute("-- test tampering across every org_id\nDELETE FROM audit_events WHERE org_id = ?", (b["org_id"],))
    assert audit_integrity.verify_integrity()["valid"] is False


def test_retention_deletion_no_longer_breaks_the_integrity_chain(install):
    with audit_integrity.sqlite3.connect(audit_integrity.database_path) as connection:
        for timestamp in ("2000-01-01T00:00:00+00:00", "2099-01-01T00:00:00+00:00"):
            connection.execute(
                "INSERT INTO audit_events (agent_name, timestamp, action, decision, approval, risk_added, risk_score,"
                " risk_level, agent_status, blocked_attempts, org_id) VALUES ('a', ?, 'x', 'ALLOW', 'n', 0, 0, 'LOW', 'ACTIVE', 0, ?)",
                (timestamp, organizations.DEFAULT_ORG_ID))
    assert audit_integrity.apply_retention("op", True)["deleted"] == 1
    verification = audit_integrity.verify_integrity()
    assert verification["valid"] is True and verification["records_erased"] == 1


def test_a_legal_hold_blocks_deletion(install):
    org = tenant(install, "Held")
    populate(org, "held")
    audit_integrity.create_legal_hold("Litigation", "Pending litigation hold for held_agent", "held_agent", None, None, "legal")
    offboard(org)
    with pytest.raises(HTTPException) as error:
        delete(org)
    assert error.value.status_code == 409 and "legal hold" in error.value.detail
    assert sum(scoped_counts(org["org_id"]).values()) > 0


def test_foreign_key_children_are_deleted_before_their_parents(install):
    with org_lifecycle.sqlite3.connect(org_lifecycle.database_path) as connection:
        order = org_lifecycle._scoped_tables(connection)
        for table in order:
            for parent in {row[2] for row in connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()}:
                if parent in tenant_guard.ORG_SCOPED_TABLES and parent != table:
                    assert order.index(table) < order.index(parent), (table, parent)


def test_the_default_org_can_never_be_deleted(install):
    with pytest.raises(org_lifecycle.LifecycleError):
        org_lifecycle.delete_organization(organizations.DEFAULT_ORG_ID, "op", "default")
