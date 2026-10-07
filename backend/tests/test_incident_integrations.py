import hashlib,hmac,json
import pytest
from backend.app import incident_integrations as integrations
@pytest.fixture()
def isolated(tmp_path,monkeypatch):monkeypatch.setattr(integrations,"database_path",tmp_path/"incidents.db");integrations.initialize_incident_integrations();return integrations
def destination(module,**changes):
 data=dict(name="Jira SOC",system_type="JIRA",endpoint="https://jira.example.com",credential_reference="JIRA_TOKEN",project_or_table="SEC",enabled=True,actor="owner");data.update(changes);return module.save_destination(**data)
def test_disabled_destination_blocks_incident(isolated):
 item=destination(isolated,enabled=False);assert item["credentials_stored"] is False
 with pytest.raises(PermissionError):isolated.queue_incident(item["destination_id"],{"alert_id":"a1"})
def test_incident_deduplication_and_delivery_evidence(isolated):
 item=destination(isolated);alert={"alert_id":"a1","title":"Blocked action","summary":"Review","severity":"HIGH"};queued=isolated.queue_incident(item["destination_id"],alert);assert isolated.queue_incident(item["destination_id"],alert)["status"]=="DEDUPLICATED";integrations.process_incidents(lambda *_,**__:"JIRA-42");record=isolated.list_controls()["records"][0];assert queued["record_id"]==record["record_id"] and record["external_id"]=="JIRA-42"
def test_approval_link_is_single_use(isolated):
 link=isolated.create_approval_link("req_1","APPROVED",15,"owner");assert isolated.consume_approval_link(link["token"],"approver")["request_id"]=="req_1"
 with pytest.raises(ValueError,match="no longer active"):isolated.consume_approval_link(link["token"],"approver")
def test_signed_callback_rejects_tampering(isolated,monkeypatch):
 monkeypatch.setenv("CALLBACK_KEY","secret-callback-key");payload={"external_id":"JIRA-42","status":"OPEN"};serialized=json.dumps(payload,separators=(",",":"),sort_keys=True);signature="sha256="+hmac.new(b"secret-callback-key",serialized.encode(),hashlib.sha256).hexdigest();assert isolated.verify_callback("record",payload,signature,"CALLBACK_KEY")["signature_valid"]
 with pytest.raises(PermissionError):isolated.verify_callback("record",{"status":"CLOSED"},signature,"CALLBACK_KEY")
@pytest.mark.parametrize("system",sorted(integrations.SYSTEMS))
def test_supported_incident_systems(isolated,system):assert destination(isolated,name=system,system_type=system)["system_type"]==system
def test_external_id_prefers_jira_id_field():assert integrations._external_id_from_response(b'{"id":"JIRA-1"}',"fallback")=="JIRA-1"
def test_external_id_prefers_servicenow_sys_id():assert integrations._external_id_from_response(b'{"result":{"sys_id":"SN-1"}}',"fallback")=="SN-1"
def test_external_id_falls_back_on_unparsable_body():assert integrations._external_id_from_response(b"not json","idem-1")=="idem-1"
def test_external_id_falls_back_on_empty_body():assert integrations._external_id_from_response(b"","idem-2")=="idem-2"
