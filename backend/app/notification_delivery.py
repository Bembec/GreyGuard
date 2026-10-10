"""Governed external notification delivery with quiet hours and evidence."""
import hashlib,json,uuid
from . import db_compat as sqlite3
from datetime import datetime,timedelta,timezone
from . import organizations
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
_DESTINATIONS_SCHEMA=f"""(destination_id TEXT PRIMARY KEY,name TEXT NOT NULL COLLATE NOCASE,channel TEXT NOT NULL,endpoint_reference TEXT NOT NULL,enabled INTEGER NOT NULL,minimum_severity TEXT NOT NULL,quiet_start_hour INTEGER,quiet_end_hour INTEGER,critical_bypass INTEGER NOT NULL,escalation_minutes INTEGER NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,max_attempts INTEGER NOT NULL DEFAULT {DEFAULT_MAX_ATTEMPTS},org_id TEXT NOT NULL DEFAULT 'org_default',UNIQUE(name,org_id))"""
_TEMPLATES_SCHEMA="""(template_id TEXT PRIMARY KEY,name TEXT NOT NULL,event_type TEXT NOT NULL,subject_template TEXT NOT NULL,body_template TEXT NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,org_id TEXT NOT NULL DEFAULT 'org_default',UNIQUE(name,org_id))"""
_DESTINATION_COLUMNS="destination_id,name,channel,endpoint_reference,enabled,minimum_severity,quiet_start_hour,quiet_end_hour,critical_bypass,escalation_minutes,created_at,created_by"
_TEMPLATE_COLUMNS="template_id,name,event_type,subject_template,body_template,created_at,created_by"
def _rebuild_with_org(c,table,schema,columns,extra_columns=()):
 # `name` was globally UNIQUE on both config tables - two orgs would collide on the same
 # human-chosen name - so rebuild with UNIQUE(name,org_id), as security_exports (batch 15) did:
 # build under a temporary name, copy, drop the original and rename the new table into place,
 # since SQLite's RENAME rewrites inbound foreign keys to follow a table renamed aside.
 # extra_columns are (name,fallback) pairs for later-added columns a legacy table may lack.
 existing={row[1] for row in c.execute(f"PRAGMA table_info({table})")}
 if not existing or "org_id" in existing:return
 copied=",".join(name for name,_ in extra_columns);source=",".join(name if name in existing else fallback for name,fallback in extra_columns)
 c.execute(f"CREATE TABLE {table}_org {schema}")
 c.execute(f"INSERT INTO {table}_org({columns}{','+copied if copied else ''},org_id) SELECT {columns}{','+source if source else ''},'org_default' FROM {table}")
 c.execute(f"DROP TABLE {table}")
 c.execute(f"ALTER TABLE {table}_org RENAME TO {table}")
