import pytest
from backend.app import secret_manager

@pytest.fixture()
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(secret_manager,"database_path",tmp_path/"secrets.db")
    secret_manager.initialize_secret_manager()

def test_values_are_never_stored(isolated,monkeypatch):
    monkeypatch.setenv("GREYGUARD_TEST_SECRET","super-private-value")
    item=secret_manager.create_secret("Demo","GREYGUARD_TEST_SECRET","admin")
    assert "super-private-value" not in str(item)
    assert secret_manager.resolve_secret(item["secret_id"],"admin")=="super-private-value"
    assert "super-private-value" not in str(secret_manager.list_secrets())

def test_redaction_removes_environment_secret(isolated,monkeypatch):
    monkeypatch.setenv("SERVICE_API_KEY","abcdefgh-secret")
    assert "abcdefgh-secret" not in secret_manager.redact("token=abcdefgh-secret")
    assert "[REDACTED]" in secret_manager.redact("token=abcdefgh-secret")

def test_revocation_blocks_retrieval(isolated,monkeypatch):
    monkeypatch.setenv("GREYGUARD_TEST_SECRET","super-private-value")
    item=secret_manager.create_secret("Demo","GREYGUARD_TEST_SECRET","admin")
    secret_manager.revoke_secret(item["secret_id"],"admin")
    with pytest.raises(ValueError,match="revoked"):
        secret_manager.resolve_secret(item["secret_id"],"admin")

def test_rotation_changes_reference_without_value(isolated):
    item=secret_manager.create_secret("Demo","OLD_SECRET_NAME","admin")
    rotated=secret_manager.rotate_secret(item["secret_id"],"NEW_SECRET_NAME","admin")
    assert rotated["reference"]=="NEW_SECRET_NAME"
    assert rotated["rotated_at"]

def test_secrets_can_share_a_name_across_organizations(isolated):
    default_secret=secret_manager.create_secret("Demo","DEFAULT_SECRET_NAME","admin",org_id="org_default")
    other_secret=secret_manager.create_secret("Demo","OTHER_SECRET_NAME","admin",org_id="org_other")
    assert default_secret["secret_id"]!=other_secret["secret_id"]
    assert [s["secret_id"] for s in secret_manager.list_secrets("org_default")]==[default_secret["secret_id"]]
    assert [s["secret_id"] for s in secret_manager.list_secrets("org_other")]==[other_secret["secret_id"]]
    with pytest.raises(KeyError):secret_manager.get_secret(other_secret["secret_id"],org_id="org_default")

def test_emergency_revoke_never_revokes_another_organizations_secret(isolated,monkeypatch):
    monkeypatch.setenv("GREYGUARD_TEST_SECRET","super-private-value")
    default_secret=secret_manager.create_secret("Demo","GREYGUARD_TEST_SECRET","admin",org_id="org_default")
    other_secret=secret_manager.create_secret("Demo2","GREYGUARD_TEST_SECRET","admin",org_id="org_other")
    result=secret_manager.emergency_revoke_all("admin",org_id="org_other")
    assert result["revoked"]==1
    assert secret_manager.get_secret(other_secret["secret_id"],org_id="org_other")["status"]=="REVOKED"
    assert secret_manager.get_secret(default_secret["secret_id"],org_id="org_default")["status"]=="ACTIVE"
