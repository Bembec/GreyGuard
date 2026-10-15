"""P2.4 provider-neutral billing, billing-event evidence, payment-failure grace and self-hosted
licence leases, through the real routes."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import (
    admin_auth, alerts, api, billing, compliance_reports, database, entitlements, incident_integrations, licensing,
    main, notification_delivery, notifications, organizations, outbound_delivery, policy_control,
    policy_integrations, report_governance, security_exports,
)

PASSWORD = "SecureDemo!123"
SECRET = "test-billing-webhook-secret-0123456789abcdef"
MODULES = (admin_auth, alerts, billing, compliance_reports, database, entitlements, incident_integrations,
           licensing, notification_delivery, notifications, organizations, outbound_delivery, policy_control,
           policy_integrations, report_governance, security_exports)


@pytest.fixture()
def org(tmp_path, monkeypatch):
    path = tmp_path / "billing.db"
    for module in MODULES:
        monkeypatch.setattr(module, "database_path", path)
    monkeypatch.setattr(main, "state_path", tmp_path / "state.json")
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.setenv("GREYGUARD_BILLING_PROVIDER", "mock")
    monkeypatch.setenv("GREYGUARD_BILLING_WEBHOOK_SECRET", SECRET)
    monkeypatch.delenv("GREYGUARD_LICENSE_REQUIRED", raising=False)
    main.initialize_greyguard()
    policy_control.initialize_policy_control(main.permissions, main.risk_weights,
                                             main.max_blocked_attempts, main.max_risk_score)
    policy_integrations.initialize_policy_integrations()
    for initialize in (admin_auth.initialize_admin_auth, organizations.initialize_organizations,
                       entitlements.initialize_entitlements, billing.initialize_billing,
                       licensing.initialize_licensing, security_exports.initialize_security_exports,
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
    tokens = {}
    for email, role, governance in (("owner@tenant.example", "PLATFORM_ADMIN", "OWNER"),
                                    ("billing@tenant.example", "AUDITOR", "BILLING_ADMIN"),
                                    ("analyst@tenant.example", "SECURITY_ANALYST", "MEMBER")):
        person = admin_auth.create_administrator(email, email.split("@")[0], role, PASSWORD)
        organizations.ensure_membership(tenant["org_id"], person["admin_id"], role, governance)
        token = admin_auth.authenticate(email, PASSWORD)["access_token"]
        organizations.switch_active_org(person["admin_id"], tenant["org_id"], hashlib.sha256(token.encode()).hexdigest())
        tokens[governance] = token
    return {"org_id": tenant["org_id"], "operator": operator_token, "admin": tokens["OWNER"],
            "billing_admin": tokens["BILLING_ADMIN"], "member": tokens["MEMBER"]}


def link(org, plan="ENTERPRISE"):
    return api.link_organization_billing(org["org_id"], api.BillingLinkRequest(plan=plan, billing_email="ap@tenant.example"),
                                         org["operator"])


def simulate(org, event_type, **extra):
    return api.simulate_organization_billing_event(
        org["org_id"], api.BillingSimulationRequest(event_type=event_type, **extra), org["operator"])


def register(org, name):
    return api.register_agent_identity(api.AgentRegistration(agent_name=name, scopes=["read_file"]), org["admin"])


def refused(call):
    with pytest.raises(entitlements.EntitlementError) as error:
        call()
    return str(error.value)


def lapse_grace(org):
    with billing.sqlite3.connect(billing.database_path) as connection:
        connection.execute("UPDATE billing_accounts SET grace_ends_at = ? WHERE org_id = ?",
                           ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), org["org_id"]))


def webhook(body, headers):
    return TestClient(api.app).post("/billing/webhooks/mock", content=body, headers=headers)


def test_billing_is_off_by_default_and_changes_nothing(org, monkeypatch):
    monkeypatch.delenv("GREYGUARD_BILLING_PROVIDER")
    assert api.current_billing(org["admin"]) == {"enabled": False, "linked": False, "restriction": None}
    with pytest.raises(HTTPException) as error:
        link(org)
    assert error.value.status_code == 400
    assert api.current_entitlements(org["admin"])["restricted"] is False


def test_the_mock_provider_is_refused_in_production(org, monkeypatch):
    monkeypatch.setenv("GREYGUARD_ENV", "production")
    with pytest.raises(billing.BillingError, match="sandbox"):
        billing.provider()


def test_linking_assigns_the_plan_and_records_evidence(org):
    summary = link(org, "FOUNDATION")
    assert summary["linked"] and summary["billing_state"] == "ACTIVE" and summary["plan"] == "FOUNDATION"
    assert api.current_entitlements(org["admin"])["plan"] == "FOUNDATION"
    history = api.organization_entitlements(org["org_id"], org["operator"])["history"]
    assert history[0]["event_type"] == "PLAN_ASSIGNED" and history[0]["actor"]
    events = api.current_billing_events(org["admin"])
    assert [event["event_type"] for event in events["events"]] == ["ACCOUNT_LINKED"]
    assert events["verification"]["valid"] is True
    with pytest.raises(HTTPException) as error:
        link(org)
    assert error.value.status_code == 400


def test_payment_failure_starts_a_grace_period_then_restricts_but_never_removes_protection(org):
    link(org)
    issued = register(org, "billed_agent")
    simulate(org, "PAYMENT_FAILED", amount_minor=49900, currency="usd")
    current = api.current_billing(org["admin"])
    assert current["billing_state"] == "PAST_DUE" and current["restriction"] is None
    grace_ends = current["grace_ends_at"]
    # Still inside the grace period: nothing is restricted.
    register(org, "grace_agent")
    # A retry storm cannot extend the deadline.
    simulate(org, "PAYMENT_FAILED")
    assert api.current_billing(org["admin"])["grace_ends_at"] == grace_ends
    lapse_grace(org)
    current = api.current_entitlements(org["admin"])
    assert current["restricted"] is True and current["restriction_reasons"] == ["PAYMENT_OVERDUE"]
    assert current["status"] == "ACTIVE"  # the operator's plan status is untouched
    assert "payment is overdue" in refused(lambda: register(org, "blocked_agent"))
    # Existing agents keep being enforced; evidence, export and emergency controls stay available.
    assert main.authenticate_agent("billed_agent", issued["credential"], "read_file")["agent_name"] == "billed_agent"
    assert main.submit_tool_request("billed_agent", "read_file", "a.txt")["policy_decision"] == "ALLOW"
    report = api.generate_compliance_report(api.ComplianceReportRequest(title="Exit evidence"), org["admin"])
    assert api.export_compliance_report(report["report_id"], format="json", x_admin_pin=org["admin"]).status_code == 200
    assert api.configure_policy_emergency_controls(api.PolicyEmergencyRequest(global_deny=True), org["admin"])["global_deny"]
    assert api.revoke_credential("billed_agent", org["admin"])["revoked"] is True


def test_a_successful_payment_recovers_at_once(org):
    link(org)
    simulate(org, "PAYMENT_FAILED")
    lapse_grace(org)
    assert api.current_entitlements(org["admin"])["restricted"] is True
    simulate(org, "PAYMENT_SUCCEEDED", amount_minor=49900, currency="USD")
    assert api.current_billing(org["admin"])["billing_state"] == "ACTIVE"
    assert api.current_entitlements(org["admin"])["restricted"] is False
    register(org, "recovered_agent")


def test_a_payment_never_lifts_an_operator_suspension(org):
    link(org)
    api.assign_organization_plan(org["org_id"], api.PlanAssignmentRequest(plan="ENTERPRISE", status="SUSPENDED"), org["operator"])
    simulate(org, "PAYMENT_SUCCEEDED")
    assert api.current_entitlements(org["admin"])["restriction_reasons"] == ["PLAN_SUSPENDED"]


def test_cancellation_restricts_and_a_payment_does_not_reopen_it(org):
    link(org)
    api.cancel_organization_billing(org["org_id"], org["operator"])
    assert api.current_entitlements(org["admin"])["restriction_reasons"] == ["SUBSCRIPTION_CANCELED"]
    simulate(org, "PAYMENT_SUCCEEDED")
    assert api.current_billing(org["admin"])["billing_state"] == "CANCELED"


def test_webhooks_are_signed_idempotent_and_never_store_card_data(org):
    link(org)
    subscription = billing.get_account(org["org_id"])["subscription_ref"]
    mock = billing.provider("mock")
    event = {"provider_event_id": "evt_1", "event_type": "PAYMENT_FAILED", "subscription_ref": subscription,
             "card_number": "4242424242424242", "cvc": "123", "billing_address": "1 Main St"}
    body, headers = mock.sign(event)
    response = webhook(body, headers)
    assert response.status_code == 200 and response.json() == {"received": True, "duplicate": False}
    # Delivered again: recorded once.
    assert webhook(body, headers).json() == {"received": True, "duplicate": True}
    events = api.current_billing_events(org["admin"])["events"]
    assert [e["event_type"] for e in events].count("PAYMENT_FAILED") == 1
    with billing.sqlite3.connect(billing.database_path) as connection:
        stored = json.dumps([list(row) for row in connection.execute(
            "SELECT * FROM billing_events WHERE org_id = ?", (org["org_id"],)).fetchall()])
    assert "4242" not in stored and "cvc" not in stored and "Main St" not in stored
    # A tampered body, a bad signature, a stale timestamp and an unsigned request are all refused.
    assert webhook(body.replace(b"PAYMENT_FAILED", b"PAYMENT_SUCCEEDED"), headers).status_code == 400
    assert webhook(body, {billing.SIGNATURE_HEADER: headers[billing.SIGNATURE_HEADER][:-4] + "0000"}).status_code == 400
    stale_body, stale_headers = mock.sign({**event, "provider_event_id": "evt_2"}, timestamp=1_000_000_000)
    assert webhook(stale_body, stale_headers).status_code == 400
    assert webhook(body, {}).status_code == 400
    assert TestClient(api.app).post("/billing/webhooks/unknown", content=body, headers=headers).status_code == 404


def test_an_unknown_subscription_is_acknowledged_without_disclosure(org):
    body, headers = billing.provider("mock").sign(
        {"provider_event_id": "evt_x", "event_type": "PAYMENT_FAILED", "subscription_ref": "mock_sub_unknown"})
    assert webhook(body, headers).json() == {"received": True}


def test_webhooks_need_a_configured_secret(org, monkeypatch):
    link(org)
    body, headers = billing.provider("mock").sign(
        {"provider_event_id": "evt_s", "event_type": "PAYMENT_FAILED", "subscription_ref": "mock_sub_x"})
    monkeypatch.setenv("GREYGUARD_BILLING_WEBHOOK_SECRET", "short")
    assert webhook(body, headers).status_code == 400


def test_billing_evidence_is_hash_chained_and_tamper_evident(org):
    link(org)
    simulate(org, "PAYMENT_FAILED")
    simulate(org, "PAYMENT_SUCCEEDED")
    assert billing.verify_billing_evidence(org["org_id"]) == {
        "valid": True, "events": 3, "head": billing.billing_events(org["org_id"])[0]["record_hash"]}
    with billing.sqlite3.connect(billing.database_path) as connection:
        connection.execute("UPDATE billing_events SET detail_json = '{}' WHERE org_id = ? AND event_type = 'PAYMENT_FAILED'",
                           (org["org_id"],))
    verification = billing.verify_billing_evidence(org["org_id"])
    assert verification["valid"] is False and verification["broken_at_event_id"]


def test_billing_roles_and_tenant_isolation(org):
    link(org)
    # Owners and billing administrators manage billing whatever their operational role (the
    # billing administrator here is an AUDITOR); other members only see the status.
    assert api.update_billing_contact(api.BillingContactRequest(billing_email="finance@tenant.example"),
                                      org["billing_admin"])["billing_email"] == "finance@tenant.example"
    response = TestClient(api.app).put("/billing/contact", headers={"X-Admin-Pin": org["billing_admin"]},
                                       json={"billing_email": "ap2@tenant.example"})
    assert response.status_code == 200
    assert api.current_billing(org["member"])["linked"] is True
    for call in (lambda: api.current_billing_events(org["member"]),
                 lambda: api.update_billing_contact(api.BillingContactRequest(billing_email="x@y.example"), org["member"]),
                 lambda: link({**org, "operator": org["admin"]}),
                 lambda: simulate({**org, "operator": org["admin"]}, "PAYMENT_SUCCEEDED"),
                 lambda: api.cancel_organization_billing(org["org_id"], org["admin"]),
                 lambda: api.organization_billing(org["org_id"], org["admin"])):
        with pytest.raises(HTTPException) as error:
            call()
        assert error.value.status_code == 403
    # The default org has no billing account and is untouched by the tenant's billing state.
    simulate(org, "PAYMENT_FAILED")
    lapse_grace(org)
    assert billing.billing_summary(organizations.DEFAULT_ORG_ID)["linked"] is False
    assert entitlements.get_entitlements(organizations.DEFAULT_ORG_ID)["restricted"] is False


# --- Licence leases -------------------------------------------------------------------------

@pytest.fixture()
def keys(monkeypatch):
    private = Ed25519PrivateKey.generate()
    encode = licensing._b64encode
    monkeypatch.setenv("GREYGUARD_LICENSE_PUBLIC_KEY", encode(private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)))
    return encode(private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))


def lease(private_key, days=30, grace_days=14, issued_at=None, install=None):
    return licensing.issue_lease(private_key, licensee="Example Ltd", install=install or licensing.install_id(),
                                 plan="ENTERPRISE", days=days, grace_days=grace_days, issued_at=issued_at)


def put_lease(org, token):
    return api.install_license_lease(api.LicenseLeaseRequest(token=token), org["operator"])


def test_leases_are_not_enforced_unless_required(org, keys):
    assert api.install_license(org["operator"])["state"] == "NOT_REQUIRED"
    assert api.current_entitlements(org["admin"])["restricted"] is False


def test_a_required_licence_restricts_until_a_valid_lease_is_installed(org, keys, monkeypatch):
    monkeypatch.setenv("GREYGUARD_LICENSE_REQUIRED", "true")
    assert api.current_entitlements(org["admin"])["restriction_reasons"] == ["LICENSE_MISSING"]
    assert "no valid licence lease" in refused(lambda: register(org, "unlicensed"))
    status = put_lease(org, lease(keys))
    assert status["state"] == "VALID" and status["lease"]["licensee"] == "Example Ltd"
    register(org, "licensed")
    assert api.install_license(org["operator"])["history"][0]["event_type"] == "LEASE_INSTALLED"


def test_an_expired_lease_has_grace_then_lapses_and_a_renewal_recovers(org, keys, monkeypatch):
    monkeypatch.setenv("GREYGUARD_LICENSE_REQUIRED", "true")
    now = datetime.now(timezone.utc)
    put_lease(org, lease(keys, days=30, grace_days=6, issued_at=now - timedelta(days=35)))
    assert api.install_license(org["operator"])["state"] == "GRACE"
    issued = register(org, "grace_agent")
    # Two days later the grace period is over (the install's clock high-water mark is how time
    # is measured, so moving it forward stands in for waiting).
    with licensing.sqlite3.connect(licensing.database_path) as connection:
        connection.execute("UPDATE license_install SET clock_high_water = ?", ((now + timedelta(days=2)).isoformat(),))
    assert api.install_license(org["operator"])["state"] == "LAPSED"
    assert "licence lease has lapsed" in refused(lambda: register(org, "lapsed_agent"))
    # Every org on the install is restricted, but protection and existing agents are not touched.
    assert entitlements.get_entitlements(organizations.DEFAULT_ORG_ID)["restriction_reasons"] == ["LICENSE_LAPSED"]
    assert main.submit_tool_request("grace_agent", "read_file", "a.txt")["policy_decision"] == "ALLOW"
    assert api.revoke_credential("grace_agent", org["admin"])["revoked"] is True
    assert issued["credential"]
    put_lease(org, lease(keys))
    assert api.current_entitlements(org["admin"])["restricted"] is False


def test_bad_leases_are_refused(org, keys, monkeypatch):
    monkeypatch.setenv("GREYGUARD_LICENSE_REQUIRED", "true")
    other_key = licensing._b64encode(Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
    now = datetime.now(timezone.utc)
    current = lease(keys, issued_at=now - timedelta(days=1))
    put_lease(org, current)
    payload, signature = current.split(".")
    forged = json.loads(licensing._b64decode(payload))
    forged["expires_at"] = (now + timedelta(days=300)).isoformat()
    forged_token = licensing._b64encode(json.dumps(forged).encode()) + "." + signature
    for token, message in ((lease(other_key), "signature is invalid"),
                           (forged_token, "signature is invalid"),
                           (lease(keys, install="ins_someone_else"), "different install"),
                           (lease(keys, issued_at=now - timedelta(days=2)), "older lease"),
                           (lease(keys, days=1, grace_days=0, issued_at=now - timedelta(days=3)), "already lapsed"),
                           (lease(keys, days=401), "at most 400 days")):
        with pytest.raises(HTTPException) as error:
            put_lease(org, token)
        assert error.value.status_code == 400 and message in error.value.detail, (message, error.value.detail)
    with pytest.raises(HTTPException) as error:
        api.install_license_lease(api.LicenseLeaseRequest(token=lease(keys)), org["admin"])
    assert error.value.status_code == 403


def test_editing_the_stored_lease_or_winding_back_the_clock_does_not_revive_it(org, keys, monkeypatch):
    monkeypatch.setenv("GREYGUARD_LICENSE_REQUIRED", "true")
    now = datetime.now(timezone.utc)
    put_lease(org, lease(keys, days=30, grace_days=1, issued_at=now - timedelta(days=29, hours=23)))
    # Editing the table's dates has no effect: the signed token is re-verified on every read.
    with licensing.sqlite3.connect(licensing.database_path) as connection:
        connection.execute("UPDATE license_leases SET expires_at = '2999-01-01T00:00:00+00:00'")
    assert api.install_license(org["operator"])["lease"]["expires_at"] < "2999"
    # Tampering with the token itself makes the install unlicensed rather than extended.
    with licensing.sqlite3.connect(licensing.database_path) as connection:
        connection.execute("UPDATE license_leases SET token = token || 'x'")
    assert api.install_license(org["operator"])["state"] == "INVALID"
    with licensing.sqlite3.connect(licensing.database_path) as connection:
        connection.execute("UPDATE license_leases SET token = substr(token, 1, length(token) - 1)")
    # The install has seen a time past the grace period; a clock set back cannot revive the lease.
    with licensing.sqlite3.connect(licensing.database_path) as connection:
        connection.execute("UPDATE license_install SET clock_high_water = ?", ((now + timedelta(days=3)).isoformat(),))
    status = api.install_license(org["operator"])
    assert status["state"] == "LAPSED" and status["clock_rolled_back"] is True


def test_concurrent_deliveries_keep_one_unbroken_chain(org):
    from concurrent.futures import ThreadPoolExecutor
    link(org)
    subscription = billing.get_account(org["org_id"])["subscription_ref"]
    mock = billing.provider("mock")
    # Eight distinct events, each delivered three times at once.
    deliveries = [mock.sign({"provider_event_id": f"evt_c{n}", "event_type": "PAYMENT_SUCCEEDED",
                             "subscription_ref": subscription}) for n in range(8)] * 3
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda delivery: billing.handle_webhook("mock", *delivery), deliveries))
    assert sum(not result["duplicate"] for result in results) == 8
    assert billing.verify_billing_evidence(org["org_id"]) == {
        "valid": True, "events": 9, "head": billing.billing_events(org["org_id"])[0]["record_hash"]}
