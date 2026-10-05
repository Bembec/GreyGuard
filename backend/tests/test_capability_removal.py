import sqlite3,pytest
from backend.app import capability_removal as removal
@pytest.fixture
def isolated(tmp_path,monkeypatch):
 path=tmp_path/"remove.db";monkeypatch.setattr(removal,"database_path",path);removal.initialize_capability_removal()
 with sqlite3.connect(path) as c:c.execute("CREATE TABLE universal_capability_controls(capability TEXT PRIMARY KEY,enabled INTEGER,integration_kill_switch INTEGER,updated_at TEXT,updated_by TEXT)");c.execute("INSERT INTO universal_capability_controls VALUES('SIMULATION_LAB',1,0,'now','owner')")
 return path
def test_begin_removal_immediately_fails_closed(isolated):
 item=removal.begin_removal("SIMULATION_LAB","Capability retirement","owner")
 with sqlite3.connect(isolated) as c:assert c.execute("SELECT enabled,integration_kill_switch FROM universal_capability_controls").fetchone()==(0,1)
 assert item["steps"][0]["step_name"]=="DISABLE_INTERFACE"
def test_steps_must_be_completed_in_order(isolated):
 item=removal.begin_removal("SIMULATION_LAB","Capability retirement","owner")
 with pytest.raises(PermissionError,match="in order"):removal.complete_step(item["removal_id"],"REVOKE_CREDENTIALS","revoked","owner")
def test_completion_requires_evidence(isolated):
 item=removal.begin_removal("SIMULATION_LAB","Capability retirement","owner")
 with pytest.raises(ValueError,match="evidence"):removal.complete_step(item["removal_id"],"DISABLE_INTERFACE","","owner")
def test_emergency_shutdown_creates_audited_workflow(isolated):
 result=removal.emergency_shutdown("Suspected control compromise","owner")
 assert result["new_requests_frozen"] and result["audit_evidence_preserved"] and result["workflows"]
