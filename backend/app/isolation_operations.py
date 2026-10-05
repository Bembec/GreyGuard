"""Per-agent workspaces, quarantine, network policy, and Kubernetes job controls."""
from __future__ import annotations
import hashlib,json,re,shutil,sqlite3,uuid
from datetime import datetime,timezone
from pathlib import Path
from .database import database_path

backend_path=Path(__file__).resolve().parents[1];workspace_root=(backend_path/"data"/"isolated_workspaces").resolve();quarantine_root=(backend_path/"data"/"quarantine").resolve()
def utc_now():return datetime.now(timezone.utc).isoformat()
def initialize_isolation_operations():
 workspace_root.mkdir(parents=True,exist_ok=True);quarantine_root.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(database_path) as c:
  c.execute("""CREATE TABLE IF NOT EXISTS isolation_operations_config(config_id INTEGER PRIMARY KEY CHECK(config_id=1),global_kill_switch INTEGER NOT NULL,network_enabled INTEGER NOT NULL,destination_allowlist_json TEXT NOT NULL,dns_allowlist_json TEXT NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT NOT NULL)""")
  c.execute("INSERT OR IGNORE INTO isolation_operations_config VALUES(1,0,0,'[]','[]',?,?)",(utc_now(),"system"))
  c.execute("""CREATE TABLE IF NOT EXISTS isolated_workspaces(workspace_id TEXT PRIMARY KEY,agent_name TEXT NOT NULL UNIQUE,path TEXT NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL,destroyed_at TEXT,destroyed_by TEXT)""")
  c.execute("""CREATE TABLE IF NOT EXISTS quarantined_artifacts(artifact_id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,original_name TEXT NOT NULL,sha256 TEXT NOT NULL,size_bytes INTEGER NOT NULL,quarantine_path TEXT NOT NULL,status TEXT NOT NULL,scan_engine TEXT,scan_result TEXT,created_at TEXT NOT NULL,scanned_at TEXT)""")
def _safe_agent(agent_name):
 value=str(agent_name).strip()
 if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}",value):raise ValueError("Agent name is unsafe for workspace isolation.")
 return value
def _inside(root,path):
 try:path.resolve().relative_to(root);return True
 except ValueError:return False
def get_operations():
 initialize_isolation_operations()
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;config=dict(c.execute("SELECT * FROM isolation_operations_config WHERE config_id=1").fetchone());workspaces=[dict(r) for r in c.execute("SELECT * FROM isolated_workspaces ORDER BY created_at DESC")];artifacts=[dict(r) for r in c.execute("SELECT artifact_id,workspace_id,original_name,sha256,size_bytes,status,scan_engine,scan_result,created_at,scanned_at FROM quarantined_artifacts ORDER BY created_at DESC LIMIT 100")]
 config["global_kill_switch"]=bool(config["global_kill_switch"]);config["network_enabled"]=bool(config["network_enabled"]);config["destination_allowlist"]=json.loads(config.pop("destination_allowlist_json"));config["dns_allowlist"]=json.loads(config.pop("dns_allowlist_json"));return {"config":config,"workspaces":workspaces,"artifacts":artifacts}
def update_operations(global_kill_switch,network_enabled,destinations,dns_names,actor):
 clean_dest=[]
 for item in destinations:
  if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]{1,5})?",item):raise ValueError("Destination allowlist contains an invalid host or port.")
  clean_dest.append(item.lower())
 clean_dns=[]
 for item in dns_names:
  if not re.fullmatch(r"[A-Za-z0-9.-]+",item):raise ValueError("DNS allowlist contains an invalid name.")
  clean_dns.append(item.lower())
 if network_enabled and (not clean_dest or not clean_dns):raise ValueError("Network enablement requires destination and DNS allowlists.")
 with sqlite3.connect(database_path) as c:c.execute("UPDATE isolation_operations_config SET global_kill_switch=?,network_enabled=?,destination_allowlist_json=?,dns_allowlist_json=?,updated_at=?,updated_by=? WHERE config_id=1",(int(global_kill_switch),int(network_enabled),json.dumps(sorted(set(clean_dest))),json.dumps(sorted(set(clean_dns))),utc_now(),actor))
 return get_operations()["config"]
def create_workspace(agent_name):
 agent=_safe_agent(agent_name);config=get_operations()["config"]
 if config["global_kill_switch"]:raise PermissionError("The global execution kill switch is active.")
 path=(workspace_root/agent).resolve()
 if not _inside(workspace_root,path):raise ValueError("Workspace path escaped its isolation root.")
 path.mkdir(mode=0o700,parents=True,exist_ok=True);wid="ws_"+uuid.uuid4().hex
 with sqlite3.connect(database_path) as c:
  old=c.execute("SELECT workspace_id FROM isolated_workspaces WHERE agent_name=?",(agent,)).fetchone()
  if old:wid=old[0];c.execute("UPDATE isolated_workspaces SET path=?,status='ACTIVE',destroyed_at=NULL,destroyed_by=NULL WHERE workspace_id=?",(str(path),wid))
  else:c.execute("INSERT INTO isolated_workspaces VALUES(?,?,?,?,?,?,?)",(wid,agent,str(path),utc_now(),"ACTIVE",None,None))
 return {"workspace_id":wid,"agent_name":agent,"path":str(path),"status":"ACTIVE"}
