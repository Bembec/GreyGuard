"""Universal Tier 2/3 administrator capability controls and fail-closed gate."""
from __future__ import annotations
import json,uuid
from . import db_compat as sqlite3
from datetime import datetime,timedelta,timezone
from .database import database_path
CAPABILITIES=("EXECUTION_ISOLATION","ENDPOINT_TELEMETRY","DEFENSIVE_RESPONSE","BROWSER_CONNECTOR","SIMULATION_LAB")
def now():return datetime.now(timezone.utc)
def utc_now():return now().isoformat()
def initialize_universal_controls(org_id="org_default"):
 with sqlite3.connect(database_path) as c:
  existing_columns={row[1] for row in c.execute("PRAGMA table_info(universal_capability_controls)")}
  if existing_columns and "org_id" not in existing_columns:
   # SQLite cannot ALTER a PRIMARY KEY in place - the old PK (capability alone) would let two
   # orgs collide on the same capability name, so this rebuilds the table with a composite
   # (capability, org_id) key, carrying every pre-existing row into the default org.
   c.execute("ALTER TABLE universal_capability_controls RENAME TO universal_capability_controls_pre_org")
  c.execute("""CREATE TABLE IF NOT EXISTS universal_capability_controls(
    capability TEXT NOT NULL,org_id TEXT NOT NULL DEFAULT 'org_default',enabled INTEGER NOT NULL,
    owner TEXT NOT NULL,purpose TEXT NOT NULL,permissions_json TEXT NOT NULL,agents_json TEXT NOT NULL,
    targets_json TEXT NOT NULL,expires_at TEXT,human_approval INTEGER NOT NULL,dry_run INTEGER NOT NULL,
    rate_limit INTEGER NOT NULL,resource_limit INTEGER NOT NULL,global_kill_switch INTEGER NOT NULL,
    disabled_agents_json TEXT NOT NULL,integration_kill_switch INTEGER NOT NULL,updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL,PRIMARY KEY(capability,org_id))""")
  if existing_columns and "org_id" not in existing_columns:
   c.execute("""INSERT INTO universal_capability_controls
     (capability,org_id,enabled,owner,purpose,permissions_json,agents_json,targets_json,expires_at,
      human_approval,dry_run,rate_limit,resource_limit,global_kill_switch,disabled_agents_json,
      integration_kill_switch,updated_at,updated_by)
     SELECT capability,'org_default',enabled,owner,purpose,permissions_json,agents_json,targets_json,
            expires_at,human_approval,dry_run,rate_limit,resource_limit,global_kill_switch,
            disabled_agents_json,integration_kill_switch,updated_at,updated_by
     FROM universal_capability_controls_pre_org""")
   c.execute("DROP TABLE universal_capability_controls_pre_org")
  c.execute("CREATE TABLE IF NOT EXISTS universal_control_events(event_id TEXT PRIMARY KEY,capability TEXT NOT NULL,event_type TEXT NOT NULL,actor TEXT NOT NULL,timestamp TEXT NOT NULL,detail_json TEXT NOT NULL,org_id TEXT NOT NULL DEFAULT 'org_default')")
  event_columns={row[1] for row in c.execute("PRAGMA table_info(universal_control_events)")}
  if "org_id" not in event_columns:c.execute("ALTER TABLE universal_control_events ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
  for name in CAPABILITIES:
   c.execute("INSERT OR IGNORE INTO universal_capability_controls (capability,org_id,enabled,owner,purpose,permissions_json,agents_json,targets_json,expires_at,human_approval,dry_run,rate_limit,resource_limit,global_kill_switch,disabled_agents_json,integration_kill_switch,updated_at,updated_by) VALUES(?,?,0,'','','[]','[]','[]',NULL,1,1,10,10,0,'[]',0,?,?)",(name,org_id,utc_now(),"system"))
def _row(row):return {"capability":row["capability"],"enabled":bool(row["enabled"]),"owner":row["owner"],"purpose":row["purpose"],"permissions":json.loads(row["permissions_json"]),"agent_allowlist":json.loads(row["agents_json"]),"target_allowlist":json.loads(row["targets_json"]),"expires_at":row["expires_at"],"human_approval":bool(row["human_approval"]),"dry_run":bool(row["dry_run"]),"rate_limit_per_minute":row["rate_limit"],"resource_limit":row["resource_limit"],"global_kill_switch":bool(row["global_kill_switch"]),"disabled_agents":json.loads(row["disabled_agents_json"]),"integration_kill_switch":bool(row["integration_kill_switch"]),"updated_at":row["updated_at"],"updated_by":row["updated_by"]}
def list_controls(org_id):
 initialize_universal_controls(org_id)
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row
  return [_row(row) for row in c.execute("SELECT * FROM universal_capability_controls WHERE org_id=? ORDER BY capability",(org_id,))]
def configure_control(capability,config,actor,org_id):
 initialize_universal_controls(org_id)
 capability=str(capability).upper()
 if capability not in CAPABILITIES:raise ValueError("Universal capability is not registered.")
 enabled=bool(config.get("enabled"));owner=str(config.get("owner","")).strip();purpose=str(config.get("purpose","")).strip();permissions=sorted(set(config.get("permissions",[])));agents=sorted(set(config.get("agent_allowlist",[])));targets=sorted(set(config.get("target_allowlist",[])))
 if enabled and (len(owner)<3 or len(purpose)<5 or not permissions):raise ValueError("Enabled capabilities require owner, purpose and exact permissions.")
 expires=config.get("expires_at")
 if enabled and (not expires or datetime.fromisoformat(str(expires).replace("Z","+00:00"))<=now()):raise ValueError("Enabled capabilities require a future expiry.")
 rate=int(config.get("rate_limit_per_minute",10));resource=int(config.get("resource_limit",10))
 if not 1<=rate<=1000 or not 1<=resource<=1000:raise ValueError("Rate and resource limits must be between 1 and 1000.")
 with sqlite3.connect(database_path) as c:
  old_row=c.execute("SELECT enabled FROM universal_capability_controls WHERE capability=? AND org_id=?",(capability,org_id)).fetchone()
  old=old_row[0] if old_row else 0
  c.execute("UPDATE universal_capability_controls SET enabled=?,owner=?,purpose=?,permissions_json=?,agents_json=?,targets_json=?,expires_at=?,human_approval=?,dry_run=?,rate_limit=?,resource_limit=?,global_kill_switch=?,disabled_agents_json=?,integration_kill_switch=?,updated_at=?,updated_by=? WHERE capability=? AND org_id=?",(int(enabled),owner,purpose,json.dumps(permissions),json.dumps(agents),json.dumps(targets),expires,int(config.get("human_approval",True)),int(config.get("dry_run",True)),rate,resource,int(config.get("global_kill_switch",False)),json.dumps(sorted(set(config.get("disabled_agents",[])))),int(config.get("integration_kill_switch",False)),utc_now(),actor,capability,org_id))
  event="ACTIVATED" if enabled and not old else "CONFIGURED";c.execute("INSERT INTO universal_control_events (event_id,capability,event_type,actor,timestamp,detail_json,org_id) VALUES(?,?,?,?,?,?,?)",("uce_"+uuid.uuid4().hex,capability,event,actor,utc_now(),json.dumps({"notification_required":event=="ACTIVATED"}),org_id))
 return next(item for item in list_controls(org_id) if item["capability"]==capability)
def authorize(capability,actor,org_id,permission,target="",agent="",approved=False,dry_run=True,resource_units=1):
 control=next((item for item in list_controls(org_id) if item["capability"]==capability),None)
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
  recent=c.execute("SELECT COUNT(*) FROM universal_control_events WHERE capability=? AND event_type='USED' AND timestamp>=? AND org_id=?",(capability,(now()-timedelta(minutes=1)).isoformat(),org_id)).fetchone()[0]
  if not reason and recent>=control["rate_limit_per_minute"]:reason="Capability rate limit exceeded."
  event="BLOCKED" if reason else "USED";c.execute("INSERT INTO universal_control_events (event_id,capability,event_type,actor,timestamp,detail_json,org_id) VALUES(?,?,?,?,?,?,?)",("uce_"+uuid.uuid4().hex,capability,event,actor,utc_now(),json.dumps({"reason":reason,"target":target,"agent":agent,"notification_required":not bool(reason)}),org_id))
 if reason:raise PermissionError(reason)
 return {"authorized":True,"capability":capability,"dry_run":bool(dry_run),"data_minimization":True,"sensitive_field_redaction":True,"audit_recorded":True,"notification_required":True}
def removal_plan(capability):
 if capability not in CAPABILITIES:raise KeyError("Universal capability not found.")
 return {"capability":capability,"steps":["Disable through the interface","Activate integration kill switch","Revoke credentials","Stop workers","Remove network access","Preserve audit evidence","Restore previous safe configuration","Run disabled-means-disabled regression test"]}
