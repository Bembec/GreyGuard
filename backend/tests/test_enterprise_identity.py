import sqlite3

import pytest

from backend.app import admin_auth, enterprise_identity


@pytest.fixture()
def identity(tmp_path, monkeypatch):
    path = tmp_path / "enterprise.db"
    monkeypatch.setattr(admin_auth, "database_path", path)
    monkeypatch.setattr(enterprise_identity, "database_path", path)
    admin_auth.initialize_admin_auth(); enterprise_identity.initialize_enterprise_identity()
    owner = admin_auth.create_administrator("owner@example.com", "Owner", "PLATFORM_ADMIN", "StrongPassword123!")
    reviewer = admin_auth.create_administrator("reviewer@example.com", "Reviewer", "PLATFORM_ADMIN", "StrongPassword123!")
    return owner, reviewer


def test_oidc_provider_and_role_mapping(identity):
    owner, _ = identity
    provider = enterprise_identity.save_provider(owner["admin_id"], "Entra ID", "https://login.example.com/tenant/v2.0", "client-123", ["example.com"])
    assert provider["discovery_url"].endswith("/.well-known/openid-configuration")
    mapping = enterprise_identity.add_role_mapping(owner["admin_id"], provider["provider_id"], "groups", "security-team", "SECURITY_ANALYST")
    assert mapping["greyguard_role"] == "SECURITY_ANALYST"


def test_provider_rejects_insecure_issuer(identity):
    with pytest.raises(ValueError, match="HTTPS"):
        enterprise_identity.save_provider(identity[0]["admin_id"], "Unsafe", "http://idp.example", "client")


def test_workload_certificate_is_fingerprinted_not_stored(identity):
    pem = "-----BEGIN CERTIFICATE-----\nTEST-CERTIFICATE-MATERIAL\n-----END CERTIFICATE-----"
    workload = enterprise_identity.create_workload_identity(identity[0]["admin_id"], "production-agent", "spiffe://greyguard/agent", pem, ["read_file"])
    assert len(workload["certificate_thumbprint"]) == 64
    with sqlite3.connect(enterprise_identity.database_path) as connection:
        assert pem not in str(connection.execute("SELECT * FROM workload_identities").fetchall())


def test_elevation_requires_separate_approver(identity):
    owner, reviewer = identity
    request = enterprise_identity.request_elevation(owner["admin_id"], "PLATFORM_ADMIN", "Investigate active incident")
    with pytest.raises(ValueError, match="different administrator"):
        enterprise_identity.decide_elevation(owner["admin_id"], request["elevation_id"], True)
    assert enterprise_identity.decide_elevation(reviewer["admin_id"], request["elevation_id"], True)["status"] == "APPROVED"


def test_break_glass_requires_designation_and_mfa(identity):
    owner, _ = identity
    with pytest.raises(PermissionError):
        enterprise_identity.activate_break_glass(owner["admin_id"], "Production identity provider outage")
    with sqlite3.connect(enterprise_identity.database_path) as connection:
        connection.execute("UPDATE administrators SET break_glass=1,mfa_enabled=1 WHERE admin_id=?", (owner["admin_id"],))
    result = enterprise_identity.activate_break_glass(owner["admin_id"], "Production identity provider outage")
    assert result["status"] == "ACTIVE"


def test_summary_reports_governed_identity_state(identity):
    assert enterprise_identity.identity_summary() == {"providers": 0, "workload_identities": 0, "pending_elevations": 0, "active_break_glass": 0}