def destroy_workspace(workspace_id,actor):
 with sqlite3.connect(database_path) as c:
  row=c.execute("SELECT path FROM isolated_workspaces WHERE workspace_id=? AND status='ACTIVE'",(workspace_id,)).fetchone()
  if not row:raise KeyError("Active isolated workspace not found.")
  path=Path(row[0]).resolve()
  if not _inside(workspace_root,path):raise PermissionError("Workspace deletion boundary check failed.")
  if path.exists():shutil.rmtree(path)
  c.execute("UPDATE isolated_workspaces SET status='DESTROYED',destroyed_at=?,destroyed_by=? WHERE workspace_id=?",(utc_now(),actor,workspace_id))
 return {"workspace_id":workspace_id,"status":"DESTROYED","recoverable":False}
def quarantine_artifact(workspace_id,source_path):
 initialize_isolation_operations();source=Path(source_path).resolve()
 with sqlite3.connect(database_path) as c:row=c.execute("SELECT path FROM isolated_workspaces WHERE workspace_id=? AND status='ACTIVE'",(workspace_id,)).fetchone()
 if not row:raise KeyError("Active isolated workspace not found.")
 workspace=Path(row[0]).resolve()
 if not _inside(workspace,source) or not source.is_file():raise PermissionError("Artifact must be a regular file inside its isolated workspace.")
 data=source.read_bytes()
 if len(data)>10_000_000:raise ValueError("Artifact exceeds the 10 MB quarantine limit.")
 digest=hashlib.sha256(data).hexdigest();aid="art_"+uuid.uuid4().hex;target=(quarantine_root/f"{aid}.bin").resolve()
 if not _inside(quarantine_root,target):raise PermissionError("Quarantine path boundary check failed.")
 target.write_bytes(data);source.unlink()
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO quarantined_artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?)",(aid,workspace_id,source.name,digest,len(data),str(target),"QUARANTINED",None,None,utc_now(),None))
 return {"artifact_id":aid,"sha256":digest,"size_bytes":len(data),"status":"QUARANTINED"}
def scan_artifact(artifact_id,scanner):
 with sqlite3.connect(database_path) as c:
  row=c.execute("SELECT quarantine_path FROM quarantined_artifacts WHERE artifact_id=? AND status='QUARANTINED'",(artifact_id,)).fetchone()
  if not row:raise KeyError("Quarantined artifact not found.")
  result=scanner(Path(row[0]));clean=bool(result.get("clean"));status="CLEAN" if clean else "MALICIOUS";c.execute("UPDATE quarantined_artifacts SET status=?,scan_engine=?,scan_result=?,scanned_at=? WHERE artifact_id=?",(status,str(result.get("engine","unknown")),str(result.get("detail",""))[:500],utc_now(),artifact_id))
 return {"artifact_id":artifact_id,"status":status,"released":False}
def kubernetes_job_manifest(agent_name,job_id,image="greyguard-sandbox:local"):
 agent=_safe_agent(agent_name);config=get_operations()["config"]
 if config["global_kill_switch"]:raise PermissionError("The global execution kill switch is active.")
 safe_job=re.sub(r"[^a-z0-9-]","-",job_id.lower())[:40].strip("-")
 if not safe_job:raise ValueError("Kubernetes job identifier is invalid.")
 return {"apiVersion":"batch/v1","kind":"Job","metadata":{"name":f"gg-{safe_job}","namespace":"greyguard-sandbox","labels":{"greyguard-agent":agent}},"spec":{"ttlSecondsAfterFinished":60,"backoffLimit":0,"template":{"spec":{"serviceAccountName":"greyguard-sandbox-runner","automountServiceAccountToken":False,"restartPolicy":"Never","securityContext":{"runAsNonRoot":True,"runAsUser":65532,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{"name":"sandbox","image":image,"args":["python","-c","print('GreyGuard isolated job')"],"securityContext":{"allowPrivilegeEscalation":False,"readOnlyRootFilesystem":True,"capabilities":{"drop":["ALL"]}},"resources":{"limits":{"cpu":"500m","memory":"256Mi"}},"volumeMounts":[{"name":"workspace","mountPath":"/workspace"}]}],"volumes":[{"name":"workspace","emptyDir":{"sizeLimit":"32Mi"}}]}}}}
