import pytest
from backend.app import adversarial_simulations as lab
@pytest.fixture
def isolated(tmp_path,monkeypatch):
 monkeypatch.setattr(lab,"database_path",tmp_path/"sim.db");lab.initialize_simulations();return lab
def test_lab_disabled_by_default(isolated):
 assert isolated.simulation_status()["enabled"] is False
 with pytest.raises(PermissionError,match="disabled"):isolated.run_simulation("sim-keylogger","owner")
def test_catalog_uses_only_fictional_non_operational_targets(isolated):
 assert len(isolated.scenario_catalog())==18
 assert all(not item["operational"] and item["fictional_target"].endswith(".example") for item in isolated.scenario_catalog())
def test_simulation_has_no_side_effects(isolated):
 isolated.set_enabled(True,"owner");result=isolated.run_simulation("sim-ransomware","owner")
 assert result["simulated"] is True and result["real_action_executed"] is False
 assert not any(result[key] for key in ("filesystem_side_effect","process_side_effect","network_side_effect"))
 assert result["decision"]=="REFUSED" and result["environment_reset"] is True
def test_arbitrary_scenarios_are_rejected(isolated):
 isolated.set_enabled(True,"owner")
 with pytest.raises(KeyError,match="Predefined"):isolated.run_simulation("custom-command","owner")
def test_module_does_not_import_production_executor():
 source=__import__("inspect").getsource(lab)
 assert "tool_gateway" not in source and "subprocess" not in source and "socket" not in source
