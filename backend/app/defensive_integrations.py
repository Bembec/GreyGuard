"""Permissioned browser connectors and reversible defensive-response plans."""
from __future__ import annotations
import json,re,uuid
from . import db_compat as sqlite3
from datetime import datetime,timedelta,timezone
from .database import database_path
from . import organizations

SAFE_ACTIONS={"TERMINATE_APPROVED_PROCESS","QUARANTINE_FILE","TEMPORARY_NETWORK_ISOLATION","REVOKE_CREDENTIAL","SUSPEND_AGENT","DISABLE_TOOL","DISABLE_INTEGRATION"}
def now():return datetime.now(timezone.utc)
def utc_now():return now().isoformat()
def initialize_defensive_integrations():
 with sqlite3.connect(database_path) as c:
  c.execute("CREATE TABLE IF NOT EXISTS browser_connectors(connector_id TEXT PRIMARY KEY,name TEXT NOT NULL,owner TEXT NOT NULL,purpose TEXT NOT NULL,enabled INTEGER NOT NULL,visible_indicator INTEGER NOT NULL,domains_json TEXT NOT NULL,consent_reference TEXT NOT NULL,created_at TEXT NOT NULL,disconnected_at TEXT,org_id TEXT NOT NULL DEFAULT 'org_default')")
  c.execute("CREATE TABLE IF NOT EXISTS defensive_response_plans(response_id TEXT PRIMARY KEY,action TEXT NOT NULL,target TEXT NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL,requested_by TEXT NOT NULL,approved_by TEXT,created_at TEXT NOT NULL,expires_at TEXT NOT NULL,evidence_preserved INTEGER NOT NULL,recovery_json TEXT NOT NULL,completed_at TEXT,org_id TEXT NOT NULL DEFAULT 'org_default')")
  existing=[row[1] for row in c.execute("PRAGMA table_info(browser_connectors)")]
  if "org_id" not in existing:c.execute("ALTER TABLE browser_connectors ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
  existing=[row[1] for row in c.execute("PRAGMA table_info(defensive_response_plans)")]
  if "org_id" not in existing:c.execute("ALTER TABLE defensive_response_plans ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
def _domain(value):
 value=str(value).strip().lower()
 if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?",value) or "." not in value:raise ValueError("Connector domain is invalid.")
 return value
def list_connectors(org_id=organizations.DEFAULT_ORG_ID):
 initialize_defensive_integrations()
 with sqlite3.connect(database_path) as c:return [{"connector_id":r[0],"name":r[1],"owner":r[2],"purpose":r[3],"enabled":bool(r[4]),"visible_indicator":bool(r[5]),"domains":json.loads(r[6]),"consent_reference":r[7],"created_at":r[8],"disconnected_at":r[9]} for r in c.execute("SELECT connector_id,name,owner,purpose,enabled,visible_indicator,domains_json,consent_reference,created_at,disconnected_at FROM browser_connectors WHERE org_id=? ORDER BY created_at DESC",(org_id,))]
def create_connector(name,owner,purpose,domains,consent_reference,org_id=organizations.DEFAULT_ORG_ID):
 clean=sorted({_domain(item) for item in domains})
 if not clean:raise ValueError("At least one connector domain is required.")
 if len(str(consent_reference).strip())<6:raise ValueError("Connector consent reference is required.")
 cid="browser_"+uuid.uuid4().hex
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO browser_connectors (connector_id,name,owner,purpose,enabled,visible_indicator,domains_json,consent_reference,created_at,disconnected_at,org_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(cid,str(name).strip(),str(owner).strip(),str(purpose).strip(),0,1,json.dumps(clean),str(consent_reference).strip(),utc_now(),None,org_id))
 return next(item for item in list_connectors(org_id) if item["connector_id"]==cid)
def set_connector_enabled(connector_id,enabled,org_id=organizations.DEFAULT_ORG_ID):
 with sqlite3.connect(database_path) as c:
  row=c.execute("SELECT visible_indicator,domains_json FROM browser_connectors WHERE connector_id=? AND org_id=?",(connector_id,org_id)).fetchone()
  if not row:raise KeyError("Browser connector not found.")
  if enabled and (not row[0] or not json.loads(row[1])):raise PermissionError("Visible indicator and domain allowlist are required.")
  c.execute("UPDATE browser_connectors SET enabled=?,disconnected_at=? WHERE connector_id=? AND org_id=?",(int(enabled),None if enabled else utc_now(),connector_id,org_id))
 return {"connector_id":connector_id,"enabled":bool(enabled)}
def authorize_browser_access(connector_id,domain,fields,org_id=organizations.DEFAULT_ORG_ID):
 with sqlite3.connect(database_path) as c:row=c.execute("SELECT enabled,visible_indicator,domains_json FROM browser_connectors WHERE connector_id=? AND org_id=?",(connector_id,org_id)).fetchone()
 if not row or not row[0]:raise PermissionError("Browser connector is disconnected.")
 if not row[1]:raise PermissionError("Visible connector indicator is required.")
 if _domain(domain) not in json.loads(row[2]):raise PermissionError("Domain is outside the connector allowlist.")
 prohibited={"cookie","cookies","password","password_field","token","session_token","authorization"}
 if prohibited&{str(item).lower() for item in fields}:raise PermissionError("Credential and session data capture is prohibited.")
 return {"authorized":True,"domain":domain,"fields":sorted(set(fields)),"visible_indicator":True}
def request_response(action,target,reason,duration_minutes,actor,org_id=organizations.DEFAULT_ORG_ID):
 action=str(action).upper()
 if action not in SAFE_ACTIONS:raise ValueError("Defensive response action is not allowlisted.")
 if not (1<=int(duration_minutes)<=1440):raise ValueError("Defensive response expiry must be between 1 minute and 24 hours.")
 rid="resp_"+uuid.uuid4().hex;created=now();expires=created+timedelta(minutes=int(duration_minutes));recovery={"automatic_expiry":True,"restore_previous_state":True,"notify_administrators":True}
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO defensive_response_plans (response_id,action,target,reason,status,requested_by,approved_by,created_at,expires_at,evidence_preserved,recovery_json,completed_at,org_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(rid,action,str(target).strip(),str(reason).strip(),"PENDING_APPROVAL",actor,None,created.isoformat(),expires.isoformat(),1,json.dumps(recovery),None,org_id))
 return {"response_id":rid,"status":"PENDING_APPROVAL","action":action,"expires_at":expires.isoformat(),"evidence_preserved":True,"recovery":recovery}
def approve_response(response_id,approver,org_id=organizations.DEFAULT_ORG_ID):
 with sqlite3.connect(database_path) as c:
  row=c.execute("SELECT requested_by,expires_at,status FROM defensive_response_plans WHERE response_id=? AND org_id=?",(response_id,org_id)).fetchone()
  if not row:raise KeyError("Defensive response not found.")
  if row[0]==approver:raise PermissionError("Defensive response requires a separate approver.")
  if row[2]!="PENDING_APPROVAL" or datetime.fromisoformat(row[1])<=now():raise PermissionError("Defensive response is not active for approval.")
  c.execute("UPDATE defensive_response_plans SET status='APPROVED',approved_by=? WHERE response_id=? AND org_id=?",(approver,response_id,org_id))
 return {"response_id":response_id,"status":"APPROVED","approved_by":approver,"execution_requires_controlled_adapter":True}
def list_responses(org_id=organizations.DEFAULT_ORG_ID):
 initialize_defensive_integrations()
 with sqlite3.connect(database_path) as c:return [{"response_id":r[0],"action":r[1],"target":r[2],"reason":r[3],"status":r[4],"requested_by":r[5],"approved_by":r[6],"created_at":r[7],"expires_at":r[8],"evidence_preserved":bool(r[9]),"recovery":json.loads(r[10])} for r in c.execute("SELECT response_id,action,target,reason,status,requested_by,approved_by,created_at,expires_at,evidence_preserved,recovery_json FROM defensive_response_plans WHERE org_id=? ORDER BY created_at DESC LIMIT 100",(org_id,))]
