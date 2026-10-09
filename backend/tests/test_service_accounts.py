import pytest

from backend.app import service_accounts


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    path = tmp_path / "service-accounts.db"
    monkeypatch.setattr(service_accounts, "database_path", path)
    service_accounts.initialize_service_accounts()
    return path


def create_account():
    return service_accounts.create_service_account(
        "Deployment Bot", "CI deployment identity",
        ["tools:execute", "audit:read"], 30, "admin",
    )


def test_create_reveals_key_once_and_stores_only_metadata(isolated_database):
    account = create_account()
    assert account["issued_key"]["api_key"].startswith("ggsa_")
    listed = service_accounts.list_service_accounts()[0]
    assert "issued_key" not in listed
    assert "api_key" not in listed["keys"][0]


def test_key_authentication_records_usage(isolated_database):
    created = create_account()
    key = created["issued_key"]["api_key"]
    identity = service_accounts.authenticate_service_key(key, "tools:execute")
    assert identity["authenticated"] is True
    assert service_accounts.get_service_account(created["account_id"])["use_count"] == 1


def test_missing_scope_is_rejected(isolated_database):
    key = create_account()["issued_key"]["api_key"]
    with pytest.raises(PermissionError, match="scope"):
        service_accounts.authenticate_service_key(key, "policy:read")


def test_rotation_revokes_previous_key(isolated_database):
    created = create_account()
    old_key = created["issued_key"]["api_key"]
    rotated = service_accounts.rotate_service_account_key(created["account_id"], 60, "admin")
    with pytest.raises(ValueError, match="revoked"):
        service_accounts.authenticate_service_key(old_key)
    assert service_accounts.authenticate_service_key(rotated["issued_key"]["api_key"])["authenticated"]


def test_revocation_blocks_all_usage(isolated_database):
    created = create_account()
    service_accounts.revoke_service_account(created["account_id"], "admin")
    with pytest.raises(ValueError, match="revoked"):
        service_accounts.authenticate_service_key(created["issued_key"]["api_key"])


def test_unsupported_scope_is_rejected(isolated_database):
    with pytest.raises(ValueError, match="Unsupported"):
        service_accounts.create_service_account("Bad Bot", "", ["admin:all"], 30, "admin")


def test_service_accounts_are_isolated_per_organization(isolated_database):
    default_account = create_account()
    other = service_accounts.create_service_account(
        "Deployment Bot", "Other org's identical name is allowed", ["tools:execute"], 30, "admin",
        org_id="org_other",
    )
    assert [a["account_id"] for a in service_accounts.list_service_accounts("org_default")] == [default_account["account_id"]]
    assert [a["account_id"] for a in service_accounts.list_service_accounts("org_other")] == [other["account_id"]]
    with pytest.raises(KeyError):
        service_accounts.get_service_account(other["account_id"], org_id="org_default")
    with pytest.raises(KeyError):
        service_accounts.revoke_service_account(default_account["account_id"], "admin", org_id="org_other")
    identity = service_accounts.authenticate_service_key(other["issued_key"]["api_key"])
    assert identity["org_id"] == "org_other"
