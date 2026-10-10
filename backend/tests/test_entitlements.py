"""P2.3 plans, entitlements, trials, usage meters and limits, through the real routes."""
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend.app import (
    admin_auth, alerts, api, compliance_reports, database, entitlements, incident_integrations, main,
    notification_delivery, notifications, organizations, outbound_delivery, policy_control,
    policy_integrations, report_governance, security_exports,
)

PASSWORD = "SecureDemo!123"
MODULES = (admin_auth, alerts, compliance_reports, database, entitlements, incident_integrations,
           notification_delivery, notifications, organizations, outbound_delivery, policy_control,
           policy_integrations, report_governance, security_exports)


@pytest.fixture()
def org(tmp_path, monkeypatch):
    path = tmp_path / "entitlements.db"
    for module in MODULES:
        monkeypatch.setattr(module, "database_path", path)
    monkeypatch.setattr(main, "state_path", tmp_path / "state.json")
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    main.initialize_greyguard()
    policy_control.initialize_policy_control(main.permissions, main.risk_weights,
                                             main.max_blocked_attempts, main.max_risk_score)
    policy_integrations.initialize_policy_integrations()
    for initialize in (admin_auth.initialize_admin_auth, organizations.initialize_organizations,
                       entitlements.initialize_entitlements, security_exports.initialize_security_exports,
                       incident_integrations.initialize_incident_integrations,
                       notification_delivery.initialize_notification_delivery,
                       report_governance.initialize_report_governance,
                       compliance_reports.initialize_compliance_reports,
                       outbound_delivery.initialize_outbound_delivery):
        initialize()
    operator = admin_auth.create_administrator("op@greyguard.local", "Op", "PLATFORM_ADMIN", PASSWORD, install_operator=True)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, operator["admin_id"], "PLATFORM_ADMIN", "OWNER")
    operator_token = admin_auth.authenticate(operator["email"], PASSWORD)["access_token"]
    tenant = organizations.create_organization("Tenant", operator["admin_id"])
    admin = admin_auth.create_administrator("admin@tenant.example", "Admin", "PLATFORM_ADMIN", PASSWORD)
    organizations.ensure_membership(tenant["org_id"], admin["admin_id"], "PLATFORM_ADMIN", "OWNER")
    admin_token = admin_auth.authenticate(admin["email"], PASSWORD)["access_token"]
    organizations.switch_active_org(admin["admin_id"], tenant["org_id"], hashlib.sha256(admin_token.encode()).hexdigest())
    return {"org_id": tenant["org_id"], "operator": operator_token, "admin": admin_token}


def assign(org, plan, status="ACTIVE", trial_days=None):
    return api.assign_organization_plan(
        org["org_id"], api.PlanAssignmentRequest(plan=plan, status=status, trial_days=trial_days), org["operator"])


def register(org, name):
    return api.register_agent_identity(api.AgentRegistration(agent_name=name, scopes=["read_file"]), org["admin"])


def siem(org, name="SIEM"):
    return api.configure_security_export_destination(api.ExportDestinationRequest(
        name=name, destination_type="SPLUNK", endpoint="https://siem.example.com/ingest", enabled=True,
        minimization_profile="STANDARD", rate_limit_per_minute=60, max_attempts=3), org["admin"])


def refused(call):
    with pytest.raises(entitlements.EntitlementError) as error:
        call()
    return str(error.value)


def test_no_plan_feature_can_ever_be_a_mandatory_protection():
    assert not (entitlements.FEATURES & entitlements.MANDATORY_PROTECTIONS)
    for plan in entitlements.PLANS.values():
        assert plan["features"] <= entitlements.FEATURES
        assert set(plan["limits"]) == set(entitlements.METERS)
    # Mandatory protections are never refused, whatever the org's state.
    entitlements.require_feature("org_anything", "emergency_stop")


def test_an_unassigned_org_is_not_restricted_at_all(org):
    current = api.current_entitlements(org["admin"])
    assert current["plan"] == "UNASSIGNED" and current["restricted"] is False
    assert set(current["features"]) == entitlements.FEATURES
    assert siem(org)["name"] == "SIEM"


def test_a_plan_without_a_feature_refuses_it_in_the_backend(org):
    assign(org, "FOUNDATION")
    assert "does not include siem export" in refused(lambda: siem(org))
    assert "does not include incident integrations" in refused(lambda: api.configure_incident_destination(
        api.IncidentDestinationRequest(name="Jira", system_type="JIRA", endpoint="https://jira.example.com",
                                       credential_reference="JIRA_TOKEN", project_or_table="SEC", enabled=True), org["admin"]))
    assert "does not include scheduled reports" in refused(lambda: api.schedule_security_report(
        api.ReportScheduleRequest(title="Weekly", frequency="WEEKLY", next_run_at="2099-01-01T00:00:00+00:00"), org["admin"]))


def test_hard_limits_refuse_growth_and_soft_limits_are_reported(org):
    assign(org, "FOUNDATION")
    api.add_entitlement_override(org["org_id"], api.EntitlementOverrideRequest(
        key="limit:agents:hard", value=2, reason="Small pilot - two agents only"), org["operator"])
    api.add_entitlement_override(org["org_id"], api.EntitlementOverrideRequest(
        key="limit:agents:soft", value=1, reason="Warn the pilot at its first agent"), org["operator"])
    register(org, "pilot_one")
    register(org, "pilot_two")
    assert "allows 2 agents" in refused(lambda: register(org, "pilot_three"))
    current = api.current_entitlements(org["admin"])
    assert current["usage"]["agents"] == 2 and current["soft_limits_exceeded"] == ["agents"]


