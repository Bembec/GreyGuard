"""Install-wide controls are gated on the global install_operator flag, not on PLATFORM_ADMIN.

Since P2.1, PLATFORM_ADMIN is resolved from the caller's active org membership, and creating an
org makes its creator that org's PLATFORM_ADMIN. Gating install-wide controls on it let any
administrator - even an AUDITOR - create an org, become PLATFORM_ADMIN there, and then reset
another org owner's password through /administrators.
"""
import sqlite3

import pytest
from fastapi import HTTPException

from backend.app import admin_auth, api, organizations

PASSWORD = "SecureDemo!123"


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    path = tmp_path / "operator.db"
    monkeypatch.setattr(admin_auth, "database_path", path)
    monkeypatch.setattr(organizations, "database_path", path)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_PASSWORD", raising=False)
    admin_auth.initialize_admin_auth()
    organizations.initialize_organizations()
    return path


def create_admin(email, role="PLATFORM_ADMIN", install_operator=False):
    created = admin_auth.create_administrator(email, email.split("@")[0], role, PASSWORD,
                                              install_operator=install_operator)
    organizations.ensure_membership(organizations.DEFAULT_ORG_ID, created["admin_id"], role,
                                    "OWNER" if role == "PLATFORM_ADMIN" else "MEMBER")
    return created


def login(admin):
    return admin_auth.authenticate(admin["email"], PASSWORD)["access_token"]


def forbidden(call):
    with pytest.raises(HTTPException) as error:
        call()
    return error.value.status_code == 403


# Every install-wide route. Each gate runs before its payload is read, so a denied caller never
# reaches the body - None stands in for payloads the gate never gets to.
GATED_ROUTES = {
    "create organization": lambda t: api.create_organization_route(api.OrganizationCreate(name="Mine"), t),
    "list administrators": lambda t: api.administrators(t),
    "create administrator": lambda t: api.register_administrator(None, t),
    "edit administrator": lambda t: api.edit_administrator("adm_x", api.AdministratorUpdate(), t),
    "reset password": lambda t: api.reset_admin_password("adm_x", None, t),
    "revoke sessions": lambda t: api.revoke_admin_sessions("adm_x", t),
    "observability config": lambda t: api.observability_configuration(t),
    "update observability": lambda t: api.configure_observability(None, t),
    "observability metrics": lambda t: api.observability_metrics(t),
    "observability traces": lambda t: api.observability_traces(x_admin_pin=t),
    "list private allowlist": lambda t: api.outbound_private_allowlist(t),
    "allow private host": lambda t: api.allow_outbound_private_destination(None, t),
    "revoke private host": lambda t: api.revoke_outbound_private_destination("h.corp", t),
    "abuse protection": lambda t: api.abuse_protection_overview(t),
    "update rate limit": lambda t: api.administrator_update_rate_limit_policy("LOGIN", None, t),
    "enterprise identity": lambda t: api.enterprise_identity_overview(t),
    "identity provider": lambda t: api.configure_identity_provider(None, t),
    "identity mapping": lambda t: api.configure_identity_mapping(None, t),
    "workload identity": lambda t: api.register_workload_identity(None, t),
    "revoke workload": lambda t: api.revoke_workload_identity_route("wid_x", None, t),
    "elevation decision": lambda t: api.review_elevation_request("elv_x", None, t),
    # One hash chain and one retention policy for the whole audit log: any org's admin applying
    # retention would delete every other org's audit history.
    "audit integrity": lambda t: api.audit_integrity_controls(t),
    "verify audit chain": lambda t: api.verify_audit_chain(t),
    "configure audit retention": lambda t: api.configure_audit_retention(None, t),
    "create legal hold": lambda t: api.add_audit_legal_hold(None, t),
    "release legal hold": lambda t: api.release_audit_legal_hold("hold_x", t),
    "apply audit retention": lambda t: api.execute_audit_retention(None, t),
}


@pytest.mark.parametrize("route", sorted(GATED_ROUTES))
def test_an_org_platform_admin_who_is_not_an_operator_is_refused(isolated, route):
    create_admin("operator@greyguard.local", install_operator=True)
    tenant_admin = create_admin("tenant@greyguard.local", "PLATFORM_ADMIN")
    token = login(tenant_admin)
    assert api.require_admin(token)["role"] == "PLATFORM_ADMIN"
    assert forbidden(lambda: GATED_ROUTES[route](token))


