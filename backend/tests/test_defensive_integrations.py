import pytest
from backend.app import defensive_integrations as controls
@pytest.fixture
def isolated(tmp_path,monkeypatch):
 monkeypatch.setattr(controls,"database_path",tmp_path/"optional.db");controls.initialize_defensive_integrations()
 return controls.create_connector("Support browser","owner","Approved ticket workflow",["support.example.com"],"consent-42")
def test_browser_connector_disabled_by_default(isolated):assert isolated["enabled"] is False and isolated["visible_indicator"] is True
def test_domain_and_credential_boundaries(isolated):
 controls.set_connector_enabled(isolated["connector_id"],True)
 with pytest.raises(PermissionError,match="allowlist"):controls.authorize_browser_access(isolated["connector_id"],"evil.example.com",["title"])
 with pytest.raises(PermissionError,match="prohibited"):controls.authorize_browser_access(isolated["connector_id"],"support.example.com",["cookie"])
def test_response_requires_separate_approver(isolated):
 response=controls.request_response("SUSPEND_AGENT","agent-a","Credential compromise",30,"owner")
 assert response["evidence_preserved"] is True
 with pytest.raises(PermissionError,match="separate approver"):controls.approve_response(response["response_id"],"owner")
 assert controls.approve_response(response["response_id"],"approver")["status"]=="APPROVED"
def test_hack_back_is_not_allowlisted(isolated):
 with pytest.raises(ValueError,match="not allowlisted"):controls.request_response("HACK_BACK","external-host","retaliate",30,"owner")
