"""Governed external notification delivery with quiet hours and evidence."""
import hashlib,json,uuid
from . import db_compat as sqlite3
from datetime import datetime,timedelta,timezone
from .database import database_path
from .observability import redact
from .outbound_delivery import (
 PermanentDeliveryError,SSRFBlocked,backoff_seconds,
 new_claim_token,record_evidence,safe_error,send_json,
)

CHANNELS={"EMAIL","SLACK","MICROSOFT_TEAMS","PAGERDUTY","OPSGENIE"}
WEBHOOK_CHANNELS=CHANNELS-{"EMAIL"}
SEVERITY_ORDER={"INFO":0,"LOW":1,"MEDIUM":2,"HIGH":3,"CRITICAL":4}
DEFAULT_MAX_ATTEMPTS=8
LEASE_SECONDS=120
def utc_now():return datetime.now(timezone.utc).isoformat()
def initialize_notification_delivery():
 with sqlite3.connect(database_path) as c:
  c.execute("""CREATE TABLE IF NOT EXISTS notification_destinations(destination_id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE COLLATE NOCASE,channel TEXT NOT NULL,endpoint_reference TEXT NOT NULL,enabled INTEGER NOT NULL,minimum_severity TEXT NOT NULL,quiet_start_hour INTEGER,quiet_end_hour INTEGER,critical_bypass INTEGER NOT NULL,escalation_minutes INTEGER NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL)""")
  c.execute("""CREATE TABLE IF NOT EXISTS notification_templates(template_id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,event_type TEXT NOT NULL,subject_template TEXT NOT NULL,body_template TEXT NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL)""")
  c.execute("""CREATE TABLE IF NOT EXISTS notification_deliveries(delivery_id TEXT PRIMARY KEY,destination_id TEXT NOT NULL,dedupe_key TEXT NOT NULL,created_at TEXT NOT NULL,available_at TEXT NOT NULL,status TEXT NOT NULL,attempts INTEGER NOT NULL,severity TEXT NOT NULL,subject TEXT NOT NULL,payload_json TEXT NOT NULL,delivered_at TEXT,last_error TEXT,UNIQUE(destination_id,dedupe_key))""")
  dest_columns={row[1] for row in c.execute("PRAGMA table_info(notification_destinations)")}
  if "max_attempts" not in dest_columns:c.execute(f"ALTER TABLE notification_destinations ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT {DEFAULT_MAX_ATTEMPTS}")
  delivery_columns={row[1] for row in c.execute("PRAGMA table_info(notification_deliveries)")}
  if "claim_token" not in delivery_columns:c.execute("ALTER TABLE notification_deliveries ADD COLUMN claim_token TEXT")
  if "claimed_at" not in delivery_columns:c.execute("ALTER TABLE notification_deliveries ADD COLUMN claimed_at TEXT")
def list_configuration():
 initialize_notification_delivery()
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;dest=[dict(r) for r in c.execute("SELECT * FROM notification_destinations ORDER BY name")];templates=[dict(r) for r in c.execute("SELECT * FROM notification_templates ORDER BY name")];recent=[dict(r) for r in c.execute("SELECT delivery_id,destination_id,created_at,status,attempts,severity,subject,delivered_at,last_error FROM notification_deliveries ORDER BY created_at DESC LIMIT 100")]
 for d in dest:d["enabled"]=bool(d["enabled"]);d["critical_bypass"]=bool(d["critical_bypass"]);d["credentials_stored"]=False
 return {"destinations":dest,"templates":templates,"recent_deliveries":recent,"channels":sorted(CHANNELS)}
