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
def test_destinations_can_share_a_name_across_organizations(isolated):
 default_item=destination(isolated,org_id="org_default");other_item=destination(isolated,org_id="org_other")
 assert default_item["destination_id"]!=other_item["destination_id"]
 assert [d["destination_id"] for d in isolated.list_controls("org_default")["destinations"]]==[default_item["destination_id"]]
 assert [d["destination_id"] for d in isolated.list_controls("org_other")["destinations"]]==[other_item["destination_id"]]
 # Saving the same name again within one org still updates in place rather than duplicating.
 assert destination(isolated,org_id="org_other",project_or_table="OPS")["destination_id"]==other_item["destination_id"]
 assert isolated.list_controls("org_default")["destinations"][0]["project_or_table"]=="SEC"
def test_an_organization_cannot_queue_to_another_organizations_destination(isolated):
 other_item=destination(isolated,org_id="org_other")
 with pytest.raises(KeyError):isolated.queue_incident(other_item["destination_id"],{"alert_id":"a1"},org_id="org_default")
 queued=isolated.queue_incident(other_item["destination_id"],{"alert_id":"a1"},org_id="org_other")
 assert queued["org_id"]=="org_other"
 assert isolated.list_controls("org_default")["records"]==[]
 assert [r["record_id"] for r in isolated.list_controls("org_other")["records"]]==[queued["record_id"]]
def test_worker_delivers_every_organizations_incidents_to_their_own_destinations(isolated):
 default_item=destination(isolated,org_id="org_default",endpoint="https://default.example.com");other_item=destination(isolated,org_id="org_other",endpoint="https://other.example.com")
 default_record=isolated.queue_incident(default_item["destination_id"],{"alert_id":"a1"},org_id="org_default");other_record=isolated.queue_incident(other_item["destination_id"],{"alert_id":"a1"},org_id="org_other")
 sent=[]
 def sender(system_type,endpoint,credential_reference,payload,*,idempotency_key=None):sent.append((endpoint,idempotency_key));return "EXT-"+idempotency_key
 assert isolated.process_incidents(sender)=={"processed":2}
 assert sorted(sent)==sorted([("https://default.example.com",default_record["record_id"]),("https://other.example.com",other_record["record_id"])])
 for org,record in (("org_default",default_record),("org_other",other_record)):
  controls=isolated.list_controls(org);assert controls["records"][0]["status"]=="CREATED" and controls["records"][0]["external_id"]=="EXT-"+record["record_id"];assert controls["destinations"][0]["last_success_at"]
 # Each record's delivery evidence is attributed to its own org, not the worker's.
 # Read with stdlib sqlite3 (bypassing tenant_guard): this check deliberately spans both orgs.
 import sqlite3
 from backend.app import outbound_delivery
 with sqlite3.connect(outbound_delivery.database_path) as c:evidence=c.execute("SELECT DISTINCT record_id,org_id FROM outbound_delivery_evidence WHERE record_id IN (?,?)",(default_record["record_id"],other_record["record_id"])).fetchall()
 assert sorted(evidence)==sorted([(default_record["record_id"],"org_default"),(other_record["record_id"],"org_other")])
def test_legacy_database_is_rebuilt_with_org_scoping(tmp_path,monkeypatch):
 import sqlite3
 path=tmp_path/"legacy.db"
 with sqlite3.connect(path) as c:
  # Shape from before max_attempts and the delivery columns existed.
  c.execute("""CREATE TABLE incident_destinations(destination_id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE COLLATE NOCASE,system_type TEXT NOT NULL,endpoint TEXT NOT NULL,credential_reference TEXT NOT NULL,project_or_table TEXT NOT NULL,enabled INTEGER NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,last_success_at TEXT,last_failure_at TEXT,last_error TEXT)""")
  c.execute("""CREATE TABLE external_incident_records(record_id TEXT PRIMARY KEY,destination_id TEXT NOT NULL,source_alert_id TEXT NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL,payload_json TEXT NOT NULL,external_id TEXT,delivered_at TEXT,last_error TEXT,UNIQUE(destination_id,source_alert_id))""")
  c.execute("INSERT INTO incident_destinations VALUES('idst_legacy','Jira SOC','JIRA','https://jira.example.com','JIRA_TOKEN','SEC',1,'2026-01-01','owner',NULL,NULL,NULL)")
  c.execute("INSERT INTO external_incident_records VALUES('incx_legacy','idst_legacy','a1','2026-01-01','QUEUED','{}',NULL,NULL,NULL)")
 # The pre-baseline delivery columns must be caught up before upgrading straight to org-scoped
 # code (see initialize_incident_integrations()), so emulate that step the way an operator would.
 with sqlite3.connect(path) as c:
  for column in ("attempts INTEGER NOT NULL DEFAULT 0","available_at TEXT","claim_token TEXT","claimed_at TEXT"):c.execute("ALTER TABLE external_incident_records ADD COLUMN "+column)
 monkeypatch.setattr(integrations,"database_path",path);integrations.initialize_incident_integrations()
 with sqlite3.connect(path) as c:
  tables={row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  available=c.execute("SELECT available_at FROM external_incident_records").fetchone()[0]
 assert "incident_destinations_org" not in tables and available=="2026-01-01"
 controls=integrations.list_controls("org_default")
 assert [(d["destination_id"],d["max_attempts"]) for d in controls["destinations"]]==[("idst_legacy",integrations.DEFAULT_MAX_ATTEMPTS)]
 assert [r["record_id"] for r in controls["records"]]==["incx_legacy"]
 assert destination(integrations,org_id="org_other")["destination_id"]!="idst_legacy"
