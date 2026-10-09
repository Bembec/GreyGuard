"""Per-agent workspaces, quarantine, network policy, and Kubernetes job controls."""
from __future__ import annotations
import hashlib,json,re,shutil,uuid
from . import db_compat as sqlite3
from datetime import datetime,timezone
from pathlib import Path
from .database import database_path
from .paths import data_directory
from . import organizations

backend_path=Path(__file__).resolve().parents[1];workspace_root=(data_directory()/"isolated_workspaces").resolve();quarantine_root=(data_directory()/"quarantine").resolve()
def utc_now():return datetime.now(timezone.utc).isoformat()
def initialize_isolation_operations(org_id=organizations.DEFAULT_ORG_ID):
 workspace_root.mkdir(parents=True,exist_ok=True);quarantine_root.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(database_path) as c:
  config_columns={row[1] for row in c.execute("PRAGMA table_info(isolation_operations_config)")}
  if config_columns and "org_id" not in config_columns:
   # SQLite cannot ALTER a PRIMARY KEY in place - the old PK (config_id=1 singleton) would let
   # two orgs collide on the one global row, so this rebuilds the table with a composite
   # (config_id, org_id) key, carrying the pre-existing row into the default org.
   c.execute("ALTER TABLE isolation_operations_config RENAME TO isolation_operations_config_pre_org")
  c.execute("""CREATE TABLE IF NOT EXISTS isolation_operations_config(config_id INTEGER NOT NULL CHECK(config_id=1),org_id TEXT NOT NULL DEFAULT 'org_default',global_kill_switch INTEGER NOT NULL,network_enabled INTEGER NOT NULL,destination_allowlist_json TEXT NOT NULL,dns_allowlist_json TEXT NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT NOT NULL,PRIMARY KEY(config_id,org_id))""")
  if config_columns and "org_id" not in config_columns:
   c.execute("""INSERT INTO isolation_operations_config (config_id,org_id,global_kill_switch,network_enabled,destination_allowlist_json,dns_allowlist_json,updated_at,updated_by)
     SELECT config_id,'org_default',global_kill_switch,network_enabled,destination_allowlist_json,dns_allowlist_json,updated_at,updated_by FROM isolation_operations_config_pre_org""")
   c.execute("DROP TABLE isolation_operations_config_pre_org")
  c.execute("INSERT OR IGNORE INTO isolation_operations_config (config_id,org_id,global_kill_switch,network_enabled,destination_allowlist_json,dns_allowlist_json,updated_at,updated_by) VALUES(1,?,0,0,'[]','[]',?,?)",(org_id,utc_now(),"system"))
  workspace_columns={row[1] for row in c.execute("PRAGMA table_info(isolated_workspaces)")}
  if workspace_columns and "org_id" not in workspace_columns:
   # agent_name was globally UNIQUE - two orgs would collide on an agent of the same name, both
   # in the database and (worse) on disk under the same workspace_root/<agent> path. Reshaped to
   # UNIQUE(agent_name, org_id), the same rebuild dance as the composite-key tables above.
   c.execute("ALTER TABLE isolated_workspaces RENAME TO isolated_workspaces_pre_org")
  c.execute("""CREATE TABLE IF NOT EXISTS isolated_workspaces(workspace_id TEXT PRIMARY KEY,agent_name TEXT NOT NULL COLLATE NOCASE,path TEXT NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL,destroyed_at TEXT,destroyed_by TEXT,org_id TEXT NOT NULL DEFAULT 'org_default',UNIQUE(agent_name,org_id))""")
  if workspace_columns and "org_id" not in workspace_columns:
   c.execute("""INSERT INTO isolated_workspaces (workspace_id,agent_name,path,created_at,status,destroyed_at,destroyed_by,org_id)
     SELECT workspace_id,agent_name,path,created_at,status,destroyed_at,destroyed_by,'org_default' FROM isolated_workspaces_pre_org""")
   c.execute("DROP TABLE isolated_workspaces_pre_org")
  c.execute("""CREATE TABLE IF NOT EXISTS quarantined_artifacts(artifact_id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,original_name TEXT NOT NULL,sha256 TEXT NOT NULL,size_bytes INTEGER NOT NULL,quarantine_path TEXT NOT NULL,status TEXT NOT NULL,scan_engine TEXT,scan_result TEXT,created_at TEXT NOT NULL,scanned_at TEXT,org_id TEXT NOT NULL DEFAULT 'org_default')""")
  artifact_columns={row[1] for row in c.execute("PRAGMA table_info(quarantined_artifacts)")}
  if "org_id" not in artifact_columns:c.execute("ALTER TABLE quarantined_artifacts ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
MAX_UPLOAD_BYTES=1_000_000
def _safe_agent(agent_name):
 value=str(agent_name).strip()
 if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}",value):raise ValueError("Agent name is unsafe for workspace isolation.")
 return value
def _safe_filename(filename):
 value=str(filename).strip()
 if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}",value) or value in {".",".."}:raise ValueError("Artifact filename is unsafe.")
 return value
