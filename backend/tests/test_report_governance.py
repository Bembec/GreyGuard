import pytest
from backend.app import report_governance

@pytest.fixture
def isolated(tmp_path,monkeypatch):
 monkeypatch.setattr(report_governance,"database_path",tmp_path/"governance.db")
 report_governance.initialize_report_governance()

def test_schedule_lifecycle(isolated):
 item=report_governance.create_schedule("Weekly evidence","weekly","2026-10-12T08:00:00Z","admin")
 assert item["enabled"] is True
 assert report_governance.disable_schedule(item["schedule_id"],"admin")["enabled"] is False

def test_manifest_signature_and_tamper_detection():
 report={"report_id":"r1","evidence_hash":"a"*64};key="k"*32
 manifest=report_governance.signed_manifest(report,{"json":"b"*64},key)
 assert report_governance.verify_manifest(manifest,key)
 manifest["evidence_hash"]="changed"
 assert not report_governance.verify_manifest(manifest,key)

def test_manifest_requires_strong_key():
 with pytest.raises(RuntimeError,match="32 characters"):
  report_governance.signed_manifest({"report_id":"r1","evidence_hash":"x"},{},"short")

def test_postmortem_template(isolated):
 item=report_governance.create_postmortem("inc-101","Authentication incident","admin")
 assert item["status"]=="DRAFT" and "root_cause" in item["template"]

def test_control_mapping_is_explicit():
 assert {row["framework"] for row in report_governance.compliance_mapping()} >= {"NIST CSF 2.0","ISO 27001:2022","SOC 2"}
