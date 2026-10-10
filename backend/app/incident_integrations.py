"""Governed incident-system adapters, approval links, and signed callbacks."""
import hashlib,hmac,json,os,secrets,uuid
from . import db_compat as sqlite3
from datetime import datetime,timedelta,timezone
from . import organizations
from .database import database_path
from .observability import redact
from .outbound_delivery import (
 PermanentDeliveryError,SSRFBlocked,backoff_seconds,
 new_claim_token,record_evidence,safe_error,send_json,
)

SYSTEMS={"JIRA","SERVICENOW"}
DEFAULT_MAX_ATTEMPTS=8
LEASE_SECONDS=120
def utc_now():return datetime.now(timezone.utc).isoformat()
_DESTINATIONS_SCHEMA=f"(destination_id TEXT PRIMARY KEY,name TEXT NOT NULL COLLATE NOCASE,system_type TEXT NOT NULL,endpoint TEXT NOT NULL,credential_reference TEXT NOT NULL,project_or_table TEXT NOT NULL,enabled INTEGER NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,last_success_at TEXT,last_failure_at TEXT,last_error TEXT,max_attempts INTEGER NOT NULL DEFAULT {DEFAULT_MAX_ATTEMPTS},org_id TEXT NOT NULL DEFAULT 'org_default',UNIQUE(name,org_id))"
_DESTINATION_COLUMNS="destination_id,name,system_type,endpoint,credential_reference,project_or_table,enabled,created_at,created_by,last_success_at,last_failure_at,last_error"
def initialize_incident_integrations():
 with sqlite3.connect(database_path) as c:
  existing=[row[1] for row in c.execute("PRAGMA table_info(incident_destinations)")]
  if existing and "org_id" not in existing:
   # incident_destinations.name was globally UNIQUE (case-insensitive) - two orgs would collide on
   # the same human-chosen destination name - so rebuild with UNIQUE(name,org_id), using batch 15's
   # build-new/drop/rename-into-place order (safe against SQLite rewriting inbound foreign keys on
   # RENAME, even though nothing references this table today). A legacy table may predate
   # max_attempts, so that column is only copied when present.
   columns=_DESTINATION_COLUMNS+(",max_attempts" if "max_attempts" in existing else "")
   c.execute("CREATE TABLE incident_destinations_org "+_DESTINATIONS_SCHEMA)
   c.execute(f"INSERT INTO incident_destinations_org({columns},org_id) SELECT {columns},'org_default' FROM incident_destinations")
   c.execute("DROP TABLE incident_destinations")
   c.execute("ALTER TABLE incident_destinations_org RENAME TO incident_destinations")
  c.execute("CREATE TABLE IF NOT EXISTS incident_destinations "+_DESTINATIONS_SCHEMA)
  c.execute("""CREATE TABLE IF NOT EXISTS external_incident_records(record_id TEXT PRIMARY KEY,destination_id TEXT NOT NULL,source_alert_id TEXT NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL,payload_json TEXT NOT NULL,external_id TEXT,delivered_at TEXT,last_error TEXT,attempts INTEGER NOT NULL DEFAULT 0,available_at TEXT,claim_token TEXT,claimed_at TEXT,org_id TEXT NOT NULL DEFAULT 'org_default',UNIQUE(destination_id,source_alert_id))""")
  c.execute("""CREATE TABLE IF NOT EXISTS expiring_approval_links(link_id TEXT PRIMARY KEY,request_id TEXT NOT NULL,token_hash TEXT NOT NULL UNIQUE,decision TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,used_at TEXT,used_by TEXT,revoked_at TEXT)""")
  c.execute("""CREATE TABLE IF NOT EXISTS callback_evidence(callback_id TEXT PRIMARY KEY,record_id TEXT NOT NULL,received_at TEXT NOT NULL,signature_valid INTEGER NOT NULL,payload_hash TEXT NOT NULL,outcome TEXT NOT NULL)""")
  # The CREATE TABLEs above already define every column, so these ALTERs only upgrade a pre-existing
  # database. As with export_queue (batch 15), tenant_guard checks each one and only the org_id ALTER
  # mentions the literal it requires, so a database old enough to predate the delivery columns must
  # have its schema caught up before upgrading straight to org-scoped code.
  record_columns={row[1] for row in c.execute("PRAGMA table_info(external_incident_records)")}
  if "attempts" not in record_columns:c.execute("ALTER TABLE external_incident_records ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
  if "available_at" not in record_columns:c.execute("ALTER TABLE external_incident_records ADD COLUMN available_at TEXT")
  if "claim_token" not in record_columns:c.execute("ALTER TABLE external_incident_records ADD COLUMN claim_token TEXT")
  if "claimed_at" not in record_columns:c.execute("ALTER TABLE external_incident_records ADD COLUMN claimed_at TEXT")
  if "org_id" not in record_columns:c.execute("ALTER TABLE external_incident_records ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
  c.execute("-- legacy backfill, deliberately across every org_id\n UPDATE external_incident_records SET available_at=created_at WHERE available_at IS NULL")
def list_controls(org_id=organizations.DEFAULT_ORG_ID):
 initialize_incident_integrations()
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;dest=[dict(r) for r in c.execute("SELECT * FROM incident_destinations WHERE org_id=? ORDER BY name",(org_id,))];records=[dict(r) for r in c.execute("SELECT record_id,destination_id,source_alert_id,created_at,status,external_id,delivered_at,last_error FROM external_incident_records WHERE org_id=? ORDER BY created_at DESC LIMIT 100",(org_id,))];links=[dict(r) for r in c.execute("SELECT link_id,request_id,decision,expires_at,created_at,created_by,used_at,used_by,revoked_at FROM expiring_approval_links ORDER BY created_at DESC LIMIT 100")]
 for d in dest:d["enabled"]=bool(d["enabled"]);d["credentials_stored"]=False
 return {"destinations":dest,"records":records,"approval_links":links,"systems":sorted(SYSTEMS)}
def save_destination(name,system_type,endpoint,credential_reference,project_or_table,enabled,actor,org_id=organizations.DEFAULT_ORG_ID):
 system_type=system_type.upper()
 if system_type not in SYSTEMS:raise ValueError("Unsupported incident system.")
 if not endpoint.startswith("https://"):raise ValueError("Incident-system endpoints must use HTTPS.")
 did="idst_"+uuid.uuid4().hex
 with sqlite3.connect(database_path) as c:
  old=c.execute("SELECT destination_id FROM incident_destinations WHERE name=? AND org_id=?",(name.strip(),org_id)).fetchone()
  if old:did=old[0];c.execute("UPDATE incident_destinations SET system_type=?,endpoint=?,credential_reference=?,project_or_table=?,enabled=? WHERE destination_id=? AND org_id=?",(system_type,endpoint,credential_reference,project_or_table,int(enabled),did,org_id))
  else:c.execute(f"INSERT INTO incident_destinations({_DESTINATION_COLUMNS},org_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(did,name.strip(),system_type,endpoint,credential_reference,project_or_table,int(enabled),utc_now(),actor,None,None,None,org_id))
 return next(d for d in list_controls(org_id)["destinations"] if d["destination_id"]==did)
def queue_incident(destination_id,alert,org_id=organizations.DEFAULT_ORG_ID):
 initialize_incident_integrations();safe=redact(alert)
 with sqlite3.connect(database_path) as c:
  # Scoped by the caller's org, not just the id: otherwise one org could open tickets in another
  # org's Jira/ServiceNow project, with that org's credential, by destination_id.
  c.row_factory=sqlite3.Row;d=c.execute("SELECT * FROM incident_destinations WHERE destination_id=? AND org_id=?",(destination_id,org_id)).fetchone()
  if not d:raise KeyError("Incident destination not found.")
  if not d["enabled"]:raise PermissionError("Incident destination is disabled.")
  source=str(safe.get("alert_id") or safe.get("source_alert_id") or "")
  if not source:raise ValueError("A source alert identifier is required.")
  payload={"system":d["system_type"],"target":d["project_or_table"],"summary":safe.get("title","GreyGuard incident"),"description":safe.get("summary",safe.get("message","")),"severity":safe.get("severity","MEDIUM"),"source_alert_id":source}
  rid="incx_"+uuid.uuid4().hex
  try:c.execute("INSERT INTO external_incident_records(record_id,destination_id,source_alert_id,created_at,status,payload_json,external_id,delivered_at,last_error,attempts,available_at,org_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(rid,destination_id,source,utc_now(),"QUEUED",json.dumps(payload,separators=(",",":"),sort_keys=True),None,None,None,0,utc_now(),org_id))
  except sqlite3.IntegrityError:return {"status":"DEDUPLICATED","source_alert_id":source}
 record_evidence("INCIDENT_INTEGRATION",rid,"ENQUEUED",detail={"destination_id":destination_id,"source_alert_id":source})
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;return dict(c.execute("SELECT * FROM external_incident_records WHERE record_id=? AND org_id=?",(rid,org_id)).fetchone())
def _external_id_from_response(body,fallback):
 """The POST already succeeded once send_json returns without raising; an unparsable or
 unexpected response body is not a delivery failure, just a missing external ticket id."""
 try:parsed=json.loads(body or b"{}")
 except ValueError:return fallback
 if not isinstance(parsed,dict):return fallback
 result=parsed.get("result")
 return parsed.get("id") or (result.get("sys_id") if isinstance(result,dict) else None) or fallback
def real_sender(system_type,endpoint,credential_reference,payload,*,idempotency_key=None):
 """The production transport: POST to the Jira/ServiceNow REST API with a bearer credential."""
 token=os.getenv(credential_reference)
 if not token:raise PermanentDeliveryError("Incident-system credential environment reference is unavailable.")
 body=json.dumps(payload,separators=(",",":"),sort_keys=True).encode()
 response=send_json(endpoint,body,headers={"Authorization":f"Bearer {token}"},idempotency_key=idempotency_key)
 return _external_id_from_response(response["body"],idempotency_key)
def process_incidents(sender,limit=100,worker_id=None):
 """Deliver due incidents through an injected transport.

 This worker services every org's records in one pass, so the claim is intentionally cross-org (the
 same design as security_exports.process_queue()): it carries no org_id filter, but it only ever
 joins a record to a destination of the *same* org, and every later write is scoped by the claimed
 row's own org_id."""
 initialize_incident_integrations();processed=0;now=utc_now()
 claim_token=new_claim_token()
 with sqlite3.connect(database_path) as c:
  c.execute("""-- intentional cross-org claim, no org_id filter: see process_incidents() docstring
   UPDATE external_incident_records SET claim_token=?,claimed_at=?,status='SENDING' WHERE record_id IN (
   SELECT r.record_id FROM external_incident_records r JOIN incident_destinations d
    ON d.destination_id=r.destination_id AND d.org_id=r.org_id
   WHERE (r.status='QUEUED' OR (r.status='SENDING' AND r.claimed_at<=?)) AND r.available_at<=? AND d.enabled=1
   ORDER BY r.created_at LIMIT ?)""",(claim_token,now,(datetime.now(timezone.utc)-timedelta(seconds=LEASE_SECONDS)).isoformat(),now,limit))
  c.row_factory=sqlite3.Row
  rows=c.execute("""SELECT r.*,d.endpoint,d.credential_reference,d.system_type,d.max_attempts FROM external_incident_records r
   JOIN incident_destinations d ON d.destination_id=r.destination_id AND d.org_id=r.org_id WHERE r.claim_token=?""",(claim_token,)).fetchall()
 for row in rows:
  attempts=row["attempts"]+1
  record_evidence("INCIDENT_INTEGRATION",row["record_id"],"ATTEMPT",attempt=attempts,worker_id=worker_id)
  try:
   external_id=sender(row["system_type"],row["endpoint"],row["credential_reference"],json.loads(row["payload_json"]),idempotency_key=row["record_id"])
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE external_incident_records SET status='CREATED',attempts=?,external_id=?,delivered_at=?,last_error=NULL,claim_token=NULL,claimed_at=NULL WHERE record_id=? AND org_id=?",(attempts,str(external_id),utc_now(),row["record_id"],row["org_id"]))
    c.execute("UPDATE incident_destinations SET last_success_at=?,last_error=NULL WHERE destination_id=? AND org_id=?",(utc_now(),row["destination_id"],row["org_id"]))
   record_evidence("INCIDENT_INTEGRATION",row["record_id"],"SUCCESS",attempt=attempts,worker_id=worker_id)
  except SSRFBlocked as error:
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE external_incident_records SET status='BLOCKED',attempts=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE record_id=? AND org_id=?",(attempts,safe_error(error),row["record_id"],row["org_id"]))
   record_evidence("INCIDENT_INTEGRATION",row["record_id"],"BLOCKED",attempt=attempts,detail={"error":str(error)},worker_id=worker_id)
  except PermanentDeliveryError as error:
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE external_incident_records SET status='DEAD_LETTER',attempts=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE record_id=? AND org_id=?",(attempts,safe_error(error),row["record_id"],row["org_id"]))
    c.execute("UPDATE incident_destinations SET last_failure_at=?,last_error=? WHERE destination_id=? AND org_id=?",(utc_now(),safe_error(error),row["destination_id"],row["org_id"]))
   record_evidence("INCIDENT_INTEGRATION",row["record_id"],"DEAD_LETTER",attempt=attempts,detail={"error":str(error)},worker_id=worker_id)
  except Exception as error:
   terminal=attempts>=row["max_attempts"]
   available=(datetime.now(timezone.utc)+timedelta(seconds=backoff_seconds(attempts))).isoformat()
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE external_incident_records SET status=?,attempts=?,available_at=?,last_error=?,claim_token=NULL,claimed_at=NULL WHERE record_id=? AND org_id=?",("DEAD_LETTER" if terminal else "QUEUED",attempts,available,safe_error(error),row["record_id"],row["org_id"]))
    c.execute("UPDATE incident_destinations SET last_failure_at=?,last_error=? WHERE destination_id=? AND org_id=?",(utc_now(),safe_error(error),row["destination_id"],row["org_id"]))
   record_evidence("INCIDENT_INTEGRATION",row["record_id"],"DEAD_LETTER" if terminal else "RETRY",attempt=attempts,detail={"error":safe_error(error)},worker_id=worker_id)
  processed+=1
 return {"processed":processed}
def create_approval_link(request_id,decision,minutes,actor):
 decision=decision.upper()
 if decision not in {"APPROVED","DENIED"}:raise ValueError("Decision must be APPROVED or DENIED.")
 if not 5<=minutes<=60:raise ValueError("Approval links must expire within 5 to 60 minutes.")
 token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest();lid="alink_"+uuid.uuid4().hex;expires=(datetime.now(timezone.utc)+timedelta(minutes=minutes)).isoformat()
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO expiring_approval_links VALUES(?,?,?,?,?,?,?,?,?,?)",(lid,request_id,digest,decision,expires,utc_now(),actor,None,None,None))
 return {"link_id":lid,"request_id":request_id,"decision":decision,"expires_at":expires,"token":token,"shown_once":True}
def consume_approval_link(token,actor):
 digest=hashlib.sha256(token.encode()).hexdigest();now=utc_now()
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;row=c.execute("SELECT * FROM expiring_approval_links WHERE token_hash=?",(digest,)).fetchone()
  if not row:raise ValueError("Approval link is invalid.")
  if row["revoked_at"] or row["used_at"]:raise ValueError("Approval link is no longer active.")
  if row["expires_at"]<=now:raise ValueError("Approval link has expired.")
  changed=c.execute("UPDATE expiring_approval_links SET used_at=?,used_by=? WHERE link_id=? AND used_at IS NULL",(now,actor,row["link_id"])).rowcount
  if not changed:raise ValueError("Approval link was already consumed.")
 return {"link_id":row["link_id"],"request_id":row["request_id"],"decision":row["decision"]}
def verify_callback(record_id,payload,signature,key_reference):
 key=os.getenv(key_reference)
 if not key:raise ValueError("Callback signing-key reference is unavailable.")
 serialized=json.dumps(redact(payload),separators=(",",":"),sort_keys=True);expected="sha256="+hmac.new(key.encode(),serialized.encode(),hashlib.sha256).hexdigest();valid=hmac.compare_digest(expected,signature or "");cid="cb_"+uuid.uuid4().hex
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO callback_evidence VALUES(?,?,?,?,?,?)",(cid,record_id,utc_now(),int(valid),hashlib.sha256(serialized.encode()).hexdigest(),"ACCEPTED" if valid else "REJECTED"))
 if not valid:raise PermissionError("Callback signature is invalid.")
 return {"callback_id":cid,"signature_valid":True,"payload":json.loads(serialized)}
