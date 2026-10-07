"""Fail-closed controls for predefined Docker sandbox jobs."""
from __future__ import annotations
import re,subprocess,threading,uuid
from . import db_compat as sqlite3
from datetime import datetime,timezone
from .database import database_path

_running={};_lock=threading.Lock();ALLOWED_JOBS={"SANDBOX_PROBE":["python","-c","print('GreyGuard isolated sandbox ready')"]}
def utc_now():return datetime.now(timezone.utc).isoformat()
def initialize_execution_isolation():
 with sqlite3.connect(database_path) as c:
  c.execute("""CREATE TABLE IF NOT EXISTS isolation_config(config_id INTEGER PRIMARY KEY CHECK(config_id=1),enabled INTEGER NOT NULL,image TEXT NOT NULL,cpu_limit REAL NOT NULL,memory_mb INTEGER NOT NULL,pids_limit INTEGER NOT NULL,timeout_seconds INTEGER NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT NOT NULL)""")
  c.execute("INSERT OR IGNORE INTO isolation_config VALUES(1,0,'greyguard-sandbox:local',0.5,256,64,30,?,?)",(utc_now(),"system"))
  c.execute("""CREATE TABLE IF NOT EXISTS isolation_executions(execution_id TEXT PRIMARY KEY,job_type TEXT NOT NULL,created_at TEXT NOT NULL,started_by TEXT NOT NULL,status TEXT NOT NULL,container_name TEXT NOT NULL,finished_at TEXT,result TEXT,termination_reason TEXT)""")
def get_config():
 initialize_execution_isolation()
 with sqlite3.connect(database_path) as c:c.row_factory=sqlite3.Row;row=dict(c.execute("SELECT * FROM isolation_config WHERE config_id=1").fetchone())
 row["enabled"]=bool(row["enabled"]);row.update({"network_mode":"none","read_only":True,"non_root":True,"capabilities_dropped":"ALL","no_new_privileges":True,"arbitrary_commands_allowed":False});return row
def update_config(enabled,image,cpu_limit,memory_mb,pids_limit,timeout_seconds,actor):
 if not re.fullmatch(r"[a-z0-9][a-z0-9._/-]{2,127}(?::[a-zA-Z0-9._-]+)?",image):raise ValueError("Sandbox image reference is invalid.")
 if not 0.1<=cpu_limit<=2 or not 64<=memory_mb<=1024 or not 16<=pids_limit<=256 or not 1<=timeout_seconds<=300:raise ValueError("Sandbox resource limits are outside the supported range.")
 with sqlite3.connect(database_path) as c:c.execute("UPDATE isolation_config SET enabled=?,image=?,cpu_limit=?,memory_mb=?,pids_limit=?,timeout_seconds=?,updated_at=?,updated_by=? WHERE config_id=1",(int(enabled),image,cpu_limit,memory_mb,pids_limit,timeout_seconds,utc_now(),actor))
 return get_config()
def docker_command(job_type,execution_id):
 config=get_config()
 if not config["enabled"]:raise PermissionError("Controlled Docker execution is disabled.")
 if job_type not in ALLOWED_JOBS:raise PermissionError("Only predefined sandbox jobs are permitted.")
 name="greyguard-"+execution_id
 return ["docker","run","--rm","--name",name,"--network","none","--read-only","--user","65532:65532","--cap-drop","ALL","--security-opt","no-new-privileges:true","--pids-limit",str(config["pids_limit"]),"--cpus",str(config["cpu_limit"]),"--memory",f"{config['memory_mb']}m","--tmpfs","/workspace:rw,noexec,nosuid,nodev,size=32m",config["image"],*ALLOWED_JOBS[job_type]]
def run_predefined_job(job_type,actor,runner=subprocess.run):
 execution_id="iso_"+uuid.uuid4().hex;command=docker_command(job_type,execution_id);name="greyguard-"+execution_id;config=get_config()
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO isolation_executions VALUES(?,?,?,?,?,?,?,?,?)",(execution_id,job_type,utc_now(),actor,"RUNNING",name,None,None,None))
 with _lock:_running[execution_id]=name
 try:
  result=runner(command,capture_output=True,text=True,timeout=config["timeout_seconds"],check=False);status="SUCCEEDED" if result.returncode==0 else "FAILED";output=(result.stdout or result.stderr or "")[:2000]
 except subprocess.TimeoutExpired:status="TIMED_OUT";output="Execution exceeded its approved timeout."
 finally:
  with _lock:_running.pop(execution_id,None)
 with sqlite3.connect(database_path) as c:
  # Only a still-RUNNING record is finalized here; an emergency TERMINATED status must never be overwritten.
  c.execute("UPDATE isolation_executions SET status=?,finished_at=?,result=? WHERE execution_id=? AND status='RUNNING'",(status,utc_now(),output,execution_id))
  c.row_factory=sqlite3.Row;status=c.execute("SELECT status FROM isolation_executions WHERE execution_id=?",(execution_id,)).fetchone()["status"]
 return {"execution_id":execution_id,"status":status,"result":output}
CONTAINER_NAME_PATTERN=re.compile(r"greyguard-iso_[0-9a-f]{32}")
def emergency_terminate(actor,runner=subprocess.run):
 """Kill every RUNNING sandbox job, whichever backend worker started it.

 The database is the source of truth because each worker process has its own memory;
 the in-memory registry is merged in as a fallback for jobs not yet visible elsewhere.
 """
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row
  targets={r["execution_id"]:r["container_name"] for r in c.execute("SELECT execution_id,container_name FROM isolation_executions WHERE status='RUNNING'")}
 with _lock:targets.update(_running)
 terminated=[]
 for execution_id,name in targets.items():
  if not CONTAINER_NAME_PATTERN.fullmatch(name):continue
  runner(["docker","kill",name],capture_output=True,text=True,timeout=10,check=False);terminated.append(execution_id)
  with sqlite3.connect(database_path) as c:c.execute("UPDATE isolation_executions SET status='TERMINATED',finished_at=?,termination_reason=? WHERE execution_id=?",(utc_now(),f"Emergency termination by {actor}",execution_id))
 return {"terminated":terminated,"count":len(terminated)}
def execution_history(limit=100):
 initialize_execution_isolation()
 with sqlite3.connect(database_path) as c:c.row_factory=sqlite3.Row;return [dict(r) for r in c.execute("SELECT * FROM isolation_executions ORDER BY created_at DESC LIMIT ?",(limit,))]