def _inside(root,path):
 try:path.resolve().relative_to(root);return True
 except ValueError:return False
def get_operations(org_id=organizations.DEFAULT_ORG_ID):
 initialize_isolation_operations(org_id)
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row;config=dict(c.execute("SELECT * FROM isolation_operations_config WHERE config_id=1 AND org_id=?",(org_id,)).fetchone());workspaces=[dict(r) for r in c.execute("SELECT * FROM isolated_workspaces WHERE org_id=? ORDER BY created_at DESC",(org_id,))];artifacts=[dict(r) for r in c.execute("SELECT artifact_id,workspace_id,original_name,sha256,size_bytes,status,scan_engine,scan_result,created_at,scanned_at FROM quarantined_artifacts WHERE org_id=? ORDER BY created_at DESC LIMIT 100",(org_id,))]
 config["global_kill_switch"]=bool(config["global_kill_switch"]);config["network_enabled"]=bool(config["network_enabled"]);config["destination_allowlist"]=json.loads(config.pop("destination_allowlist_json"));config["dns_allowlist"]=json.loads(config.pop("dns_allowlist_json"));return {"config":config,"workspaces":workspaces,"artifacts":artifacts}
def update_operations(global_kill_switch,network_enabled,destinations,dns_names,actor,org_id=organizations.DEFAULT_ORG_ID):
 clean_dest=[]
 for item in destinations:
  if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]{1,5})?",item):raise ValueError("Destination allowlist contains an invalid host or port.")
  clean_dest.append(item.lower())
 clean_dns=[]
 for item in dns_names:
  if not re.fullmatch(r"[A-Za-z0-9.-]+",item):raise ValueError("DNS allowlist contains an invalid name.")
  clean_dns.append(item.lower())
 if network_enabled and (not clean_dest or not clean_dns):raise ValueError("Network enablement requires destination and DNS allowlists.")
 initialize_isolation_operations(org_id)
 with sqlite3.connect(database_path) as c:c.execute("UPDATE isolation_operations_config SET global_kill_switch=?,network_enabled=?,destination_allowlist_json=?,dns_allowlist_json=?,updated_at=?,updated_by=? WHERE config_id=1 AND org_id=?",(int(global_kill_switch),int(network_enabled),json.dumps(sorted(set(clean_dest))),json.dumps(sorted(set(clean_dns))),utc_now(),actor,org_id))
 return get_operations(org_id)["config"]
def create_workspace(agent_name,org_id=organizations.DEFAULT_ORG_ID):
 agent=_safe_agent(agent_name);config=get_operations(org_id)["config"]
 if config["global_kill_switch"]:raise PermissionError("The global execution kill switch is active.")
 org_root=(workspace_root/org_id).resolve();path=(org_root/agent).resolve()
 if not _inside(org_root,path):raise ValueError("Workspace path escaped its isolation root.")
 path.mkdir(mode=0o700,parents=True,exist_ok=True);wid="ws_"+uuid.uuid4().hex
 with sqlite3.connect(database_path) as c:
  old=c.execute("SELECT workspace_id FROM isolated_workspaces WHERE agent_name=? AND org_id=?",(agent,org_id)).fetchone()
  if old:wid=old[0];c.execute("UPDATE isolated_workspaces SET path=?,status='ACTIVE',destroyed_at=NULL,destroyed_by=NULL WHERE workspace_id=? AND org_id=?",(str(path),wid,org_id))
  else:c.execute("INSERT INTO isolated_workspaces (workspace_id,agent_name,path,created_at,status,destroyed_at,destroyed_by,org_id) VALUES(?,?,?,?,?,?,?,?)",(wid,agent,str(path),utc_now(),"ACTIVE",None,None,org_id))
 return {"workspace_id":wid,"agent_name":agent,"path":str(path),"status":"ACTIVE"}
def destroy_workspace(workspace_id,actor,org_id=organizations.DEFAULT_ORG_ID):
 with sqlite3.connect(database_path) as c:
  row=c.execute("SELECT path FROM isolated_workspaces WHERE workspace_id=? AND org_id=? AND status='ACTIVE'",(workspace_id,org_id)).fetchone()
  if not row:raise KeyError("Active isolated workspace not found.")
  path=Path(row[0]).resolve()
  if not _inside((workspace_root/org_id).resolve(),path):raise PermissionError("Workspace deletion boundary check failed.")
  if path.exists():shutil.rmtree(path)
  c.execute("UPDATE isolated_workspaces SET status='DESTROYED',destroyed_at=?,destroyed_by=? WHERE workspace_id=? AND org_id=?",(utc_now(),actor,workspace_id,org_id))
 return {"workspace_id":workspace_id,"status":"DESTROYED","recoverable":False}
