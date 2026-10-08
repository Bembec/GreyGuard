import sqlite3
import pytest
from backend.app import admin_auth


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    path = tmp_path / "rbac.db"
    monkeypatch.setattr(admin_auth, "database_path", path)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_PASSWORD", raising=False)
    admin_auth.initialize_admin_auth()
    return path


def create_admin():
    return admin_auth.create_administrator(
        "admin@greyguard.local", "GreyGuard Admin", "PLATFORM_ADMIN", "SecureDemo!123"
    )


def test_password_is_not_stored_in_plaintext(isolated):
    create_admin()
    with sqlite3.connect(isolated) as connection:
        stored = connection.execute("SELECT password_hash FROM administrators").fetchone()[0]
    assert stored != "SecureDemo!123"


def test_login_and_session_validation(isolated):
    create_admin()
    result = admin_auth.authenticate("admin@greyguard.local", "SecureDemo!123")
    assert result["access_token"].startswith("gga_")
    assert admin_auth.validate_session(result["access_token"])["role"] == "PLATFORM_ADMIN"


def test_invalid_password_is_rejected(isolated):
    create_admin()
    with pytest.raises(ValueError):
        admin_auth.authenticate("admin@greyguard.local", "incorrect-password")


def test_roles_enforce_distinct_permissions(isolated):
    auditor = {"role": "AUDITOR"}
    analyst = {"role": "SECURITY_ANALYST"}
    assert admin_auth.has_permission(auditor, "read")
    assert not admin_auth.has_permission(auditor, "incident:manage")
    assert admin_auth.has_permission(analyst, "incident:manage")
    assert not admin_auth.has_permission(analyst, "identity:manage")


def test_logout_revokes_session(isolated):
    create_admin()
    token = admin_auth.authenticate("admin@greyguard.local", "SecureDemo!123")["access_token"]
    assert admin_auth.revoke_session(token)
    with pytest.raises(ValueError):
        admin_auth.validate_session(token)


# -- first-install setup wizard -----------------------------------------------

def test_count_administrators_reflects_fresh_install(isolated):
    assert admin_auth.count_administrators() == 0
    create_admin()
    assert admin_auth.count_administrators() == 1


def test_setup_first_administrator_creates_platform_admin_and_signs_in(isolated):
    result = admin_auth.setup_first_administrator(
        "owner@greyguard.local", "First Owner", "SecureSetup!123",
    )
    assert result["administrator"]["role"] == "PLATFORM_ADMIN"
    assert result["administrator"]["email"] == "owner@greyguard.local"
    assert result["access_token"].startswith("gga_")
    # The issued session is immediately valid, not a separate login round trip.
    assert admin_auth.validate_session(result["access_token"])["email"] == "owner@greyguard.local"


def test_setup_first_administrator_rejects_when_an_administrator_already_exists(isolated):
    create_admin()
    with pytest.raises(ValueError, match="already exists"):
        admin_auth.setup_first_administrator("second@greyguard.local", "Second", "SecureSetup!123")
