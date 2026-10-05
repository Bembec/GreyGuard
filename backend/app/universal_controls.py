"""Universal Tier 2/3 administrator capability controls and fail-closed gate."""
from __future__ import annotations
import json,sqlite3,uuid
from datetime import datetime,timedelta,timezone
from .database import database_path
CAPABILITIES=("EXECUTION_ISOLATION","ENDPOINT_TELEMETRY","DEFENSIVE_RESPONSE","BROWSER_CONNECTOR","SIMULATION_LAB")
def now():return datetime.now(timezone.utc)
def utc_now():return now().isoformat()
def initialize_universal_controls():
 with sqlite3.connect(database_path) as c:
  c.execute("CREATE TABLE IF NOT EXISTS universal_capability_controls(capability TEXT PRIMARY KEY,enabled INTEGER NOT NULL,owner TEXT NOT NULL,purpose TEXT NOT NULL,permissions_json TEXT NOT NULL,agents_json TEXT NOT NULL,targets_json TEXT NOT NULL,expires_at TEXT,human_approval INTEGER NOT NULL,dry_run INTEGER NOT NULL,rate_limit INTEGER NOT NULL,resource_limit INTEGER NOT NULL,global_kill_switch INTEGER NOT NULL,disabled_agents_json TEXT NOT NULL,integration_kill_switch INTEGER NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT NOT NULL)")
  c.execute("CREATE TABLE IF NOT EXISTS universal_control_events(event_id TEXT PRIMARY KEY,capability TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,timestamp TEXT NOT NULL,detail_json TEXT NOT NULL)")
  for name in CAPABILITIES:c.execute("INSERT OR IGNORE INTO universal_capability_controls VALUES(?,0,'','','[]','[]','[]',NULL,1,1,10,10,0,'[]',0,?,?)",(name,utc_now(),"system"))
def _row(row):return {"capability":row[0],"enabled":bool(row[1]),"owner":row[2],"purpose":row[3],"permissions":json.loads(row[4]),"agent_allowlist":json.loads(row[5]),"target_allowlist":json.loads(row[6]),"expires_at":row[7],"human_approval":bool(row[8]),"dry_run":bool(row[9]),"rate_limit_per_minute":row[10],"resource_limit":row[11],"global_kill_switch":bool(row[12]),"disabled_agents":json.loads(row[13]),"integration_kill_switch":bool(row[14]),"updated_at":row[15],"updated_by":row[16]}
def list_controls():
 initialize_universal_controls()
 with sqlite3.connect(database_path) as c:return [_row(row) for row in c.execute("SELECT * FROM universal_capability_controls ORDER BY capability")]
def configure_control(capability,config,actor):
 capability=str(capability).upper()
 if capability not in CAPABILITIES:raise ValueError("Universal capability is not registered.")
 enabled=bool(config.get("enabled"));owner=str(config.get("owner","")).strip();purpose=str(config.get("purpose","")).strip();permissions=sorted(set(config.get("permissions",[])));agents=sorted(set(config.get("agent_allowlist",[])));targets=sorted(set(config.get("target_allowlist",[])))
 if enabled and (len(owner)<3 or len(purpose)<5 or not permissions):raise ValueError("Enabled capabilities require owner, purpose and exact permissions.")
 expires=config.get("expires_at")
 if enabled and (not expires or datetime.fromisoformat(str(expires).replace("Z","+00:00"))<=now()):raise ValueError("Enabled capabilities require a future expiry.")
 rate=int(config.get("rate_limit_per_minute",10));resource=int(config.get("resource_limit",10))
 if not 1<=rate<=1000 or not 1<=resource<=1000:raise ValueError("Rate and resource limits must be between 1 and 1000.")
 with sqlite3.connect(database_path) as c:
  old=c.execute("SELECT enabled FROM universal_capability_controls WHERE capability=?",(capability,)).fetchone()[0]
  c.execute("UPDATE universal_capability_controls SET enabled=?,owner=?,purpose=?,permissions_json=?,agents_json=?,targets_json=?,expires_at=?,human_approval=?,dry_run=?,rate_limit=?,resource_limit=?,global_kill_switch=?,disabled_agents_json=?,integration_kill_switch=?,updated_at=?,updated_by=? WHERE capability=?",(int(enabled),owner,purpose,json.dumps(permissions),json.dumps(agents),json.dumps(targets),expires,int(config.get("human_approval",True)),int(config.get("dry_run",True)),rate,resource,int(config.get("global_kill_switch",False)),json.dumps(sorted(set(config.get("disabled_agents",[])))),int(config.get("integration_kill_switch",False)),utc_now(),actor,capability))
  event="ACTIVATED" if enabled and not old else "CONFIGURED";c.execute("INSERT INTO universal_control_events VALUES(?,?,?,?,?,?)",("uce_"+uuid.uuid4().hex,capability,event,actor,utc_now(),json.dumps({"notification_required":event=="ACTIVATED"})))
 return next(item for item in list_controls() if item["capability"]==capability)
def authorize(capability,actor,permission,target="",agent="",approved=False,dry_run=True,resource_units=1):
 control=next((item for item in list_controls() if item["capability"]==capability),None)
 reason=None
 if not control or not control["enabled"]:reason="Capability is disabled."
 elif control["global_kill_switch"] or control["integration_kill_switch"]:reason="Capability kill switch is active."
 elif control["expires_at"] and datetime.fromisoformat(control["expires_at"].replace("Z","+00:00"))<=now():reason="Capability authorization expired."
 elif permission not in control["permissions"]:reason="Permission is outside the manifest."
 elif control["agent_allowlist"] and agent not in control["agent_allowlist"]:reason="Agent is outside the allowlist."
 elif agent and agent in control["disabled_agents"]:reason="Per-agent kill switch is active."
 elif control["target_allowlist"] and target not in control["target_allowlist"]:reason="Target is outside the allowlist."
 elif control["human_approval"] and not approved:reason="Human approval is required."
 elif control["dry_run"] and not dry_run:reason="Capability is restricted to dry-run mode."
 elif int(resource_units)>control["resource_limit"]:reason="Resource limit exceeded."
 with sqlite3.connect(database_path) as c:
  recent=c.execute("SELECT COUNT(*) FROM universal_control_events WHERE capability=? AND event_type='USED' AND timestamp>=?",(capability,(now()-timedelta(minutes=1)).isoformat())).fetchone()[0]
  if not reason and recent>=control["rate_limit_per_minute"]:reason="Capability rate limit exceeded."
  event="BLOCKED" if reason else "USED";c.execute("INSERT INTO universal_control_events VALUES(?,?,?,?,?,?)",("uce_"+uuid.uuid4().hex,capability,event,actor,utc_now(),json.dumps({"reason":reason,"target":target,"agent":agent,"notification_required":not bool(reason)})))
 if reason:raise PermissionError(reason)
 return {"authorized":True,"capability":capability,"dry_run":bool(dry_run),"data_minimization":True,"sensitive_field_redaction":True,"audit_recorded":True,"notification_required":True}
def removal_plan(capability):
 if capability not in CAPABILITIES:raise KeyError("Universal capability not found.")
 return {"capability":capability,"steps":["Disable through the interface","Activate integration kill switch","Revoke credentials","Stop workers","Remove network access","Preserve audit evidence","Restore previous safe configuration","Run disabled-means-disabled regression test"]}
