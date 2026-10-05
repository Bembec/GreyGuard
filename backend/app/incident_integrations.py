"""Governed incident-system adapters, approval links, and signed callbacks."""
import hashlib,hmac,json,os,secrets,sqlite3,uuid
from datetime import datetime,timedelta,timezone
from .database import database_path
from .observability import redact

SYSTEMS={"JIRA","SERVICENOW"}
def utc_now():return datetime.now(timezone.utc).isoformat()
def initialize_incident_integrations():
 with sqlite3.connect(database_path) as c:
  c.execute("""CREATE TABLE IF NOT EXISTS incident_destinations(destination_id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE COLLATE NOCASE,system_type TEXT NOT NULL,endpoint TEXT NOT NULL,credential_reference TEXT NOT NULL,project_or_table TEXT NOT NULL,enabled INTEGER NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,last_success_at TEXT,last_failure_at TEXT,last_error TEXT)""")
  c.execute("""CREATE TABLE IF NOT EXISTS external_incident_records(record_id TEXT PRIMARY KEY,destination_id TEXT NOT NULL,source_alert_id TEXT NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL,payload_json TEXT NOT NULL,external_id TEXT,delivered_at TEXT,last_error TEXT,UNIQUE(destination_id,source_alert_id))""")
  c.execute("""CREATE TABLE IF NOT EXISTS expiring_approval_links(link_id TEXT PRIMARY KEY,request_id TEXT NOT NULL,token_hash TEXT NOT NULL UNIQUE,decision TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT NOT NULL,created_by TEXT NOT NULL,used_at TEXT,used_by TEXT,revoked_at TEXT)""")
  c.execute("""CREATE TABLE IF NOT EXISTS callback_evidence(callback_id TEXT PRIMARY KEY,record_id TEXT NOT NULL,received_at TEXT NOT NULL,signature_valid INTEGER NOT NULL,payload_hash TEXT NOT NULL,outcome TEXT NOT NULL)""")
def list_controls():
 initialize_incident_integrations()
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;dest=[dict(r) for r in c.execute("SELECT * FROM incident_destinations ORDER BY name")];records=[dict(r) for r in c.execute("SELECT record_id,destination_id,source_alert_id,created_at,status,external_id,delivered_at,last_error FROM external_incident_records ORDER BY created_at DESC LIMIT 100")];links=[dict(r) for r in c.execute("SELECT link_id,request_id,decision,expires_at,created_at,created_by,used_at,used_by,revoked_at FROM expiring_approval_links ORDER BY created_at DESC LIMIT 100")]
 for d in dest:d["enabled"]=bool(d["enabled"]);d["credentials_stored"]=False
 return {"destinations":dest,"records":records,"approval_links":links,"systems":sorted(SYSTEMS)}
def save_destination(name,system_type,endpoint,credential_reference,project_or_table,enabled,actor):
 system_type=system_type.upper()
 if system_type not in SYSTEMS:raise ValueError("Unsupported incident system.")
 if not endpoint.startswith("https://"):raise ValueError("Incident-system endpoints must use HTTPS.")
 did="idst_"+uuid.uuid4().hex
 with sqlite3.connect(database_path) as c:
  old=c.execute("SELECT destination_id FROM incident_destinations WHERE name=?",(name.strip(),)).fetchone()
  if old:did=old[0];c.execute("UPDATE incident_destinations SET system_type=?,endpoint=?,credential_reference=?,project_or_table=?,enabled=? WHERE destination_id=?",(system_type,endpoint,credential_reference,project_or_table,int(enabled),did))
  else:c.execute("INSERT INTO incident_destinations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(did,name.strip(),system_type,endpoint,credential_reference,project_or_table,int(enabled),utc_now(),actor,None,None,None))
 return next(d for d in list_controls()["destinations"] if d["destination_id"]==did)
def queue_incident(destination_id,alert):
 initialize_incident_integrations();safe=redact(alert)
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;d=c.execute("SELECT * FROM incident_destinations WHERE destination_id=?",(destination_id,)).fetchone()
  if not d:raise KeyError("Incident destination not found.")
  if not d["enabled"]:raise PermissionError("Incident destination is disabled.")
  source=str(safe.get("alert_id") or safe.get("source_alert_id") or "")
  if not source:raise ValueError("A source alert identifier is required.")
  payload={"system":d["system_type"],"target":d["project_or_table"],"summary":safe.get("title","GreyGuard incident"),"description":safe.get("summary",safe.get("message","")),"severity":safe.get("severity","MEDIUM"),"source_alert_id":source}
  rid="incx_"+uuid.uuid4().hex
  try:c.execute("INSERT INTO external_incident_records VALUES(?,?,?,?,?,?,?,?,?)",(rid,destination_id,source,utc_now(),"QUEUED",json.dumps(payload,separators=(",",":"),sort_keys=True),None,None,None))
  except sqlite3.IntegrityError:return {"status":"DEDUPLICATED","source_alert_id":source}
  c.row_factory=sqlite3.Row;return dict(c.execute("SELECT * FROM external_incident_records WHERE record_id=?",(rid,)).fetchone())
def process_incidents(sender,limit=100):
 initialize_incident_integrations();processed=0
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;rows=c.execute("SELECT r.*,d.endpoint,d.credential_reference,d.system_type FROM external_incident_records r JOIN incident_destinations d USING(destination_id) WHERE r.status='QUEUED' AND d.enabled=1 ORDER BY r.created_at LIMIT ?",(limit,)).fetchall()
  for row in rows:
   try:
    external_id=sender(row["system_type"],row["endpoint"],row["credential_reference"],json.loads(row["payload_json"]));c.execute("UPDATE external_incident_records SET status='CREATED',external_id=?,delivered_at=?,last_error=NULL WHERE record_id=?",(str(external_id),utc_now(),row["record_id"]));c.execute("UPDATE incident_destinations SET last_success_at=?,last_error=NULL WHERE destination_id=?",(utc_now(),row["destination_id"]))
   except Exception as e:c.execute("UPDATE external_incident_records SET status='FAILED',last_error=? WHERE record_id=?",(str(e)[:500],row["record_id"]));c.execute("UPDATE incident_destinations SET last_failure_at=?,last_error=? WHERE destination_id=?",(utc_now(),str(e)[:500],row["destination_id"]))
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
