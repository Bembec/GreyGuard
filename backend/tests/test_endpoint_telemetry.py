import pytest
from backend.app import endpoint_telemetry

@pytest.fixture
def isolated(tmp_path,monkeypatch):
 monkeypatch.setattr(endpoint_telemetry,"database_path",tmp_path/"endpoint.db");endpoint_telemetry.initialize_endpoint_telemetry()
 return endpoint_telemetry.register_collector("Finance endpoint","owner","Approved health telemetry","consent-2026",["PROCESS_HEALTH","FILESYSTEM_EVENTS"],["C:/GreyGuard/approved"],30,"aa:"*31+"aa")

def test_collector_is_disabled_by_default(isolated):assert isolated["enabled"] is False and isolated["visible_indicator"] is True
def test_collection_requires_explicit_enablement(isolated):
 with pytest.raises(PermissionError,match="disabled"):endpoint_telemetry.validate_event(isolated["collector_id"],"PROCESS_HEALTH",{"process":"agent","status":"healthy"})
def test_prohibited_content_is_rejected(isolated):
 endpoint_telemetry.set_collector_enabled(isolated["collector_id"],True,"owner")
 with pytest.raises(PermissionError,match="prohibited"):endpoint_telemetry.validate_event(isolated["collector_id"],"PROCESS_HEALTH",{"command_line":"secret"})
def test_filesystem_scope_is_enforced(isolated):
 endpoint_telemetry.set_collector_enabled(isolated["collector_id"],True,"owner")
 with pytest.raises(PermissionError,match="approved directories"):endpoint_telemetry.validate_event(isolated["collector_id"],"FILESYSTEM_EVENT",{"path":"C:/Windows/System32/file"})
def test_uninstall_requires_confirmation(isolated):
 with pytest.raises(PermissionError,match="confirmation"):endpoint_telemetry.uninstall_collector(isolated["collector_id"])
