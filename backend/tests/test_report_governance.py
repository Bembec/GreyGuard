import pytest
from backend.app import report_governance

@pytest.fixture
def isolated(tmp_path,monkeypatch):
 monkeypatch.setattr(report_governance,"database_path",tmp_path/"governance.db")
 report_governance.initialize_report_governance()

def test_schedule_lifecycle(isolated):
 item=report_governance.create_schedule("Weekly evidence","weekly","2026-10-12T08:00:00Z","admin")
 assert item["enabled"] is True
 assert report_governance.disable_schedule(item["schedule_id"],"admin")["enabled"] is False

def test_manifest_signature_and_tamper_detection():
 report={"report_id":"r1","evidence_hash":"a"*64};key="k"*32
 manifest=report_governance.signed_manifest(report,{"json":"b"*64},key)
 assert report_governance.verify_manifest(manifest,key)
 manifest["evidence_hash"]="changed"
 assert not report_governance.verify_manifest(manifest,key)

def test_manifest_requires_strong_key():
 with pytest.raises(RuntimeError,match="32 characters"):
  report_governance.signed_manifest({"report_id":"r1","evidence_hash":"x"},{},"short")

def test_postmortem_template(isolated):
 item=report_governance.create_postmortem("inc-101","Authentication incident","admin")
 assert item["status"]=="DRAFT" and "root_cause" in item["template"]

def test_control_mapping_is_explicit():
 assert {row["framework"] for row in report_governance.compliance_mapping()} >= {"NIST CSF 2.0","ISO 27001:2022","SOC 2"}

def _stub_generator(title,filters,actor,org_id=None):
 return {"report_id":"rpt_stub","title":title,"filters":filters,"actor":actor,"evidence_hash":"a"*64}

def _stub_exporter(report_id,org_id=None):
 return b'{"stub":true}'

def test_due_schedule_is_generated_signed_and_rescheduled(isolated,monkeypatch):
 import datetime
 monkeypatch.setenv("GREYGUARD_REPORT_SIGNING_KEY","a"*32)
 past=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=5)).isoformat()
 item=report_governance.create_schedule("Weekly evidence","DAILY",past,"admin")
 result=report_governance.run_due_schedules(generator=_stub_generator,exporter=_stub_exporter,limit=5)
 assert result["processed"]==1
 assert result["results"][0]["report_id"]=="rpt_stub"
 refreshed=next(s for s in report_governance.list_schedules() if s["schedule_id"]==item["schedule_id"])
 assert refreshed["last_status"]=="COMPLETED"
 assert refreshed["next_run_at"]>past

def test_schedule_not_yet_due_is_not_run(isolated):
 import datetime
 future=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=1)).isoformat()
 report_governance.create_schedule("Future report","WEEKLY",future,"admin")
 result=report_governance.run_due_schedules(generator=_stub_generator,exporter=_stub_exporter)
 assert result["processed"]==0

def test_schedule_failure_is_recorded_without_raising(isolated):
 import datetime
 past=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=5)).isoformat()
 item=report_governance.create_schedule("Broken report","DAILY",past,"admin")
 def _broken_generator(title,filters,actor,org_id=None):raise RuntimeError("report backend offline")
 result=report_governance.run_due_schedules(generator=_broken_generator,exporter=_stub_exporter)
 assert result["processed"]==1
 assert result["results"]==[]
 refreshed=next(s for s in report_governance.list_schedules() if s["schedule_id"]==item["schedule_id"])
 assert refreshed["last_status"]=="FAILED"
 assert "offline" in refreshed["last_error"]

def test_schedule_notifies_configured_destination(isolated,monkeypatch):
 import datetime
 monkeypatch.setenv("GREYGUARD_REPORT_SIGNING_KEY","a"*32)
 past=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=5)).isoformat()
 item=report_governance.create_schedule("Notified report","DAILY",past,"admin",notify_destination_id="ndst_1")
 notified=[]
 report_governance.run_due_schedules(generator=_stub_generator,exporter=_stub_exporter,notifier=lambda dest,event,org_id:notified.append((dest,event,org_id)))
 assert notified and notified[0][0]=="ndst_1"
 assert notified[0][1]["event_type"]=="REPORT_READY"
 assert notified[0][2]=="org_default"

def test_monthly_frequency_advances_correctly():
 assert report_governance._next_run_after("2026-01-31T08:00:00+00:00","MONTHLY").startswith("2026-02-28")
 assert report_governance._next_run_after("2026-10-07T08:00:00+00:00","DAILY").startswith("2026-10-08")
 assert report_governance._next_run_after("2026-10-07T08:00:00+00:00","WEEKLY").startswith("2026-10-14")

def test_schedules_and_postmortems_are_isolated_per_organization(isolated):
 default_item=report_governance.create_schedule("Default org report","WEEKLY","2026-10-12T08:00:00Z","admin",org_id="org_default")
 other_item=report_governance.create_schedule("Other org report","WEEKLY","2026-10-12T08:00:00Z","admin",org_id="org_other")
 assert [s["schedule_id"] for s in report_governance.list_schedules("org_default")]==[default_item["schedule_id"]]
 assert [s["schedule_id"] for s in report_governance.list_schedules("org_other")]==[other_item["schedule_id"]]
 with pytest.raises(KeyError):report_governance.disable_schedule(other_item["schedule_id"],"admin",org_id="org_default")
 report_governance.create_postmortem("inc-1","Default incident","admin",org_id="org_default")
 with report_governance.sqlite3.connect(report_governance.database_path) as c:
  assert c.execute("SELECT org_id FROM incident_postmortems WHERE incident_id='inc-1'").fetchone()[0]=="org_default"

def test_due_schedules_across_orgs_each_generate_their_own_scoped_report(isolated):
 import datetime
 past=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=5)).isoformat()
 report_governance.create_schedule("Default org report","DAILY",past,"admin",org_id="org_default")
 report_governance.create_schedule("Other org report","DAILY",past,"admin",org_id="org_other")
 seen_org_ids=[]
 def _recording_generator(title,filters,actor,org_id=None):
  seen_org_ids.append(org_id);return {"report_id":f"rpt_{org_id}","title":title,"filters":filters,"actor":actor,"evidence_hash":"a"*64}
 result=report_governance.run_due_schedules(generator=_recording_generator,exporter=_stub_exporter,limit=10)
 assert result["processed"]==2
 assert set(seen_org_ids)=={"org_default","org_other"}
 assert len(report_governance.list_schedules("org_default"))==1
 assert len(report_governance.list_schedules("org_other"))==1
