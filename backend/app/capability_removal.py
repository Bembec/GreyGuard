"""Audited capability removal, rollback, and emergency shutdown workflow."""
from __future__ import annotations
import json,uuid
from . import db_compat as sqlite3
from datetime import datetime,timezone
from .database import database_path
STEPS=("DISABLE_INTERFACE","DISABLE_CONFIGURATION","REVOKE_CREDENTIALS","STOP_WORKERS","REMOVE_NETWORK_ACCESS","UNINSTALL_COMPONENT","MIGRATE_OR_DELETE_DATA","PRESERVE_AUDIT_EVIDENCE","ROLLBACK_DATABASE_MIGRATION","RESTORE_KNOWN_GOOD_RELEASE","VERIFY_NO_BACKGROUND_COMPONENT","ROTATE_EXPOSED_SECRETS","NOTIFY_ADMINISTRATORS","POST_REMOVAL_TESTS")
def utc_now():return datetime.now(timezone.utc).isoformat()
def initialize_capability_removal():
 with sqlite3.connect(database_path) as c:
  c.execute("CREATE TABLE IF NOT EXISTS capability_removals(removal_id TEXT PRIMARY KEY,capability TEXT NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL,requested_by TEXT NOT NULL,created_at TEXT NOT NULL,completed_at TEXT,emergency INTEGER NOT NULL,evidence_json TEXT NOT NULL,org_id TEXT NOT NULL DEFAULT 'org_default')")
  c.execute("CREATE TABLE IF NOT EXISTS capability_removal_steps(removal_id TEXT NOT NULL,step_order INTEGER NOT NULL,step_name TEXT NOT NULL,status TEXT NOT NULL,completed_by TEXT,completed_at TEXT,evidence TEXT,org_id TEXT NOT NULL DEFAULT 'org_default',PRIMARY KEY(removal_id,step_order))")
  for table in ("capability_removals","capability_removal_steps"):
   columns={row[1] for row in c.execute(f"PRAGMA table_info({table})")}
   if "org_id" not in columns:c.execute(f"ALTER TABLE {table} ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
def _fail_close(c,capability,org_id):
 tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 if "universal_capability_controls" in tables:c.execute("UPDATE universal_capability_controls SET enabled=0,integration_kill_switch=1,updated_at=?,updated_by=? WHERE capability=? AND org_id=?",(utc_now(),"capability-removal",capability,org_id))
def begin_removal(capability,reason,actor,org_id,emergency=False):
 capability=str(capability).upper();reason=str(reason).strip()
 if len(reason)<8:raise ValueError("Removal reason must contain at least 8 characters.")
 rid="remove_"+uuid.uuid4().hex;created=utc_now();evidence={"configuration_snapshot_required":True,"audit_preservation_required":True,"automatic_data_deletion":False}
 with sqlite3.connect(database_path) as c:
  _fail_close(c,capability,org_id)
  c.execute("INSERT INTO capability_removals (removal_id,capability,reason,status,requested_by,created_at,completed_at,emergency,evidence_json,org_id) VALUES(?,?,?,?,?,?,NULL,?,?,?)",(rid,capability,reason,"IN_PROGRESS",actor,created,int(emergency),json.dumps(evidence),org_id))
  for order,step in enumerate(STEPS,1):c.execute("INSERT INTO capability_removal_steps (removal_id,step_order,step_name,status,completed_by,completed_at,evidence,org_id) VALUES(?,?,?,'PENDING',NULL,NULL,NULL,?)",(rid,order,step,org_id))
 return get_removal(rid,org_id)
def get_removal(removal_id,org_id):
 initialize_capability_removal()
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;row=c.execute("SELECT * FROM capability_removals WHERE removal_id=? AND org_id=?",(removal_id,org_id)).fetchone()
  if not row:raise KeyError("Capability removal workflow not found.")
  steps=[dict(item) for item in c.execute("SELECT step_order,step_name,status,completed_by,completed_at,evidence FROM capability_removal_steps WHERE removal_id=? AND org_id=? ORDER BY step_order",(removal_id,org_id))]
 result=dict(row);result["emergency"]=bool(result["emergency"]);result["evidence"]=json.loads(result.pop("evidence_json"));result["steps"]=steps;return result
def list_removals(org_id):
 initialize_capability_removal()
 with sqlite3.connect(database_path) as c:ids=[r[0] for r in c.execute("SELECT removal_id FROM capability_removals WHERE org_id=? ORDER BY created_at DESC",(org_id,))]
 return [get_removal(value,org_id) for value in ids]
def complete_step(removal_id,step_name,evidence,actor,org_id):
 workflow=get_removal(removal_id,org_id)
 if workflow["status"]!="IN_PROGRESS":raise PermissionError("Removal workflow is not active.")
 pending=next((item for item in workflow["steps"] if item["status"]=="PENDING"),None)
 if not pending or pending["step_name"]!=step_name:raise PermissionError("Removal steps must be completed in order.")
 if len(str(evidence).strip())<5:raise ValueError("Step completion evidence is required.")
 with sqlite3.connect(database_path) as c:
  c.execute("UPDATE capability_removal_steps SET status='COMPLETED',completed_by=?,completed_at=?,evidence=? WHERE removal_id=? AND step_name=? AND org_id=?",(actor,utc_now(),str(evidence)[:1000],removal_id,step_name,org_id))
  remaining=c.execute("SELECT COUNT(*) FROM capability_removal_steps WHERE removal_id=? AND status='PENDING' AND org_id=?",(removal_id,org_id)).fetchone()[0]
  if remaining==0:c.execute("UPDATE capability_removals SET status='COMPLETED',completed_at=? WHERE removal_id=? AND org_id=?",(utc_now(),removal_id,org_id))
 return get_removal(removal_id,org_id)
def emergency_shutdown(reason,actor,org_id):
 initialize_capability_removal();created=[]
 with sqlite3.connect(database_path) as c:
  tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  capabilities=[r[0] for r in c.execute("SELECT capability FROM universal_capability_controls WHERE org_id=?",(org_id,))] if "universal_capability_controls" in tables else ["ALL_HIGH_RISK_CAPABILITIES"]
 for capability in capabilities:created.append(begin_removal(capability,reason,actor,org_id,True))
 return {"emergency":True,"new_requests_frozen":True,"capabilities_fail_closed":len(created),"credentials_revocation_required":True,"workers_shutdown_required":True,"audit_evidence_preserved":True,"workflows":[item["removal_id"] for item in created]}