def quarantine_artifact(workspace_id,source_path,org_id=organizations.DEFAULT_ORG_ID):
 initialize_isolation_operations(org_id);source=Path(source_path).resolve()
 with sqlite3.connect(database_path) as c:row=c.execute("SELECT path FROM isolated_workspaces WHERE workspace_id=? AND org_id=? AND status='ACTIVE'",(workspace_id,org_id)).fetchone()
 if not row:raise KeyError("Active isolated workspace not found.")
 workspace=Path(row[0]).resolve()
 if not _inside(workspace,source) or not source.is_file():raise PermissionError("Artifact must be a regular file inside its isolated workspace.")
 data=source.read_bytes()
 if len(data)>10_000_000:raise ValueError("Artifact exceeds the 10 MB quarantine limit.")
 digest=hashlib.sha256(data).hexdigest();aid="art_"+uuid.uuid4().hex;target=(quarantine_root/f"{aid}.bin").resolve()
 if not _inside(quarantine_root,target):raise PermissionError("Quarantine path boundary check failed.")
 target.write_bytes(data);source.unlink()
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO quarantined_artifacts (artifact_id,workspace_id,original_name,sha256,size_bytes,quarantine_path,status,scan_engine,scan_result,created_at,scanned_at,org_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(aid,workspace_id,source.name,digest,len(data),str(target),"QUARANTINED",None,None,utc_now(),None,org_id))
 return {"artifact_id":aid,"sha256":digest,"size_bytes":len(data),"status":"QUARANTINED"}
def write_and_quarantine_artifact(workspace_id,filename,content,org_id=organizations.DEFAULT_ORG_ID):
 """Write admin-supplied bytes into the agent's isolated workspace and immediately quarantine
 them, never opening, parsing, executing, or rendering the content at any point - it is treated
 as an opaque byte string from upload through to the scanner adapter."""
 initialize_isolation_operations(org_id);safe_name=_safe_filename(filename)
 if len(content)>MAX_UPLOAD_BYTES:raise ValueError(f"Artifact exceeds the {MAX_UPLOAD_BYTES} byte upload limit.")
 with sqlite3.connect(database_path) as c:row=c.execute("SELECT path FROM isolated_workspaces WHERE workspace_id=? AND org_id=? AND status='ACTIVE'",(workspace_id,org_id)).fetchone()
 if not row:raise KeyError("Active isolated workspace not found.")
 workspace=Path(row[0]).resolve();target=(workspace/safe_name).resolve()
 if not _inside(workspace,target):raise PermissionError("Artifact path escaped its isolated workspace.")
 target.write_bytes(content)
 return quarantine_artifact(workspace_id,target,org_id)
def scan_artifact(artifact_id,scanner,org_id=organizations.DEFAULT_ORG_ID):
 with sqlite3.connect(database_path) as c:
  row=c.execute("SELECT quarantine_path FROM quarantined_artifacts WHERE artifact_id=? AND org_id=? AND status='QUARANTINED'",(artifact_id,org_id)).fetchone()
  if not row:raise KeyError("Quarantined artifact not found.")
  try:
   result=scanner(Path(row[0]));clean=bool(result.get("clean"));status="CLEAN" if clean else "MALICIOUS"
   detail=str(result.get("detail",""))[:500];engine=str(result.get("engine","unknown"))
  except Exception as error:
   # A scanner that cannot be reached or times out must never be mistaken for a clean result:
   # the artifact stays blocked, and the failure itself becomes the recorded evidence.
   status="SCAN_FAILED";detail=str(error)[:500];engine="unknown"
  c.execute("UPDATE quarantined_artifacts SET status=?,scan_engine=?,scan_result=?,scanned_at=? WHERE artifact_id=? AND org_id=?",(status,engine,detail,utc_now(),artifact_id,org_id))
 return {"artifact_id":artifact_id,"status":status,"released":False}
def kubernetes_job_manifest(agent_name,job_id,image="greyguard-sandbox:local",org_id=organizations.DEFAULT_ORG_ID):
 agent=_safe_agent(agent_name);config=get_operations(org_id)["config"]
 if config["global_kill_switch"]:raise PermissionError("The global execution kill switch is active.")
 safe_job=re.sub(r"[^a-z0-9-]","-",job_id.lower())[:40].strip("-")
 if not safe_job:raise ValueError("Kubernetes job identifier is invalid.")
 return {"apiVersion":"batch/v1","kind":"Job","metadata":{"name":f"gg-{safe_job}","namespace":"greyguard-sandbox","labels":{"greyguard-agent":agent}},"spec":{"ttlSecondsAfterFinished":60,"backoffLimit":0,"template":{"spec":{"serviceAccountName":"greyguard-sandbox-runner","automountServiceAccountToken":False,"restartPolicy":"Never","securityContext":{"runAsNonRoot":True,"runAsUser":65532,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{"name":"sandbox","image":image,"args":["python","-c","print('GreyGuard isolated job')"],"securityContext":{"allowPrivilegeEscalation":False,"readOnlyRootFilesystem":True,"capabilities":{"drop":["ALL"]}},"resources":{"limits":{"cpu":"500m","memory":"256Mi"}},"volumeMounts":[{"name":"workspace","mountPath":"/workspace"}]}],"volumes":[{"name":"workspace","emptyDir":{"sizeLimit":"32Mi"}}]}}}}
