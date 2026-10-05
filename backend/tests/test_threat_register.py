import pytest
from backend.app import threat_register as register

@pytest.fixture
def isolated(tmp_path,monkeypatch):
    path=tmp_path/"threats.db";monkeypatch.setattr(register,"database_path",path);register.initialize_threat_register();return path

def complete_payload(**changes):
    value={"status":"OPEN","severity":"HIGH","asset":"Agent credentials","threat_actor":"External attacker","attack_path":"Credential copied from an unsafe client","existing_controls":["Hashing","Rotation"],"residual_risk":"MEDIUM","test_evidence":["backend/tests/test_admin_auth.py"],"incident_response":"Revoke credentials and investigate affected sessions","owner":"Identity Team","review_date":"2030-01-01"};value.update(changes);return value

def test_catalog_contains_every_roadmap_threat(isolated):
    assert len(register.list_threats())==30

def test_update_records_governance_and_history(isolated):
    item=register.update_threat("CREDENTIAL_THEFT",complete_payload(),"owner@example.com")
    assert item["residual_risk"]=="MEDIUM" and register.threat_history(item["threat_id"])

def test_closed_risk_requires_evidence(isolated):
    with pytest.raises(ValueError,match="Closure requires"):
        register.update_threat("CREDENTIAL_THEFT",complete_payload(status="MITIGATED",test_evidence=[]),"owner")

def test_summary_highlights_unreviewed_risks(isolated):
    assert register.threat_summary()["needs_review"]==30