def test_updating_an_existing_integration_is_not_growth(org):
    assign(org, "ENTERPRISE")
    api.add_entitlement_override(org["org_id"], api.EntitlementOverrideRequest(
        key="limit:integrations:hard", value=1, reason="One SIEM destination for this pilot"), org["operator"])
    siem(org, "Primary")
    assert siem(org, "PRIMARY")["name"] == "Primary"  # same destination (names are case-insensitive)
    assert "allows 1 integrations" in refused(lambda: siem(org, "Secondary"))


def test_an_expired_trial_pauses_growth_but_never_protection_or_evidence(org):
    assign(org, "ENTERPRISE", "TRIAL", trial_days=14)
    issued = register(org, "trial_agent")
    with entitlements.sqlite3.connect(entitlements.database_path) as connection:
        connection.execute("UPDATE org_entitlements SET trial_ends_at = ? WHERE org_id = ?",
                           ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), org["org_id"]))
    current = api.current_entitlements(org["admin"])
    assert current["status"] == "EXPIRED" and current["restricted"] is True
    assert "expired" in refused(lambda: register(org, "another_agent"))
    assert "expired" in refused(lambda: siem(org))
    # Existing agents keep being enforced exactly as before.
    assert main.authenticate_agent("trial_agent", issued["credential"], "read_file")["agent_name"] == "trial_agent"
    assert main.submit_tool_request("trial_agent", "read_file", "a.txt")["policy_decision"] == "ALLOW"
    # Evidence, export and security controls stay available.
    assert api.administrator_audit_events(event_type=None, agent_name=None, limit=50, x_admin_pin=org["admin"])["events"]
    report = api.generate_compliance_report(api.ComplianceReportRequest(title="Exit evidence"), org["admin"])
    assert api.export_compliance_report(report["report_id"], format="json", x_admin_pin=org["admin"]).status_code == 200
    controls = api.configure_policy_emergency_controls(api.PolicyEmergencyRequest(global_deny=True), org["admin"])
    assert controls["global_deny"] is True
    assert api.revoke_credential("trial_agent", org["admin"])["revoked"] is True


def test_suspension_restricts_the_same_way(org):
    assign(org, "ENTERPRISE", "SUSPENDED")
    assert "suspended" in refused(lambda: register(org, "blocked_agent"))
    assert api.current_entitlements(org["admin"])["restricted"] is True


def test_overrides_are_reasoned_audited_revocable_and_cannot_touch_mandatory_protections(org):
    assign(org, "FOUNDATION")
    granted = api.add_entitlement_override(org["org_id"], api.EntitlementOverrideRequest(
        key="feature:siem_export", value=True, reason="Security review requires SIEM during pilot",
        expires_in_days=30), org["operator"])
    assert "siem_export" in granted["features"]
    assert siem(org)["name"] == "SIEM"
    override_id = granted["overrides"][0]["override_id"]
    api.revoke_entitlement_override(org["org_id"], override_id, org["operator"])
    assert "does not include siem export" in refused(lambda: siem(org, "Another"))
    for key in ("feature:emergency_stop", "feature:evidence_export", "limit:members:hard"):
        with pytest.raises(HTTPException) as error:
            api.add_entitlement_override(org["org_id"], api.EntitlementOverrideRequest(
                key=key, value=False, reason="Attempting to remove a protection"), org["operator"])
        assert error.value.status_code == 400
    history = api.organization_entitlements(org["org_id"], org["operator"])["history"]
    assert [event["event_type"] for event in history] == ["OVERRIDE_REVOKED", "OVERRIDE_ADDED", "PLAN_ASSIGNED"]


def test_only_install_operators_assign_plans_or_overrides(org):
    for call in (lambda: assign({**org, "operator": org["admin"]}, "DEDICATED"),
                 lambda: api.add_entitlement_override(org["org_id"], api.EntitlementOverrideRequest(
                     key="limit:agents:hard", value=None, reason="Self-granted unlimited agents"), org["admin"]),
                 lambda: api.organization_entitlements(org["org_id"], org["admin"])):
        with pytest.raises(HTTPException) as error:
            call()
        assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        api.assign_organization_plan("org_missing", api.PlanAssignmentRequest(plan="FOUNDATION"), org["operator"])
    assert error.value.status_code == 404


def test_meters_count_the_orgs_own_usage_only(org):
    register(org, "metered_agent")
    main.submit_tool_request("metered_agent", "read_file", "a.txt")
    siem(org)
    usage = api.current_entitlements(org["admin"])["usage"]
    assert usage["agents"] == 1 and usage["controlled_requests_monthly"] == 1 and usage["integrations"] == 1
    assert entitlements.usage(organizations.DEFAULT_ORG_ID)["agents"] == 0


def test_a_refusal_is_a_403_over_http(org):
    from fastapi.testclient import TestClient
    assign(org, "FOUNDATION")
    response = TestClient(api.app).post("/security-exports/destinations", headers={"X-Admin-Pin": org["admin"]}, json={
        "name": "SIEM", "destination_type": "SPLUNK", "endpoint": "https://siem.example.com/ingest", "enabled": True,
        "minimization_profile": "STANDARD", "rate_limit_per_minute": 60, "max_attempts": 3})
    assert response.status_code == 403 and response.json()["reason"] == "ENTITLEMENT"
