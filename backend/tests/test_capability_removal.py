import sqlite3,pytest
from backend.app import capability_removal as removal
@pytest.fixture
def isolated(tmp_path,monkeypatch):
 path=tmp_path/"remove.db";monkeypatch.setattr(removal,"database_path",path);removal.initialize_capability_removal()
 with sqlite3.connect(path) as c:c.execute("CREATE TABLE universal_capability_controls(capability TEXT NOT NULL,org_id TEXT NOT NULL,enabled INTEGER,integration_kill_switch INTEGER,updated_at TEXT,updated_by TEXT,PRIMARY KEY(capability,org_id))");c.execute("INSERT INTO universal_capability_controls VALUES('SIMULATION_LAB','org_default',1,0,'now','owner')")
 return path
def test_begin_removal_immediately_fails_closed(isolated):
 item=removal.begin_removal("SIMULATION_LAB","Capability retirement","owner","org_default")
 with sqlite3.connect(isolated) as c:assert c.execute("SELECT enabled,integration_kill_switch FROM universal_capability_controls WHERE org_id='org_default'").fetchone()==(0,1)
 assert item["steps"][0]["step_name"]=="DISABLE_INTERFACE"
def test_steps_must_be_completed_in_order(isolated):
 item=removal.begin_removal("SIMULATION_LAB","Capability retirement","owner","org_default")
 with pytest.raises(PermissionError,match="in order"):removal.complete_step(item["removal_id"],"REVOKE_CREDENTIALS","revoked","owner","org_default")
def test_completion_requires_evidence(isolated):
 item=removal.begin_removal("SIMULATION_LAB","Capability retirement","owner","org_default")
 with pytest.raises(ValueError,match="evidence"):removal.complete_step(item["removal_id"],"DISABLE_INTERFACE","","owner","org_default")
def test_emergency_shutdown_creates_audited_workflow(isolated):
 result=removal.emergency_shutdown("Suspected control compromise","owner","org_default")
 assert result["new_requests_frozen"] and result["audit_evidence_preserved"] and result["workflows"]
def test_removals_are_scoped_to_their_organization(isolated,tmp_path):
 with sqlite3.connect(isolated) as c:c.execute("INSERT INTO universal_capability_controls VALUES('SIMULATION_LAB','org_b',1,0,'now','owner')")
 removal.begin_removal("SIMULATION_LAB","Capability retirement","owner","org_default")
 removal.begin_removal("SIMULATION_LAB","Capability retirement","owner","org_b")
 assert len(removal.list_removals("org_default"))==1
 assert len(removal.list_removals("org_b"))==1
