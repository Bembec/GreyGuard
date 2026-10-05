import sqlite3
import pytest
from backend.app import audit_integrity

@pytest.fixture()
def ledger(tmp_path,monkeypatch):
 path=tmp_path/"audit.db";monkeypatch.setattr(audit_integrity,"database_path",path)
 with sqlite3.connect(path) as c:
  c.execute("CREATE TABLE audit_events(id INTEGER PRIMARY KEY,agent_name TEXT,timestamp TEXT,action TEXT,decision TEXT,approval TEXT,risk_added INTEGER,risk_score INTEGER,risk_level TEXT,agent_status TEXT,blocked_attempts INTEGER)")
  c.execute("INSERT INTO audit_events VALUES(1,'agent','2026-01-01T00:00:00+00:00','read','ALLOW','NOT_REQUIRED',0,0,'LOW','ACTIVE',0)")
 audit_integrity.initialize_audit_integrity();return path

def test_chain_verifies_and_detects_source_tampering(ledger):
 assert audit_integrity.verify_integrity("auditor")["valid"] is True
 with sqlite3.connect(ledger) as c:c.execute("UPDATE audit_events SET decision='BLOCK' WHERE id=1")
 result=audit_integrity.verify_integrity("auditor")
 assert result["valid"] is False and result["first_invalid_sequence"]==1

def test_immutable_mode_cannot_be_disabled(ledger):
 audit_integrity.update_retention(365,True,"owner")
 with pytest.raises(PermissionError,match="cannot be disabled"):audit_integrity.update_retention(365,False,"owner")

def test_legal_hold_blocks_retention_deletion(ledger):
 audit_integrity.update_retention(30,False,"owner")
 audit_integrity.create_legal_hold("Investigation","Preserve incident evidence",None,None,None,"owner")
 with pytest.raises(PermissionError,match="legal hold"):audit_integrity.apply_retention("owner",True)

def test_retention_requires_explicit_confirmation(ledger):
 with pytest.raises(PermissionError,match="confirmation"):audit_integrity.apply_retention("owner",False)
