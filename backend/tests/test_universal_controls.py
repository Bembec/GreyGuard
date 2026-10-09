import pytest
from datetime import datetime,timedelta,timezone
from backend.app import universal_controls as controls
@pytest.fixture
def isolated(tmp_path,monkeypatch):monkeypatch.setattr(controls,"database_path",tmp_path/"controls.db");controls.initialize_universal_controls();return controls
def config(**changes):
 base={"enabled":True,"owner":"Security Owner","purpose":"Controlled defensive operation","permissions":["RUN"],"agent_allowlist":["agent-a"],"target_allowlist":["target-a"],"expires_at":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),"human_approval":True,"dry_run":True,"rate_limit_per_minute":10,"resource_limit":5}
 base.update(changes);return base
def test_disabled_means_disabled(isolated):
 with pytest.raises(PermissionError,match="disabled"):isolated.authorize("SIMULATION_LAB","owner","org_default","RUN",approved=True)
def test_exact_manifest_approval_and_dry_run(isolated):
 isolated.configure_control("SIMULATION_LAB",config(),"owner","org_default")
 with pytest.raises(PermissionError,match="manifest"):isolated.authorize("SIMULATION_LAB","owner","org_default","OTHER","target-a","agent-a",True,True)
 with pytest.raises(PermissionError,match="approval"):isolated.authorize("SIMULATION_LAB","owner","org_default","RUN","target-a","agent-a",False,True)
 with pytest.raises(PermissionError,match="dry-run"):isolated.authorize("SIMULATION_LAB","owner","org_default","RUN","target-a","agent-a",True,False)
 assert isolated.authorize("SIMULATION_LAB","owner","org_default","RUN","target-a","agent-a",True,True)["authorized"]
def test_kill_switches_fail_closed(isolated):
 isolated.configure_control("DEFENSIVE_RESPONSE",config(global_kill_switch=True),"owner","org_default")
 with pytest.raises(PermissionError,match="kill switch"):isolated.authorize("DEFENSIVE_RESPONSE","owner","org_default","RUN","target-a","agent-a",True,True)
def test_enabled_requires_owner_purpose_manifest_and_expiry(isolated):
 with pytest.raises(ValueError,match="owner"):isolated.configure_control("ENDPOINT_TELEMETRY",{"enabled":True},"owner","org_default")
def test_removal_plan_is_complete(isolated):assert len(isolated.removal_plan("EXECUTION_ISOLATION")["steps"])>=8
def test_controls_are_isolated_per_organization(isolated):
 isolated.configure_control("SIMULATION_LAB",config(),"owner","org_a")
 assert isolated.authorize("SIMULATION_LAB","owner","org_a","RUN","target-a","agent-a",True,True)["authorized"]
 with pytest.raises(PermissionError,match="disabled"):isolated.authorize("SIMULATION_LAB","owner","org_b","RUN","target-a","agent-a",True,True)
