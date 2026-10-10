from datetime import datetime,timezone
import pytest
from backend.app import notification_delivery as delivery
@pytest.fixture()
def isolated(tmp_path,monkeypatch):monkeypatch.setattr(delivery,"database_path",tmp_path/"delivery.db");delivery.initialize_notification_delivery();return delivery
def make(module,**changes):
 data=dict(name="SOC",channel="SLACK",endpoint_reference="https://hooks.example.test/slack",enabled=True,minimum_severity="HIGH",quiet_start_hour=None,quiet_end_hour=None,critical_bypass=True,escalation_minutes=15,actor="owner");data.update(changes);return module.save_destination(**data)
def test_destination_is_disabled_by_default(isolated):
 item=make(isolated,enabled=False);assert item["credentials_stored"] is False
 with pytest.raises(PermissionError):isolated.queue_notification(item["destination_id"],{"severity":"HIGH"})
def test_deduplication_prevents_repeated_delivery(isolated):
 item=make(isolated);event={"event_type":"AUTH","source_id":"evt_1","severity":"HIGH","title":"Alert","summary":"Review"}
 assert isolated.queue_notification(item["destination_id"],event)["status"]=="QUEUED"
 assert isolated.queue_notification(item["destination_id"],event)["status"]=="DEDUPLICATED"
def test_quiet_hours_delay_noncritical_events(isolated):
 item=make(isolated,quiet_start_hour=22,quiet_end_hour=6);now=datetime(2026,10,5,23,tzinfo=timezone.utc)
 result=isolated.queue_notification(item["destination_id"],{"event_type":"AUTH","source_id":"2","severity":"HIGH","title":"Alert"},now=now)
 assert result["available_at"]>result["created_at"]
def test_critical_event_can_bypass_quiet_hours(isolated):
 item=make(isolated,quiet_start_hour=22,quiet_end_hour=6);now=datetime(2026,10,5,23,tzinfo=timezone.utc)
 result=isolated.queue_notification(item["destination_id"],{"event_type":"AUTH","source_id":"3","severity":"CRITICAL","title":"Alert"},now=now)
 assert result["available_at"]==result["created_at"]
def test_template_rejects_unknown_fields(isolated):
 with pytest.raises(ValueError,match="unsupported field"):isolated.save_template("Bad","AUTH","{password}","Body","owner")
@pytest.mark.parametrize("channel",sorted(delivery.CHANNELS))
def test_supported_channel_delivery_evidence(isolated,channel):
 item=make(isolated,name=channel,channel=channel);queued=isolated.queue_notification(item["destination_id"],{"event_type":"TEST","source_id":channel,"severity":"HIGH","title":"Test"});sent=[];isolated.process_deliveries(lambda ref,payload,**_:sent.append((ref,payload)));assert sent and isolated.list_configuration()["recent_deliveries"][0]["status"]=="DELIVERED"
def test_destinations_and_templates_can_share_a_name_across_organizations(isolated):
 default_item=make(isolated,org_id="org_default");other_item=make(isolated,org_id="org_other")
 assert default_item["destination_id"]!=other_item["destination_id"]
 assert [d["destination_id"] for d in isolated.list_configuration("org_default")["destinations"]]==[default_item["destination_id"]]
 assert [d["destination_id"] for d in isolated.list_configuration("org_other")["destinations"]]==[other_item["destination_id"]]
 assert make(isolated,org_id="org_other",escalation_minutes=30)["destination_id"]==other_item["destination_id"]
 default_template=isolated.save_template("Standard","AUTH","{title}","{summary}","owner",org_id="org_default")
 other_template=isolated.save_template("Standard","AUTH","[other] {title}","{summary}","owner",org_id="org_other")
 assert default_template["template_id"]!=other_template["template_id"]
 assert [t["template_id"] for t in isolated.list_configuration("org_other")["templates"]]==[other_template["template_id"]]
def test_an_organization_cannot_use_another_organizations_destination_or_template(isolated):
 default_item=make(isolated,org_id="org_default");other_item=make(isolated,org_id="org_other")
 other_template=isolated.save_template("Other","AUTH","[other-secret] {title}","{summary}","owner",org_id="org_other")
 event={"event_type":"AUTH","source_id":"x","severity":"HIGH","title":"Alert"}
 with pytest.raises(KeyError):isolated.queue_notification(other_item["destination_id"],event,org_id="org_default")
 queued=isolated.queue_notification(default_item["destination_id"],event,other_template["template_id"],org_id="org_default")
 assert queued["subject"]=="Alert"  # the other org's template was not found, so the default rendering applied
 assert isolated.list_configuration("org_other")["recent_deliveries"]==[]
