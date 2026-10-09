import pytest
from backend.app import adversarial_simulations as lab
@pytest.fixture
def isolated(tmp_path,monkeypatch):
 monkeypatch.setattr(lab,"database_path",tmp_path/"sim.db");lab.initialize_simulations();return lab
def test_lab_disabled_by_default(isolated):
 assert isolated.simulation_status("org_default")["enabled"] is False
 with pytest.raises(PermissionError,match="disabled"):isolated.run_simulation("sim-keylogger","owner","org_default")
def test_catalog_uses_only_fictional_non_operational_targets(isolated):
 assert len(isolated.scenario_catalog())==18
 assert all(not item["operational"] and item["fictional_target"].endswith(".example") for item in isolated.scenario_catalog())
def test_simulation_has_no_side_effects(isolated):
 isolated.set_enabled(True,"owner");result=isolated.run_simulation("sim-ransomware","owner","org_default")
 assert result["simulated"] is True and result["real_action_executed"] is False
 assert not any(result[key] for key in ("filesystem_side_effect","process_side_effect","network_side_effect"))
 assert result["decision"]=="REFUSED" and result["environment_reset"] is True
def test_arbitrary_scenarios_are_rejected(isolated):
 isolated.set_enabled(True,"owner")
 with pytest.raises(KeyError,match="Predefined"):isolated.run_simulation("custom-command","owner","org_default")
def test_module_does_not_import_production_executor():
 source=__import__("inspect").getsource(lab)
 assert "tool_gateway" not in source and "subprocess" not in source and "socket" not in source
def test_every_scenario_names_its_detecting_policy_and_danger(isolated):
 for item in isolated.scenario_catalog():
  assert "scope enforcement" in item["detected_by"].lower()
  assert len(item["why_dangerous"])>20
def test_simulation_creates_a_real_labelled_alert(isolated):
 import json
 isolated.set_enabled(True,"owner");result=isolated.run_simulation("sim-keylogger","owner","org_default")
 assert result["alert_created"] is True and result["evidence_preserved"] is True
 with isolated.sqlite3.connect(isolated.database_path) as c:
  row=c.execute("SELECT summary,event_type,evidence_json FROM security_alerts WHERE alert_id=?",(result["alert_id"],)).fetchone()
 assert row is not None and row[1]=="SIMULATION" and row[0].startswith("SIMULATION ONLY")
 assert json.loads(row[2])["simulated"] is True
def test_each_run_creates_its_own_alert(isolated):
 isolated.set_enabled(True,"owner")
 first=isolated.run_simulation("sim-ddos","owner","org_default");second=isolated.run_simulation("sim-ddos","owner","org_default")
 assert first["alert_id"] and second["alert_id"] and first["alert_id"]!=second["alert_id"]
def test_runs_are_scoped_to_their_organization(isolated):
 isolated.set_enabled(True,"owner",org_id="org_a");isolated.set_enabled(True,"owner",org_id="org_b")
 isolated.run_simulation("sim-ddos","owner","org_a")
 isolated.run_simulation("sim-ddos","owner","org_b")
 assert len(isolated.simulation_status("org_a")["runs"])==1
 assert len(isolated.simulation_status("org_b")["runs"])==1
def test_enablement_is_isolated_per_organization(isolated):
 isolated.set_enabled(True,"owner",org_id="org_other")
 assert isolated.simulation_status("org_default")["enabled"] is False
 assert isolated.simulation_status("org_other")["enabled"] is True
 with pytest.raises(PermissionError,match="disabled"):isolated.run_simulation("sim-keylogger","owner","org_default")
 assert isolated.run_simulation("sim-keylogger","owner","org_other")["simulated"] is True