def test_the_org_creation_takeover_chain_is_closed(isolated):
    owner = create_admin("owner@greyguard.local", install_operator=True)
    auditor = create_admin("auditor@greyguard.local", "AUDITOR")
    token = login(auditor)
    # Step 1 of the old chain: any admin could create an org and become its PLATFORM_ADMIN.
    assert forbidden(lambda: api.create_organization_route(api.OrganizationCreate(name="Mine"), token))
    # Even an admin who *is* PLATFORM_ADMIN of some other org (however they got there) still
    # cannot reach account management for anyone else.
    other_org = organizations.create_organization("Other", owner["admin_id"])
    organizations.ensure_membership(other_org["org_id"], auditor["admin_id"], "PLATFORM_ADMIN", "OWNER")
    token_hash = __import__("hashlib").sha256(token.encode()).hexdigest()
    organizations.switch_active_org(auditor["admin_id"], other_org["org_id"], token_hash)
    assert api.require_admin(token)["role"] == "PLATFORM_ADMIN"
    assert forbidden(lambda: api.reset_admin_password(
        owner["admin_id"], api.AdministratorPasswordReset(new_password="Hijacked!Password1"), token))
    assert admin_auth.authenticate(owner["email"], PASSWORD)["access_token"]


def test_an_operator_can_reach_install_wide_controls(isolated):
    operator = create_admin("operator@greyguard.local", install_operator=True)
    token = login(operator)
    assert api.administrators(token)["count"] == 1
    assert api.create_organization_route(api.OrganizationCreate(name="Tenant"), token)["name"] == "Tenant"
    assert api.outbound_private_allowlist(token) == {"hosts": []}


def test_operator_status_is_granted_explicitly_and_the_last_one_cannot_be_removed(isolated):
    operator = create_admin("operator@greyguard.local", install_operator=True)
    analyst = create_admin("analyst@greyguard.local", "SECURITY_ANALYST")
    token = login(operator)
    with pytest.raises(HTTPException) as error:
        api.edit_administrator(operator["admin_id"], api.AdministratorUpdate(install_operator=False), token)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException):
        api.edit_administrator(operator["admin_id"], api.AdministratorUpdate(status="DISABLED"), token)
    granted = api.edit_administrator(analyst["admin_id"], api.AdministratorUpdate(install_operator=True), token)
    assert granted["install_operator"] is True
    # With a second operator in place, the first may step down.
    assert api.edit_administrator(operator["admin_id"], api.AdministratorUpdate(install_operator=False),
                                  token)["install_operator"] is False


def test_first_run_setup_creates_an_operator(isolated):
    session = admin_auth.setup_first_administrator("first@greyguard.local", "First", PASSWORD)
    assert session["administrator"]["install_operator"] is True


def test_legacy_pin_is_an_install_level_shortcut(isolated, monkeypatch):
    monkeypatch.setenv("GREYGUARD_ENV", "development")
    monkeypatch.setenv("GREYGUARD_ADMIN_PIN", "legacy-test-pin")
    assert api.require_install_operator("legacy-test-pin")["install_operator"] is True


def test_existing_platform_admins_are_backfilled_as_operators(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE administrators (
            admin_id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            display_name TEXT NOT NULL, role TEXT NOT NULL, password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL, last_login_at TEXT)""")
        for admin_id, role in (("adm_platform", "PLATFORM_ADMIN"), ("adm_analyst", "SECURITY_ANALYST")):
            connection.execute("INSERT INTO administrators VALUES(?,?,?,?,'00','00','ACTIVE','2026-01-01',NULL)",
                               (admin_id, admin_id + "@greyguard.local", admin_id, role))
    monkeypatch.setattr(admin_auth, "database_path", path)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    admin_auth.initialize_admin_auth()
    assert admin_auth.get_administrator("adm_platform")["install_operator"] is True
    assert admin_auth.get_administrator("adm_analyst")["install_operator"] is False
    # Re-running initialization never re-grants: a later-demoted operator stays demoted.
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE administrators SET install_operator = 0 WHERE admin_id = 'adm_platform'")
    admin_auth.initialize_admin_auth()
    assert admin_auth.get_administrator("adm_platform")["install_operator"] is False
