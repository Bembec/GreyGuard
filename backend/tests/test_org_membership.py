import pytest
from backend.app import admin_auth, organizations


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    path = tmp_path / "membership.db"
    monkeypatch.setattr(admin_auth, "database_path", path)
    monkeypatch.setattr(organizations, "database_path", path)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_PASSWORD", raising=False)
    admin_auth.initialize_admin_auth()
    return path


def create_admin(email, role="PLATFORM_ADMIN"):
    return admin_auth.create_administrator(email, email.split("@")[0], role, "SecureDemo!123")


@pytest.fixture()
def org_with_owner(isolated):
    owner = create_admin("owner@greyguard.local")
    org = organizations.create_organization("Acme Security", owner["admin_id"])
    return org, owner


# -- invitations ---------------------------------------------------------------------

def test_owner_can_invite_and_the_invitee_can_accept(org_with_owner):
    org, owner = org_with_owner
    member = create_admin("member@greyguard.local", "SECURITY_ANALYST")
    invitation = organizations.create_invitation(
        org["org_id"], member["email"], "SECURITY_ANALYST", "MEMBER", owner["admin_id"],
    )
    membership = organizations.accept_invitation(invitation["token"], member["admin_id"], member["email"])
    assert membership["org_id"] == org["org_id"]
    assert membership["operational_role"] == "SECURITY_ANALYST"
    assert membership["governance_role"] == "MEMBER"


def test_non_owner_cannot_invite(org_with_owner):
    org, owner = org_with_owner
    member = create_admin("member@greyguard.local", "SECURITY_ANALYST")
    organizations.create_invitation(org["org_id"], member["email"], "SECURITY_ANALYST", "MEMBER", owner["admin_id"])
    invitation = organizations.create_invitation(org["org_id"], "second@greyguard.local", "AUDITOR", "MEMBER", owner["admin_id"])
    second = create_admin("second@greyguard.local", "AUDITOR")
    organizations.accept_invitation(invitation["token"], second["admin_id"], second["email"])
    with pytest.raises(PermissionError):
        organizations.create_invitation(org["org_id"], "third@greyguard.local", "AUDITOR", "MEMBER", second["admin_id"])


def test_invitation_is_scoped_to_the_invited_email(org_with_owner):
    org, owner = org_with_owner
    invitation = organizations.create_invitation(
        org["org_id"], "invited@greyguard.local", "AUDITOR", "MEMBER", owner["admin_id"],
    )
    impostor = create_admin("impostor@greyguard.local", "AUDITOR")
    with pytest.raises(PermissionError, match="different email"):
        organizations.accept_invitation(invitation["token"], impostor["admin_id"], impostor["email"])


def test_invitation_cannot_be_accepted_twice(org_with_owner):
    org, owner = org_with_owner
    member = create_admin("member@greyguard.local", "AUDITOR")
    invitation = organizations.create_invitation(org["org_id"], member["email"], "AUDITOR", "MEMBER", owner["admin_id"])
    organizations.accept_invitation(invitation["token"], member["admin_id"], member["email"])
    with pytest.raises(ValueError, match="already been accepted"):
        organizations.accept_invitation(invitation["token"], member["admin_id"], member["email"])


def test_revoked_invitation_cannot_be_accepted(org_with_owner):
    org, owner = org_with_owner
    member = create_admin("member@greyguard.local", "AUDITOR")
    invitation = organizations.create_invitation(org["org_id"], member["email"], "AUDITOR", "MEMBER", owner["admin_id"])
    organizations.revoke_invitation(org["org_id"], invitation["invitation_id"], owner["admin_id"])
    with pytest.raises(ValueError, match="revoked"):
        organizations.accept_invitation(invitation["token"], member["admin_id"], member["email"])


def test_non_owner_cannot_revoke_an_invitation(org_with_owner):
    org, owner = org_with_owner
    other_owner_like = create_admin("other@greyguard.local", "AUDITOR")
    invitation = organizations.create_invitation(org["org_id"], "x@greyguard.local", "AUDITOR", "MEMBER", owner["admin_id"])
    with pytest.raises(PermissionError):
        organizations.revoke_invitation(org["org_id"], invitation["invitation_id"], other_owner_like["admin_id"])


# -- the last-owner guard -------------------------------------------------------------

def test_the_final_owner_of_an_org_cannot_be_demoted(org_with_owner):
    org, owner = org_with_owner
    with pytest.raises(ValueError, match="final owner"):
        organizations.update_membership(org["org_id"], owner["admin_id"], owner["admin_id"], governance_role="MEMBER")


def test_the_final_owner_of_an_org_cannot_be_removed(org_with_owner):
    org, owner = org_with_owner
    with pytest.raises(ValueError, match="final owner"):
        organizations.remove_membership(org["org_id"], owner["admin_id"], owner["admin_id"])


def test_a_second_owner_can_be_demoted_once_another_owner_exists(org_with_owner):
    org, owner = org_with_owner
    second = create_admin("second@greyguard.local", "PLATFORM_ADMIN")
    invitation = organizations.create_invitation(org["org_id"], second["email"], "PLATFORM_ADMIN", "OWNER", owner["admin_id"])
    organizations.accept_invitation(invitation["token"], second["admin_id"], second["email"])
    # Two owners now exist, so demoting the original one is no longer blocked.
    updated = organizations.update_membership(org["org_id"], owner["admin_id"], second["admin_id"], governance_role="MEMBER")
    assert updated["governance_role"] == "MEMBER"


def test_removing_a_member_does_not_require_them_to_be_the_last_owner(org_with_owner):
    org, owner = org_with_owner
    member = create_admin("member@greyguard.local", "AUDITOR")
    invitation = organizations.create_invitation(org["org_id"], member["email"], "AUDITOR", "MEMBER", owner["admin_id"])
    organizations.accept_invitation(invitation["token"], member["admin_id"], member["email"])
    organizations.remove_membership(org["org_id"], member["admin_id"], owner["admin_id"])
    assert organizations.get_membership(org["org_id"], member["admin_id"]) is None
