"""Fail-closed controls for predefined Docker sandbox jobs."""
from __future__ import annotations
import re,subprocess,threading,uuid
from . import db_compat as sqlite3
from datetime import datetime,timezone
from .database import database_path
from . import organizations

_running={};_lock=threading.Lock();ALLOWED_JOBS={"SANDBOX_PROBE":["python","-c","print('GreyGuard isolated sandbox ready')"]}
def utc_now():return datetime.now(timezone.utc).isoformat()
def initialize_execution_isolation(org_id=organizations.DEFAULT_ORG_ID):
 with sqlite3.connect(database_path) as c:
  existing_columns={row[1] for row in c.execute("PRAGMA table_info(isolation_config)")}
  if existing_columns and "org_id" not in existing_columns:
   # SQLite cannot ALTER a PRIMARY KEY in place - the old PK (config_id=1 singleton) would let
   # two orgs collide on the one global row, so this rebuilds the table with a composite
   # (config_id, org_id) key, carrying the pre-existing row into the default org. Mirrors
   # universal_controls.py's initialize_universal_controls().
   c.execute("ALTER TABLE isolation_config RENAME TO isolation_config_pre_org")
  c.execute("""CREATE TABLE IF NOT EXISTS isolation_config(config_id INTEGER NOT NULL CHECK(config_id=1),org_id TEXT NOT NULL DEFAULT 'org_default',enabled INTEGER NOT NULL,image TEXT NOT NULL,cpu_limit REAL NOT NULL,memory_mb INTEGER NOT NULL,pids_limit INTEGER NOT NULL,timeout_seconds INTEGER NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT NOT NULL,PRIMARY KEY(config_id,org_id))""")
  if existing_columns and "org_id" not in existing_columns:
   c.execute("""INSERT INTO isolation_config (config_id,org_id,enabled,image,cpu_limit,memory_mb,pids_limit,timeout_seconds,updated_at,updated_by)
     SELECT config_id,'org_default',enabled,image,cpu_limit,memory_mb,pids_limit,timeout_seconds,updated_at,updated_by FROM isolation_config_pre_org""")
   c.execute("DROP TABLE isolation_config_pre_org")
  c.execute("""CREATE TABLE IF NOT EXISTS isolation_executions(execution_id TEXT PRIMARY KEY,job_type TEXT NOT NULL,created_at TEXT NOT NULL,started_by TEXT NOT NULL,status TEXT NOT NULL,container_name TEXT NOT NULL,finished_at TEXT,result TEXT,termination_reason TEXT,org_id TEXT NOT NULL DEFAULT 'org_default')""")
  exec_columns={row[1] for row in c.execute("PRAGMA table_info(isolation_executions)")}
  if "org_id" not in exec_columns:c.execute("ALTER TABLE isolation_executions ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
  c.execute("INSERT OR IGNORE INTO isolation_config (config_id,org_id,enabled,image,cpu_limit,memory_mb,pids_limit,timeout_seconds,updated_at,updated_by) VALUES(1,?,0,'greyguard-sandbox:local',0.5,256,64,30,?,?)",(org_id,utc_now(),"system"))
def get_config(org_id=organizations.DEFAULT_ORG_ID):
 initialize_execution_isolation(org_id)
 with sqlite3.connect(database_path) as c:c.row_factory=sqlite3.Row;row=dict(c.execute("SELECT * FROM isolation_config WHERE config_id=1 AND org_id=?",(org_id,)).fetchone())
 row["enabled"]=bool(row["enabled"]);row.update({"network_mode":"none","read_only":True,"non_root":True,"capabilities_dropped":"ALL","no_new_privileges":True,"arbitrary_commands_allowed":False});return row
def update_config(enabled,image,cpu_limit,memory_mb,pids_limit,timeout_seconds,actor,org_id=organizations.DEFAULT_ORG_ID):
 if not re.fullmatch(r"[a-z0-9][a-z0-9._/-]{2,127}(?::[a-zA-Z0-9._-]+)?",image):raise ValueError("Sandbox image reference is invalid.")
 if not 0.1<=cpu_limit<=2 or not 64<=memory_mb<=1024 or not 16<=pids_limit<=256 or not 1<=timeout_seconds<=300:raise ValueError("Sandbox resource limits are outside the supported range.")
 initialize_execution_isolation(org_id)
 with sqlite3.connect(database_path) as c:c.execute("UPDATE isolation_config SET enabled=?,image=?,cpu_limit=?,memory_mb=?,pids_limit=?,timeout_seconds=?,updated_at=?,updated_by=? WHERE config_id=1 AND org_id=?",(int(enabled),image,cpu_limit,memory_mb,pids_limit,timeout_seconds,utc_now(),actor,org_id))
 return get_config(org_id)
def docker_command(job_type,execution_id,org_id=organizations.DEFAULT_ORG_ID):
 config=get_config(org_id)
 if not config["enabled"]:raise PermissionError("Controlled Docker execution is disabled.")
 if job_type not in ALLOWED_JOBS:raise PermissionError("Only predefined sandbox jobs are permitted.")
 name="greyguard-"+execution_id
 return ["docker","run","--rm","--name",name,"--network","none","--read-only","--user","65532:65532","--cap-drop","ALL","--security-opt","no-new-privileges:true","--pids-limit",str(config["pids_limit"]),"--cpus",str(config["cpu_limit"]),"--memory",f"{config['memory_mb']}m","--tmpfs","/workspace:rw,noexec,nosuid,nodev,size=32m",config["image"],*ALLOWED_JOBS[job_type]]
def run_predefined_job(job_type,actor,org_id=organizations.DEFAULT_ORG_ID,runner=subprocess.run):
 execution_id="iso_"+uuid.uuid4().hex;command=docker_command(job_type,execution_id,org_id);name="greyguard-"+execution_id;config=get_config(org_id)
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO isolation_executions (execution_id,job_type,created_at,started_by,status,container_name,finished_at,result,termination_reason,org_id) VALUES(?,?,?,?,?,?,?,?,?,?)",(execution_id,job_type,utc_now(),actor,"RUNNING",name,None,None,None,org_id))
 with _lock:_running[execution_id]=(name,org_id)
 try:
  result=runner(command,capture_output=True,text=True,timeout=config["timeout_seconds"],check=False);status="SUCCEEDED" if result.returncode==0 else "FAILED";output=(result.stdout or result.stderr or "")[:2000]
 except subprocess.TimeoutExpired:status="TIMED_OUT";output="Execution exceeded its approved timeout."
 finally:
  with _lock:_running.pop(execution_id,None)
 with sqlite3.connect(database_path) as c:
  # Only a still-RUNNING record is finalized here; an emergency TERMINATED status must never be overwritten.
  c.execute("UPDATE isolation_executions SET status=?,finished_at=?,result=? WHERE execution_id=? AND org_id=? AND status='RUNNING'",(status,utc_now(),output,execution_id,org_id))
  c.row_factory=sqlite3.Row;status=c.execute("SELECT status FROM isolation_executions WHERE execution_id=? AND org_id=?",(execution_id,org_id)).fetchone()["status"]
 return {"execution_id":execution_id,"status":status,"result":output}
CONTAINER_NAME_PATTERN=re.compile(r"greyguard-iso_[0-9a-f]{32}")
def emergency_terminate(actor,org_id=organizations.DEFAULT_ORG_ID,runner=subprocess.run):
 """Kill every RUNNING sandbox job *in this org*, whichever backend worker started it.

 Scoped by org_id so one org's emergency stop can never terminate another org's running
 container - cross-tenant denial of service, not just a tenancy gap. The database is the
 source of truth because each worker process has its own memory; the in-memory registry is
 merged in as a fallback for jobs not yet visible elsewhere, filtered to the same org.
 """
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row
  targets={r["execution_id"]:r["container_name"] for r in c.execute("SELECT execution_id,container_name FROM isolation_executions WHERE status='RUNNING' AND org_id=?",(org_id,))}
 with _lock:targets.update({execution_id:name for execution_id,(name,running_org_id) in _running.items() if running_org_id==org_id})
 terminated=[]
 for execution_id,name in targets.items():
  if not CONTAINER_NAME_PATTERN.fullmatch(name):continue
  runner(["docker","kill",name],capture_output=True,text=True,timeout=10,check=False);terminated.append(execution_id)
  with sqlite3.connect(database_path) as c:c.execute("UPDATE isolation_executions SET status='TERMINATED',finished_at=?,termination_reason=? WHERE execution_id=? AND org_id=?",(utc_now(),f"Emergency termination by {actor}",execution_id,org_id))
 return {"terminated":terminated,"count":len(terminated)}
def execution_history(limit=100,org_id=organizations.DEFAULT_ORG_ID):
 initialize_execution_isolation(org_id)
 with sqlite3.connect(database_path) as c:c.row_factory=sqlite3.Row;return [dict(r) for r in c.execute("SELECT * FROM isolation_executions WHERE org_id=? ORDER BY created_at DESC LIMIT ?",(org_id,limit))]
