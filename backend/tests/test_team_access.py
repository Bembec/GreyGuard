import pytest
from backend.app import admin_auth


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(admin_auth, "database_path", tmp_path / "team.db")
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_PASSWORD", raising=False)
    admin_auth.initialize_admin_auth()


def create(email, role="PLATFORM_ADMIN"):
    return admin_auth.create_administrator(email, email.split("@")[0], role, "SecureDemo!123")


def test_role_and_status_can_be_updated(isolated):
    create("owner@greyguard.local")
    analyst = create("analyst@greyguard.local", "SECURITY_ANALYST")
    updated = admin_auth.update_administrator(analyst["admin_id"], role="AUDITOR", status="DISABLED")
    assert updated["role"] == "AUDITOR"
    assert updated["status"] == "DISABLED"


def test_final_platform_admin_is_protected(isolated):
    owner = create("owner@greyguard.local")
    with pytest.raises(ValueError, match="final active"):
        admin_auth.update_administrator(owner["admin_id"], status="DISABLED")


def test_password_reset_revokes_existing_sessions(isolated):
    owner = create("owner@greyguard.local")
    token = admin_auth.authenticate(owner["email"], "SecureDemo!123")["access_token"]
    admin_auth.reset_administrator_password(owner["admin_id"], "Replacement!456")
    with pytest.raises(ValueError):
        admin_auth.validate_session(token)
    assert admin_auth.authenticate(owner["email"], "Replacement!456")["administrator"]["email"] == owner["email"]


def test_session_revocation_is_targeted(isolated):
    first = create("first@greyguard.local")
    second = create("second@greyguard.local")
    first_token = admin_auth.authenticate(first["email"], "SecureDemo!123")["access_token"]
    second_token = admin_auth.authenticate(second["email"], "SecureDemo!123")["access_token"]
    assert admin_auth.revoke_administrator_sessions(first["admin_id"]) == 1
    with pytest.raises(ValueError):
        admin_auth.validate_session(first_token)
    assert admin_auth.validate_session(second_token)["email"] == second["email"]