def test_worker_delivers_each_organizations_notifications_to_its_own_destination(isolated):
 default_item=make(isolated,org_id="org_default",endpoint_reference="https://default.example.test/hook")
 other_item=make(isolated,org_id="org_other",endpoint_reference="https://other.example.test/hook")
 event={"event_type":"AUTH","source_id":"y","severity":"HIGH","title":"Alert"}
 isolated.queue_notification(default_item["destination_id"],event,org_id="org_default")
 isolated.queue_notification(other_item["destination_id"],event,org_id="org_other")
 sent=[];assert isolated.process_deliveries(lambda ref,payload,**_:sent.append(ref))=={"processed":2}
 assert sorted(sent)==["https://default.example.test/hook","https://other.example.test/hook"]
 assert [d["status"] for d in isolated.list_configuration("org_other")["recent_deliveries"]]==["DELIVERED"]
def test_scheduled_report_notification_is_queued_within_the_schedules_organization(isolated,monkeypatch):
 import datetime as dt
 from backend.app import report_governance
 monkeypatch.setattr(report_governance,"database_path",isolated.database_path);monkeypatch.setenv("GREYGUARD_REPORT_SIGNING_KEY","a"*32)
 other_item=make(isolated,org_id="org_other",minimum_severity="INFO")
 past=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=5)).isoformat()
 report_governance.create_schedule("Other report","DAILY",past,"admin",notify_destination_id=other_item["destination_id"],org_id="org_other")
 result=report_governance.run_due_schedules(generator=lambda title,filters,actor,org_id=None:{"report_id":"rpt_1","title":title,"evidence_hash":"a"*64},
                                            exporter=lambda report_id,org_id=None:b"{}",notifier=isolated.queue_notification)
 assert [r["report_id"] for r in result["results"]]==["rpt_1"]
 subjects=[d["subject"] for d in isolated.list_configuration("org_other")["recent_deliveries"]]
 assert len(subjects)==1 and subjects[0].startswith("Other report") and subjects[0].endswith("is ready")
 assert isolated.list_configuration("org_default")["recent_deliveries"]==[]
def test_legacy_database_is_rebuilt_with_per_org_names(tmp_path,monkeypatch):
 import sqlite3
 path=tmp_path/"legacy.db"
 with sqlite3.connect(path) as c:
  c.execute("CREATE TABLE notification_destinations(destination_id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE COLLATE NOCASE,channel TEXT NOT NULL,endpoint_reference TEXT NOT NULL,enabled INTEGER NOT NULL,minimum_severity TEXT NOT NULL,quiet_start_hour INTEGER,quiet_end_hour INTEGER,critical_bypass INTEGER NOT NULL,escalation_minutes INTEGER NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL)")
  c.execute("CREATE TABLE notification_templates(template_id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,event_type TEXT NOT NULL,subject_template TEXT NOT NULL,body_template TEXT NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL)")
  c.execute("CREATE TABLE notification_deliveries(delivery_id TEXT PRIMARY KEY,destination_id TEXT NOT NULL,dedupe_key TEXT NOT NULL,created_at TEXT NOT NULL,available_at TEXT NOT NULL,status TEXT NOT NULL,attempts INTEGER NOT NULL,severity TEXT NOT NULL,subject TEXT NOT NULL,payload_json TEXT NOT NULL,delivered_at TEXT,last_error TEXT,claim_token TEXT,claimed_at TEXT,UNIQUE(destination_id,dedupe_key))")
  c.execute("INSERT INTO notification_destinations VALUES('ndst_legacy','SOC','SLACK','https://hooks.example.test/slack',1,'HIGH',NULL,NULL,1,15,'2026-01-01','owner')")
  c.execute("INSERT INTO notification_templates VALUES('tpl_legacy','Standard','AUTH','{title}','{summary}','2026-01-01','owner')")
  c.execute("INSERT INTO notification_deliveries VALUES('dlv_legacy','ndst_legacy','k','2026-01-01','2026-01-01','DELIVERED',1,'HIGH','s','{}',NULL,NULL,NULL,NULL)")
 monkeypatch.setattr(delivery,"database_path",path);delivery.initialize_notification_delivery()
 legacy=delivery.list_configuration("org_default")
 assert [d["destination_id"] for d in legacy["destinations"]]==["ndst_legacy"]
 assert legacy["destinations"][0]["max_attempts"]==delivery.DEFAULT_MAX_ATTEMPTS  # predated the column
 assert [t["template_id"] for t in legacy["templates"]]==["tpl_legacy"]
 assert [d["delivery_id"] for d in legacy["recent_deliveries"]]==["dlv_legacy"]
 assert make(delivery,org_id="org_other")["destination_id"]!="ndst_legacy"
 with sqlite3.connect(path) as c:
  assert not {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}&{"notification_destinations_org","notification_templates_org"}