def save_destination(name,channel,endpoint_reference,enabled,minimum_severity,quiet_start_hour,quiet_end_hour,critical_bypass,escalation_minutes,actor):
 channel=channel.upper();minimum_severity=minimum_severity.upper()
 if channel not in CHANNELS:raise ValueError("Unsupported notification channel.")
 if channel in WEBHOOK_CHANNELS and not endpoint_reference.startswith("https://"):raise ValueError("Webhook notification destinations must use HTTPS.")
 if minimum_severity not in SEVERITY_ORDER:raise ValueError("Unsupported minimum severity.")
 for hour in (quiet_start_hour,quiet_end_hour):
  if hour is not None and not 0<=hour<=23:raise ValueError("Quiet-hour values must be from 0 to 23.")
 if not 0<=escalation_minutes<=1440:raise ValueError("Escalation delay is outside the supported range.")
 did="ndst_"+uuid.uuid4().hex
 with sqlite3.connect(database_path) as c:
  old=c.execute("SELECT destination_id FROM notification_destinations WHERE name=?",(name.strip(),)).fetchone()
  if old:
   did=old[0];c.execute("UPDATE notification_destinations SET channel=?,endpoint_reference=?,enabled=?,minimum_severity=?,quiet_start_hour=?,quiet_end_hour=?,critical_bypass=?,escalation_minutes=? WHERE destination_id=?",(channel,endpoint_reference,int(enabled),minimum_severity,quiet_start_hour,quiet_end_hour,int(critical_bypass),escalation_minutes,did))
  else:c.execute("INSERT INTO notification_destinations(destination_id,name,channel,endpoint_reference,enabled,minimum_severity,quiet_start_hour,quiet_end_hour,critical_bypass,escalation_minutes,created_at,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(did,name.strip(),channel,endpoint_reference,int(enabled),minimum_severity,quiet_start_hour,quiet_end_hour,int(critical_bypass),escalation_minutes,utc_now(),actor))
 return next(d for d in list_configuration()["destinations"] if d["destination_id"]==did)
def save_template(name,event_type,subject_template,body_template,actor):
 if any(x not in {"title","severity","summary","event_type","resource_path"} for x in _fields(subject_template+body_template)):raise ValueError("Template contains an unsupported field.")
 tid="tpl_"+uuid.uuid4().hex
 with sqlite3.connect(database_path) as c:
  old=c.execute("SELECT template_id FROM notification_templates WHERE name=?",(name.strip(),)).fetchone()
  if old:tid=old[0];c.execute("UPDATE notification_templates SET event_type=?,subject_template=?,body_template=? WHERE template_id=?",(event_type,subject_template,body_template,tid))
  else:c.execute("INSERT INTO notification_templates VALUES(?,?,?,?,?,?,?)",(tid,name.strip(),event_type,subject_template,body_template,utc_now(),actor))
 return next(t for t in list_configuration()["templates"] if t["template_id"]==tid)
def _fields(text):
 import string
 return [name for _,name,_,_ in string.Formatter().parse(text) if name]
def _quiet(destination,now):
 start,end=destination["quiet_start_hour"],destination["quiet_end_hour"]
 if start is None or end is None:return False
 hour=now.hour
 return start<=hour<end if start<end else hour>=start or hour<end
def queue_notification(destination_id,event,template_id=None,now=None):
 initialize_notification_delivery();now=now or datetime.now(timezone.utc);safe=redact(event);severity=str(safe.get("severity","INFO")).upper()
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;d=c.execute("SELECT * FROM notification_destinations WHERE destination_id=?",(destination_id,)).fetchone()
  if not d:raise KeyError("Notification destination not found.")
  if not d["enabled"]:raise PermissionError("Notification destination is disabled.")
  if SEVERITY_ORDER.get(severity,-1)<SEVERITY_ORDER[d["minimum_severity"]]:return {"status":"FILTERED","reason":"Below minimum severity."}
  template=c.execute("SELECT * FROM notification_templates WHERE template_id=?",(template_id,)).fetchone() if template_id else None
  values={k:str(safe.get(k,"")) for k in ("title","severity","summary","event_type","resource_path")};subject=(template["subject_template"].format(**values) if template else values["title"]);body=(template["body_template"].format(**values) if template else values["summary"])
  dedupe=hashlib.sha256(f"{d['destination_id']}:{safe.get('event_type')}:{safe.get('source_id',safe.get('title'))}".encode()).hexdigest();available=now
  if _quiet(d,now) and not(severity=="CRITICAL" and d["critical_bypass"]):available=now.replace(hour=d["quiet_end_hour"],minute=0,second=0,microsecond=0)+(timedelta(days=1) if d["quiet_start_hour"]>=d["quiet_end_hour"] and now.hour>=d["quiet_start_hour"] else timedelta())
  delivery_id="dlv_"+uuid.uuid4().hex
  try:c.execute("INSERT INTO notification_deliveries(delivery_id,destination_id,dedupe_key,created_at,available_at,status,attempts,severity,subject,payload_json,delivered_at,last_error) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(delivery_id,destination_id,dedupe,now.isoformat(),available.isoformat(),"QUEUED",0,severity,subject,json.dumps({"channel":d["channel"],"subject":subject,"body":body,"event":safe},separators=(",",":"),sort_keys=True),None,None))
  except sqlite3.IntegrityError:return {"status":"DEDUPLICATED","dedupe_key":dedupe}
 record_evidence("NOTIFICATION_DELIVERY",delivery_id,"ENQUEUED",detail={"destination_id":destination_id,"severity":severity})
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;return dict(c.execute("SELECT * FROM notification_deliveries WHERE delivery_id=?",(delivery_id,)).fetchone())
def real_sender(endpoint_reference,payload,*,idempotency_key=None):
 """The production transport: POST the templated payload to a webhook URL."""
 if payload.get("channel")=="EMAIL":
  # EMAIL needs an SMTP transport, not an HTTPS POST. Not built in this milestone; fail loud and
  # dead-letter rather than silently drop or mis-send the notification.
  raise PermanentDeliveryError("EMAIL delivery is not yet implemented; this notification cannot be sent.")
 body=json.dumps(payload,separators=(",",":"),sort_keys=True).encode()
 send_json(endpoint_reference,body,idempotency_key=idempotency_key)
def process_deliveries(sender,limit=100,worker_id=None):
 initialize_notification_delivery();processed=0;now=utc_now()
 claim_token=new_claim_token()
 with sqlite3.connect(database_path) as c:
  c.execute("""UPDATE notification_deliveries SET claim_token=?,claimed_at=? WHERE delivery_id IN (
   SELECT q.delivery_id FROM notification_deliveries q JOIN notification_destinations d USING(destination_id)
   WHERE (q.status='QUEUED' OR (q.status='SENDING' AND q.claimed_at<=?)) AND q.available_at<=? AND d.enabled=1
   ORDER BY q.created_at LIMIT ?)""",(claim_token,now,(datetime.now(timezone.utc)-timedelta(seconds=LEASE_SECONDS)).isoformat(),now,limit))
  c.execute("UPDATE notification_deliveries SET status='SENDING' WHERE claim_token=?",(claim_token,))
  c.row_factory=sqlite3.Row
  rows=c.execute("""SELECT q.*,d.endpoint_reference,d.max_attempts FROM notification_deliveries q
   JOIN notification_destinations d USING(destination_id) WHERE q.claim_token=?""",(claim_token,)).fetchall()
 for row in rows:
  attempts=row["attempts"]+1
  record_evidence("NOTIFICATION_DELIVERY",row["delivery_id"],"ATTEMPT",attempt=attempts,worker_id=worker_id)
  try:
   sender(row["endpoint_reference"],json.loads(row["payload_json"]),idempotency_key=row["dedupe_key"])
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE notification_deliveries SET status='DELIVERED',attempts=?,delivered_at=?,last_error=NULL,claim_token=NULL,claimed_at=NULL WHERE delivery_id=?",(attempts,utc_now(),row["delivery_id"]))
   record_evidence("NOTIFICATION_DELIVERY",row["delivery_id"],"SUCCESS",attempt=attempts,worker_id=worker_id)
  except SSRFBlocked as error:
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE notification_deliveries SET status='BLOCKED',attempts=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE delivery_id=?",(attempts,safe_error(error),row["delivery_id"]))
   record_evidence("NOTIFICATION_DELIVERY",row["delivery_id"],"BLOCKED",attempt=attempts,detail={"error":str(error)},worker_id=worker_id)
  except PermanentDeliveryError as error:
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE notification_deliveries SET status='DEAD_LETTER',attempts=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE delivery_id=?",(attempts,safe_error(error),row["delivery_id"]))
   record_evidence("NOTIFICATION_DELIVERY",row["delivery_id"],"DEAD_LETTER",attempt=attempts,detail={"error":str(error)},worker_id=worker_id)
  except Exception as error:
   terminal=attempts>=row["max_attempts"]
   available=(datetime.now(timezone.utc)+timedelta(seconds=backoff_seconds(attempts))).isoformat()
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE notification_deliveries SET status=?,attempts=?,available_at=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE delivery_id=?",("DEAD_LETTER" if terminal else "QUEUED",attempts,available,safe_error(error),row["delivery_id"]))
   record_evidence("NOTIFICATION_DELIVERY",row["delivery_id"],"DEAD_LETTER" if terminal else "RETRY",attempt=attempts,detail={"error":safe_error(error)},worker_id=worker_id)
  processed+=1
 return {"processed":processed}
