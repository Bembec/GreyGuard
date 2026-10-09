import pytest
from backend.app import admin_auth, organizations


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    path = tmp_path / "orgs.db"
    monkeypatch.setattr(admin_auth, "database_path", path)
    monkeypatch.setattr(organizations, "database_path", path)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_PASSWORD", raising=False)
    admin_auth.initialize_admin_auth()
    return path


def create_admin(email="owner@greyguard.local", role="PLATFORM_ADMIN"):
    return admin_auth.create_administrator(email, email.split("@")[0], role, "SecureDemo!123")


def test_fresh_install_seeds_the_default_org_with_zero_members(isolated):
    organizations.initialize_organizations()
    org = organizations.get_organization(organizations.DEFAULT_ORG_ID)
    assert org["name"] == "Default Organization"
    assert organizations.list_members(organizations.DEFAULT_ORG_ID) == []


def test_backfill_carries_existing_role_and_derives_governance_role(isolated):
    owner = create_admin("owner@greyguard.local", "PLATFORM_ADMIN")
    analyst = create_admin("analyst@greyguard.local", "SECURITY_ANALYST")
    organizations.initialize_organizations()
    owner_membership = organizations.get_membership(organizations.DEFAULT_ORG_ID, owner["admin_id"])
    analyst_membership = organizations.get_membership(organizations.DEFAULT_ORG_ID, analyst["admin_id"])
    assert owner_membership["operational_role"] == "PLATFORM_ADMIN"
    assert owner_membership["governance_role"] == "OWNER"
    assert analyst_membership["operational_role"] == "SECURITY_ANALYST"
    assert analyst_membership["governance_role"] == "MEMBER"


def test_backfill_is_idempotent_and_does_not_duplicate_memberships(isolated):
    owner = create_admin()
    organizations.initialize_organizations()
    organizations.initialize_organizations()
    organizations.initialize_organizations()
    members = organizations.list_members(organizations.DEFAULT_ORG_ID)
    assert len(members) == 1
    assert members[0]["admin_id"] == owner["admin_id"]


def test_backfill_never_auto_promotes_to_billing_admin(isolated):
    create_admin("owner@greyguard.local", "PLATFORM_ADMIN")
    create_admin("analyst@greyguard.local", "SECURITY_ANALYST")
    create_admin("auditor@greyguard.local", "AUDITOR")
    organizations.initialize_organizations()
    governance_roles = {m["governance_role"] for m in organizations.list_members(organizations.DEFAULT_ORG_ID)}
    assert "BILLING_ADMIN" not in governance_roles


def test_create_organization_makes_the_creator_an_owner(isolated):
    admin = create_admin()
    org = organizations.create_organization("Acme Security", admin["admin_id"])
    membership = organizations.get_membership(org["org_id"], admin["admin_id"])
    assert membership["governance_role"] == "OWNER"
    assert membership["operational_role"] == "PLATFORM_ADMIN"


def test_create_organization_rejects_duplicate_slug(isolated):
    admin = create_admin()
    organizations.create_organization("Acme Security", admin["admin_id"], slug="acme")
    with pytest.raises(ValueError, match="already exists"):
        organizations.create_organization("Acme Security Two", admin["admin_id"], slug="acme")


def test_list_memberships_for_admin_covers_multiple_orgs(isolated):
    """The explicit multi-org-per-administrator decision this whole module exists for."""
    admin = create_admin()
    organizations.initialize_organizations()
    second_org = organizations.create_organization("Second Org", admin["admin_id"])
    orgs = {m["org_id"] for m in organizations.list_memberships_for_admin(admin["admin_id"])}
    assert orgs == {organizations.DEFAULT_ORG_ID, second_org["org_id"]}
