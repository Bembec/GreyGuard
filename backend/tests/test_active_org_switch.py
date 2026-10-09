import hashlib

import pytest
from backend.app import admin_auth, api, organizations


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    path = tmp_path / "switch.db"
    monkeypatch.setattr(admin_auth, "database_path", path)
    monkeypatch.setattr(organizations, "database_path", path)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_PASSWORD", raising=False)
    admin_auth.initialize_admin_auth()
    return path


def create_admin(email, role="PLATFORM_ADMIN"):
    return admin_auth.create_administrator(email, email.split("@")[0], role, "SecureDemo!123")


def test_a_brand_new_session_auto_selects_the_only_membership(isolated):
    owner = create_admin("owner@greyguard.local")
    organizations.initialize_organizations()
    result = admin_auth.authenticate(owner["email"], "SecureDemo!123")
    assert result["administrator"]["active_org_id"] == organizations.DEFAULT_ORG_ID
    assert result["administrator"]["active_org_name"] == "Default Organization"
    assert result["administrator"]["governance_role"] == "OWNER"


def test_validate_session_reflects_the_membership_role_not_the_stale_global_role(isolated):
    """The real point of P2.1's auth-chain change: role comes from the active membership once
    one is resolvable, not from administrators.role directly."""
    owner = create_admin("owner@greyguard.local", "PLATFORM_ADMIN")
    organizations.initialize_organizations()
    org = organizations.create_organization("Second Org", owner["admin_id"])
    organizations.update_membership(org["org_id"], owner["admin_id"], owner["admin_id"], operational_role="AUDITOR")
    token = admin_auth.authenticate(owner["email"], "SecureDemo!123")["access_token"]
    # Fresh session auto-selects the earliest membership (the default org), where this admin is
    # still PLATFORM_ADMIN - the demotion only applies inside "Second Org".
    assert admin_auth.validate_session(token)["role"] == "PLATFORM_ADMIN"
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    organizations.switch_active_org(owner["admin_id"], org["org_id"], token_hash)
    assert admin_auth.validate_session(token)["role"] == "AUDITOR"


def test_switching_to_an_org_you_do_not_belong_to_is_rejected(isolated):
    owner = create_admin("owner@greyguard.local")
    other_owner = create_admin("other@greyguard.local")
    organizations.initialize_organizations()
    other_org = organizations.create_organization("Not Yours", other_owner["admin_id"])
    token = admin_auth.authenticate(owner["email"], "SecureDemo!123")["access_token"]
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with pytest.raises(PermissionError, match="not a member"):
        organizations.switch_active_org(owner["admin_id"], other_org["org_id"], token_hash)


def test_api_route_rejects_the_legacy_pin_since_it_has_no_session_to_switch(isolated, monkeypatch):
    monkeypatch.setenv("GREYGUARD_ENV", "development")
    monkeypatch.setenv("GREYGUARD_ADMIN_PIN", "legacy-test-pin")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        api.switch_active_organization(api.ActiveOrgSwitch(org_id="org_default"), "legacy-test-pin")
    assert error.value.status_code == 400


def test_api_route_switches_and_returns_the_refreshed_identity(isolated):
    owner = create_admin("owner@greyguard.local")
    organizations.initialize_organizations()
    org = organizations.create_organization("Second Org", owner["admin_id"])
    token = admin_auth.authenticate(owner["email"], "SecureDemo!123")["access_token"]
    updated = api.switch_active_organization(api.ActiveOrgSwitch(org_id=org["org_id"]), token)
    assert updated["active_org_id"] == org["org_id"]
    assert updated["active_org_name"] == "Second Org"
