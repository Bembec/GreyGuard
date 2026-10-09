"""Consent-bound, read-only endpoint telemetry governance and evidence."""
from __future__ import annotations
import json,re,uuid
from . import db_compat as sqlite3
from datetime import datetime,timezone
from pathlib import PurePath
from .database import database_path
from . import organizations

ALLOWED_PERMISSIONS={"PROCESS_HEALTH","FILESYSTEM_EVENTS","NETWORK_METADATA","RESOURCE_USAGE"}
def utc_now():return datetime.now(timezone.utc).isoformat()
def initialize_endpoint_telemetry():
 with sqlite3.connect(database_path) as c:
  c.execute("""CREATE TABLE IF NOT EXISTS endpoint_collectors(collector_id TEXT PRIMARY KEY,name TEXT NOT NULL,owner TEXT NOT NULL,purpose TEXT NOT NULL,enabled INTEGER NOT NULL,visible_indicator INTEGER NOT NULL,consent_reference TEXT NOT NULL,permissions_json TEXT NOT NULL,directories_json TEXT NOT NULL,retention_days INTEGER NOT NULL,public_key_fingerprint TEXT NOT NULL,created_at TEXT NOT NULL,disabled_at TEXT,org_id TEXT NOT NULL DEFAULT 'org_default')""")
  c.execute("""CREATE TABLE IF NOT EXISTS endpoint_telemetry_events(event_id TEXT PRIMARY KEY,collector_id TEXT NOT NULL,event_type TEXT NOT NULL,observed_at TEXT NOT NULL,metadata_json TEXT NOT NULL,expires_at TEXT NOT NULL,org_id TEXT NOT NULL DEFAULT 'org_default')""")
  existing=[row[1] for row in c.execute("PRAGMA table_info(endpoint_collectors)")]
  if "org_id" not in existing:c.execute("ALTER TABLE endpoint_collectors ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
  existing=[row[1] for row in c.execute("PRAGMA table_info(endpoint_telemetry_events)")]
  if "org_id" not in existing:c.execute("ALTER TABLE endpoint_telemetry_events ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
def _serialize(row):return {"collector_id":row[0],"name":row[1],"owner":row[2],"purpose":row[3],"enabled":bool(row[4]),"visible_indicator":bool(row[5]),"consent_reference":row[6],"permissions":json.loads(row[7]),"approved_directories":json.loads(row[8]),"retention_days":row[9],"public_key_fingerprint":row[10],"created_at":row[11],"disabled_at":row[12]}
def list_collectors(org_id=organizations.DEFAULT_ORG_ID):
 initialize_endpoint_telemetry()
 with sqlite3.connect(database_path) as c:return [_serialize(row) for row in c.execute("SELECT collector_id,name,owner,purpose,enabled,visible_indicator,consent_reference,permissions_json,directories_json,retention_days,public_key_fingerprint,created_at,disabled_at FROM endpoint_collectors WHERE org_id=? ORDER BY created_at DESC",(org_id,))]
def register_collector(name,owner,purpose,consent_reference,permissions,directories,retention_days,fingerprint,org_id=organizations.DEFAULT_ORG_ID):
 values={str(item).upper() for item in permissions}
 if not values or not values<=ALLOWED_PERMISSIONS:raise ValueError("Collector permissions must use the read-only permission manifest.")
 if not (1<=int(retention_days)<=90):raise ValueError("Endpoint telemetry retention must be between 1 and 90 days.")
 if len(str(consent_reference).strip())<6:raise ValueError("An owner-consent reference is required.")
 if not re.fullmatch(r"[a-fA-F0-9:]{32,128}",str(fingerprint)):raise ValueError("Collector signing fingerprint is invalid.")
 clean_dirs=[]
 for value in directories:
  path=str(value).replace("\\","/").rstrip("/")
  if not path or ".." in PurePath(path).parts or path in {"/","C:"}:raise ValueError("Approved directory is too broad or unsafe.")
  clean_dirs.append(path)
 cid="col_"+uuid.uuid4().hex;now=utc_now()
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO endpoint_collectors (collector_id,name,owner,purpose,enabled,visible_indicator,consent_reference,permissions_json,directories_json,retention_days,public_key_fingerprint,created_at,disabled_at,org_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(cid,str(name).strip(),str(owner).strip(),str(purpose).strip(),0,1,str(consent_reference).strip(),json.dumps(sorted(values)),json.dumps(sorted(set(clean_dirs))),int(retention_days),str(fingerprint).lower(),now,None,org_id))
 return next(item for item in list_collectors(org_id) if item["collector_id"]==cid)
def set_collector_enabled(collector_id,enabled,actor,org_id=organizations.DEFAULT_ORG_ID):
 with sqlite3.connect(database_path) as c:
  row=c.execute("SELECT visible_indicator,consent_reference FROM endpoint_collectors WHERE collector_id=? AND org_id=?",(collector_id,org_id)).fetchone()
  if not row:raise KeyError("Endpoint collector not found.")
  if enabled and (not row[0] or not row[1]):raise PermissionError("Consent and a visible indicator are required.")
  c.execute("UPDATE endpoint_collectors SET enabled=?,disabled_at=? WHERE collector_id=? AND org_id=?",(int(enabled),None if enabled else utc_now(),collector_id,org_id))
 return {"collector_id":collector_id,"enabled":bool(enabled),"actor":actor}
def validate_event(collector_id,event_type,metadata,org_id=organizations.DEFAULT_ORG_ID):
 event_type=str(event_type).upper()
 mapping={"PROCESS_HEALTH":"PROCESS_HEALTH","FILESYSTEM_EVENT":"FILESYSTEM_EVENTS","NETWORK_METADATA":"NETWORK_METADATA","RESOURCE_USAGE":"RESOURCE_USAGE"}
 with sqlite3.connect(database_path) as c:row=c.execute("SELECT enabled,visible_indicator,permissions_json,directories_json FROM endpoint_collectors WHERE collector_id=? AND org_id=?",(collector_id,org_id)).fetchone()
 if not row or not row[0]:raise PermissionError("Endpoint collector is disabled.")
 if not row[1]:raise PermissionError("Visible monitoring indicator is not active.")
 if mapping.get(event_type) not in json.loads(row[2]):raise PermissionError("Event is outside the collector permission manifest.")
 forbidden={"payload","content","command_line","cookie","token","password","secret","keystrokes","screen","audio","video"}
 if forbidden&{str(key).lower() for key in metadata}:raise PermissionError("Endpoint telemetry contains prohibited fields.")
 if event_type=="FILESYSTEM_EVENT":
  path=str(metadata.get("path","")).replace("\\","/")
  if not any(path==root or path.startswith(root+"/") for root in json.loads(row[3])):raise PermissionError("Filesystem event is outside approved directories.")
 return {"collector_id":collector_id,"event_type":event_type,"accepted":True,"payload_capture":False}
def uninstall_collector(collector_id,confirm=False,org_id=organizations.DEFAULT_ORG_ID):
 if not confirm:raise PermissionError("Collector uninstall requires explicit confirmation.")
 with sqlite3.connect(database_path) as c:
  if not c.execute("SELECT 1 FROM endpoint_collectors WHERE collector_id=? AND org_id=?",(collector_id,org_id)).fetchone():raise KeyError("Endpoint collector not found.")
  c.execute("UPDATE endpoint_collectors SET enabled=0,disabled_at=? WHERE collector_id=? AND org_id=?",(utc_now(),collector_id,org_id))
 return {"collector_id":collector_id,"enabled":False,"uninstall_required":True,"credentials_revoke_required":True}
