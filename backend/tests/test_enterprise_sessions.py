from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from backend.app import admin_auth


@pytest.fixture()
def identity(tmp_path, monkeypatch):
    monkeypatch.setattr(admin_auth, "database_path", tmp_path / "identity.db")
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.delenv("GREYGUARD_BOOTSTRAP_PASSWORD", raising=False)
    admin_auth.initialize_admin_auth()
    return admin_auth.create_administrator(
        "owner@example.com", "Owner", "PLATFORM_ADMIN", "StrongPassword123!"
    )


def test_access_tokens_are_short_lived_and_refresh_is_issued(identity):
    result = admin_auth.authenticate("owner@example.com", "StrongPassword123!")
    expires = datetime.fromisoformat(result["expires_at"])
    assert expires - datetime.now(timezone.utc) <= timedelta(minutes=16)
    assert result["refresh_token"].startswith("ggr_")


def test_refresh_rotates_token_and_rejects_reuse(identity):
    first = admin_auth.authenticate("owner@example.com", "StrongPassword123!")
    second = admin_auth.refresh_access_token(first["refresh_token"])
    assert second["refresh_token"] != first["refresh_token"]
    assert admin_auth.validate_session(second["access_token"])["email"] == "owner@example.com"
    with pytest.raises(ValueError, match="reuse detected"):
        admin_auth.refresh_access_token(first["refresh_token"])
    with pytest.raises(ValueError, match="revoked"):
        admin_auth.validate_session(second["access_token"])


def test_mfa_enrollment_requires_valid_totp(identity):
    enrollment = admin_auth.begin_mfa_enrollment(identity["admin_id"])
    code = admin_auth._totp(enrollment["secret"])
    confirmed = admin_auth.confirm_mfa(identity["admin_id"], code)
    assert confirmed["mfa_enabled"] is True
    with pytest.raises(PermissionError, match="MFA_REQUIRED"):
        admin_auth.authenticate("owner@example.com", "StrongPassword123!")
    assert admin_auth.authenticate("owner@example.com", "StrongPassword123!", code)["access_token"]


def test_expired_password_fails_closed(identity):
    with sqlite3.connect(admin_auth.database_path) as connection:
        connection.execute(
            "UPDATE administrators SET password_expires_at=? WHERE admin_id=?",
            ((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(), identity["admin_id"]),
        )
    with pytest.raises(ValueError, match="expired"):
        admin_auth.authenticate("owner@example.com", "StrongPassword123!")


def test_device_inventory_and_individual_revocation(identity):
    admin_auth.authenticate(
        "owner@example.com", "StrongPassword123!", device_name="Security workstation",
        ip_address="127.0.0.1",
    )
    sessions = admin_auth.list_sessions(identity["admin_id"])
    assert sessions[0]["device_name"] == "Security workstation"
    admin_auth.revoke_session_by_id(identity["admin_id"], sessions[0]["session_id"])
    assert admin_auth.list_sessions(identity["admin_id"])[0]["revoked_at"] is not None