def initialize_notification_delivery():
 with sqlite3.connect(database_path) as c:
  _rebuild_with_org(c,"notification_destinations",_DESTINATIONS_SCHEMA,_DESTINATION_COLUMNS,(("max_attempts",str(DEFAULT_MAX_ATTEMPTS)),))
  _rebuild_with_org(c,"notification_templates",_TEMPLATES_SCHEMA,_TEMPLATE_COLUMNS)
  c.execute("CREATE TABLE IF NOT EXISTS notification_destinations"+_DESTINATIONS_SCHEMA)
  c.execute("CREATE TABLE IF NOT EXISTS notification_templates"+_TEMPLATES_SCHEMA)
  c.execute("""CREATE TABLE IF NOT EXISTS notification_deliveries(delivery_id TEXT PRIMARY KEY,destination_id TEXT NOT NULL,dedupe_key TEXT NOT NULL,created_at TEXT NOT NULL,available_at TEXT NOT NULL,status TEXT NOT NULL,attempts INTEGER NOT NULL,severity TEXT NOT NULL,subject TEXT NOT NULL,payload_json TEXT NOT NULL,delivered_at TEXT,last_error TEXT,claim_token TEXT,claimed_at TEXT,org_id TEXT NOT NULL DEFAULT 'org_default',UNIQUE(destination_id,dedupe_key))""")
  # The CREATE TABLE above already defines every column, so these ALTERs only fire against a
  # pre-existing database. As with report_schedules (batch 12), tenant_guard checks each one and
  # only the org_id ALTER can carry the literal it requires, so a database old enough to predate
  # the claim columns (added before the PostgreSQL baseline) needs them caught up first.
  delivery_columns={row[1] for row in c.execute("PRAGMA table_info(notification_deliveries)")}
  if "claim_token" not in delivery_columns:c.execute("ALTER TABLE notification_deliveries ADD COLUMN claim_token TEXT")
  if "claimed_at" not in delivery_columns:c.execute("ALTER TABLE notification_deliveries ADD COLUMN claimed_at TEXT")
  if "org_id" not in delivery_columns:c.execute("ALTER TABLE notification_deliveries ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
def list_configuration(org_id=organizations.DEFAULT_ORG_ID):
 initialize_notification_delivery()
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;dest=[dict(r) for r in c.execute("SELECT * FROM notification_destinations WHERE org_id=? ORDER BY name",(org_id,))];templates=[dict(r) for r in c.execute("SELECT * FROM notification_templates WHERE org_id=? ORDER BY name",(org_id,))];recent=[dict(r) for r in c.execute("SELECT delivery_id,destination_id,created_at,status,attempts,severity,subject,delivered_at,last_error FROM notification_deliveries WHERE org_id=? ORDER BY created_at DESC LIMIT 100",(org_id,))]
 for d in dest:d["enabled"]=bool(d["enabled"]);d["critical_bypass"]=bool(d["critical_bypass"]);d["credentials_stored"]=False
 return {"destinations":dest,"templates":templates,"recent_deliveries":recent,"channels":sorted(CHANNELS)}
def save_destination(name,channel,endpoint_reference,enabled,minimum_severity,quiet_start_hour,quiet_end_hour,critical_bypass,escalation_minutes,actor,org_id=organizations.DEFAULT_ORG_ID):
 channel=channel.upper();minimum_severity=minimum_severity.upper()
 if channel not in CHANNELS:raise ValueError("Unsupported notification channel.")
 if channel in WEBHOOK_CHANNELS and not endpoint_reference.startswith("https://"):raise ValueError("Webhook notification destinations must use HTTPS.")
 if minimum_severity not in SEVERITY_ORDER:raise ValueError("Unsupported minimum severity.")
 for hour in (quiet_start_hour,quiet_end_hour):
  if hour is not None and not 0<=hour<=23:raise ValueError("Quiet-hour values must be from 0 to 23.")
 if not 0<=escalation_minutes<=1440:raise ValueError("Escalation delay is outside the supported range.")
 did="ndst_"+uuid.uuid4().hex
 with sqlite3.connect(database_path) as c:
  old=c.execute("SELECT destination_id FROM notification_destinations WHERE name=? AND org_id=?",(name.strip(),org_id)).fetchone()
  if old:
   did=old[0];c.execute("UPDATE notification_destinations SET channel=?,endpoint_reference=?,enabled=?,minimum_severity=?,quiet_start_hour=?,quiet_end_hour=?,critical_bypass=?,escalation_minutes=? WHERE destination_id=? AND org_id=?",(channel,endpoint_reference,int(enabled),minimum_severity,quiet_start_hour,quiet_end_hour,int(critical_bypass),escalation_minutes,did,org_id))
  else:c.execute("INSERT INTO notification_destinations(destination_id,name,channel,endpoint_reference,enabled,minimum_severity,quiet_start_hour,quiet_end_hour,critical_bypass,escalation_minutes,created_at,created_by,org_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(did,name.strip(),channel,endpoint_reference,int(enabled),minimum_severity,quiet_start_hour,quiet_end_hour,int(critical_bypass),escalation_minutes,utc_now(),actor,org_id))
 return next(d for d in list_configuration(org_id)["destinations"] if d["destination_id"]==did)
def save_template(name,event_type,subject_template,body_template,actor,org_id=organizations.DEFAULT_ORG_ID):
 if any(x not in {"title","severity","summary","event_type","resource_path"} for x in _fields(subject_template+body_template)):raise ValueError("Template contains an unsupported field.")
 tid="tpl_"+uuid.uuid4().hex
 with sqlite3.connect(database_path) as c:
  old=c.execute("SELECT template_id FROM notification_templates WHERE name=? AND org_id=?",(name.strip(),org_id)).fetchone()
  if old:tid=old[0];c.execute("UPDATE notification_templates SET event_type=?,subject_template=?,body_template=? WHERE template_id=? AND org_id=?",(event_type,subject_template,body_template,tid,org_id))
  else:c.execute(f"INSERT INTO notification_templates({_TEMPLATE_COLUMNS},org_id) VALUES(?,?,?,?,?,?,?,?)",(tid,name.strip(),event_type,subject_template,body_template,utc_now(),actor,org_id))
 return next(t for t in list_configuration(org_id)["templates"] if t["template_id"]==tid)
def _fields(text):
 import string
 return [name for _,name,_,_ in string.Formatter().parse(text) if name]
def _quiet(destination,now):
 start,end=destination["quiet_start_hour"],destination["quiet_end_hour"]
 if start is None or end is None:return False
 hour=now.hour
 return start<=hour<end if start<end else hour>=start or hour<end
def queue_notification(destination_id,event,template_id=None,now=None,org_id=organizations.DEFAULT_ORG_ID):
 initialize_notification_delivery();now=now or datetime.now(timezone.utc);safe=redact(event);severity=str(safe.get("severity","INFO")).upper()
 with sqlite3.connect(database_path) as c:
  # Destination and template are both resolved within the caller's org: otherwise one org could
  # route its notifications to another org's channel, or render another org's template.
  c.row_factory=sqlite3.Row;d=c.execute("SELECT * FROM notification_destinations WHERE destination_id=? AND org_id=?",(destination_id,org_id)).fetchone()
  if not d:raise KeyError("Notification destination not found.")
  if not d["enabled"]:raise PermissionError("Notification destination is disabled.")
  if SEVERITY_ORDER.get(severity,-1)<SEVERITY_ORDER[d["minimum_severity"]]:return {"status":"FILTERED","reason":"Below minimum severity."}
  template=c.execute("SELECT * FROM notification_templates WHERE template_id=? AND org_id=?",(template_id,org_id)).fetchone() if template_id else None
  values={k:str(safe.get(k,"")) for k in ("title","severity","summary","event_type","resource_path")};subject=(template["subject_template"].format(**values) if template else values["title"]);body=(template["body_template"].format(**values) if template else values["summary"])
  dedupe=hashlib.sha256(f"{d['destination_id']}:{safe.get('event_type')}:{safe.get('source_id',safe.get('title'))}".encode()).hexdigest();available=now
  if _quiet(d,now) and not(severity=="CRITICAL" and d["critical_bypass"]):available=now.replace(hour=d["quiet_end_hour"],minute=0,second=0,microsecond=0)+(timedelta(days=1) if d["quiet_start_hour"]>=d["quiet_end_hour"] and now.hour>=d["quiet_start_hour"] else timedelta())
  delivery_id="dlv_"+uuid.uuid4().hex
  try:c.execute("INSERT INTO notification_deliveries(delivery_id,destination_id,dedupe_key,created_at,available_at,status,attempts,severity,subject,payload_json,delivered_at,last_error,org_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(delivery_id,destination_id,dedupe,now.isoformat(),available.isoformat(),"QUEUED",0,severity,subject,json.dumps({"channel":d["channel"],"subject":subject,"body":body,"event":safe},separators=(",",":"),sort_keys=True),None,None,org_id))
  except sqlite3.IntegrityError:return {"status":"DEDUPLICATED","dedupe_key":dedupe}
 record_evidence("NOTIFICATION_DELIVERY",delivery_id,"ENQUEUED",org_id=org_id,detail={"destination_id":destination_id,"severity":severity})
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;return dict(c.execute("SELECT * FROM notification_deliveries WHERE delivery_id=? AND org_id=?",(delivery_id,org_id)).fetchone())
def real_sender(endpoint_reference,payload,*,idempotency_key=None):
 """The production transport: POST the templated payload to a webhook URL."""
 if payload.get("channel")=="EMAIL":
  # EMAIL needs an SMTP transport, not an HTTPS POST. Not built in this milestone; fail loud and
  # dead-letter rather than silently drop or mis-send the notification.
  raise PermanentDeliveryError("EMAIL delivery is not yet implemented; this notification cannot be sent.")
 body=json.dumps(payload,separators=(",",":"),sort_keys=True).encode()
 send_json(endpoint_reference,body,idempotency_key=idempotency_key)
def process_deliveries(sender,limit=100,worker_id=None):
 """Deliver due notifications through an injected transport.

 Services every org's queue in one pass, so the claim is intentionally cross-org (the same design
 as security_exports.process_queue()): it carries no org_id filter, but it only ever joins a
 delivery to a destination of the *same* org, and every later write is scoped by the claimed
 row's own org_id."""
 initialize_notification_delivery();processed=0;now=utc_now()
 claim_token=new_claim_token()
 with sqlite3.connect(database_path) as c:
  c.execute("""-- intentional cross-org claim, no org_id filter: see process_deliveries() docstring
   UPDATE notification_deliveries SET claim_token=?,claimed_at=?,status='SENDING' WHERE delivery_id IN (
   SELECT q.delivery_id FROM notification_deliveries q JOIN notification_destinations d
    ON d.destination_id=q.destination_id AND d.org_id=q.org_id
   WHERE (q.status='QUEUED' OR (q.status='SENDING' AND q.claimed_at<=?)) AND q.available_at<=? AND d.enabled=1
   ORDER BY q.created_at LIMIT ?)""",(claim_token,now,(datetime.now(timezone.utc)-timedelta(seconds=LEASE_SECONDS)).isoformat(),now,limit))
  c.row_factory=sqlite3.Row
  rows=c.execute("""SELECT q.*,d.endpoint_reference,d.max_attempts FROM notification_deliveries q
   JOIN notification_destinations d ON d.destination_id=q.destination_id AND d.org_id=q.org_id WHERE q.claim_token=?""",(claim_token,)).fetchall()
 for row in rows:
  attempts=row["attempts"]+1
  record_evidence("NOTIFICATION_DELIVERY",row["delivery_id"],"ATTEMPT",org_id=row["org_id"],attempt=attempts,worker_id=worker_id)
  try:
   sender(row["endpoint_reference"],json.loads(row["payload_json"]),idempotency_key=row["dedupe_key"])
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE notification_deliveries SET status='DELIVERED',attempts=?,delivered_at=?,last_error=NULL,claim_token=NULL,claimed_at=NULL WHERE delivery_id=? AND org_id=?",(attempts,utc_now(),row["delivery_id"],row["org_id"]))
   record_evidence("NOTIFICATION_DELIVERY",row["delivery_id"],"SUCCESS",org_id=row["org_id"],attempt=attempts,worker_id=worker_id)
  except SSRFBlocked as error:
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE notification_deliveries SET status='BLOCKED',attempts=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE delivery_id=? AND org_id=?",(attempts,safe_error(error),row["delivery_id"],row["org_id"]))
   record_evidence("NOTIFICATION_DELIVERY",row["delivery_id"],"BLOCKED",org_id=row["org_id"],attempt=attempts,detail={"error":str(error)},worker_id=worker_id)
  except PermanentDeliveryError as error:
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE notification_deliveries SET status='DEAD_LETTER',attempts=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE delivery_id=? AND org_id=?",(attempts,safe_error(error),row["delivery_id"],row["org_id"]))
   record_evidence("NOTIFICATION_DELIVERY",row["delivery_id"],"DEAD_LETTER",org_id=row["org_id"],attempt=attempts,detail={"error":str(error)},worker_id=worker_id)
  except Exception as error:
   terminal=attempts>=row["max_attempts"]
   available=(datetime.now(timezone.utc)+timedelta(seconds=backoff_seconds(attempts))).isoformat()
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE notification_deliveries SET status=?,attempts=?,available_at=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE delivery_id=? AND org_id=?",("DEAD_LETTER" if terminal else "QUEUED",attempts,available,safe_error(error),row["delivery_id"],row["org_id"]))
   record_evidence("NOTIFICATION_DELIVERY",row["delivery_id"],"DEAD_LETTER" if terminal else "RETRY",org_id=row["org_id"],attempt=attempts,detail={"error":safe_error(error)},worker_id=worker_id)
  processed+=1
 return {"processed":processed}
