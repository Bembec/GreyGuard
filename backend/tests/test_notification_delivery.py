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
