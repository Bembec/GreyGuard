"""Scheduling, signed manifests, control mapping, and governance reports."""
from __future__ import annotations
import hashlib,hmac,json,os,re,uuid
from . import db_compat as sqlite3
from datetime import datetime,timezone
from typing import Callable
from .database import database_path,get_administrator_audit_events

def utc_now():return datetime.now(timezone.utc).isoformat()
CONTROL_MAPPING=(
 {"framework":"NIST CSF 2.0","control":"DE.CM-01","evidence":"Security alerts and monitored events"},
 {"framework":"NIST CSF 2.0","control":"PR.AA-05","evidence":"Authorization and least-privilege decisions"},
 {"framework":"ISO 27001:2022","control":"A.8.15","evidence":"Tamper-evident logging and administrator actions"},
 {"framework":"SOC 2","control":"CC7.2","evidence":"Security-event monitoring and evaluation"},
)
def initialize_report_governance():
 with sqlite3.connect(database_path) as c:
  c.execute("CREATE TABLE IF NOT EXISTS report_schedules(schedule_id TEXT PRIMARY KEY,title TEXT NOT NULL,frequency TEXT NOT NULL,enabled INTEGER NOT NULL,next_run_at TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,disabled_at TEXT)")
  c.execute("CREATE TABLE IF NOT EXISTS incident_postmortems(postmortem_id TEXT PRIMARY KEY,incident_id TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,template_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)")
def _schedule_row(row):return {"schedule_id":row[0],"title":row[1],"frequency":row[2],"enabled":bool(row[3]),"next_run_at":row[4],"created_by":row[5],"created_at":row[6],"disabled_at":row[7]}
def list_schedules():
 initialize_report_governance()
 with sqlite3.connect(database_path) as c:return [_schedule_row(row) for row in c.execute("SELECT * FROM report_schedules ORDER BY created_at DESC")]
def create_schedule(title,frequency,next_run_at,actor):
 title=str(title).strip();frequency=str(frequency).upper();next_run_at=str(next_run_at).strip()
 if len(title)<3:raise ValueError("Schedule title must contain at least 3 characters.")
 if frequency not in {"DAILY","WEEKLY","MONTHLY"}:raise ValueError("Frequency must be DAILY, WEEKLY, or MONTHLY.")
 try:datetime.fromisoformat(next_run_at.replace("Z","+00:00"))
 except ValueError as error:raise ValueError("Next run time must be an ISO-8601 timestamp.") from error
 sid="sch_"+uuid.uuid4().hex;now=utc_now()
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO report_schedules VALUES(?,?,?,?,?,?,?,?)",(sid,title,frequency,1,next_run_at,actor,now,None))
 return next(item for item in list_schedules() if item["schedule_id"]==sid)
def disable_schedule(schedule_id,actor):
 with sqlite3.connect(database_path) as c:changed=c.execute("UPDATE report_schedules SET enabled=0,disabled_at=? WHERE schedule_id=? AND enabled=1",(utc_now(),schedule_id)).rowcount
 if not changed:raise KeyError("Active report schedule not found.")
 return {"schedule_id":schedule_id,"enabled":False,"disabled_by":actor}
def export_checksums(report_id,exporters:dict[str,Callable[[str],bytes]]):return {name:hashlib.sha256(exporter(report_id)).hexdigest() for name,exporter in exporters.items()}
def signed_manifest(report,checksums,signing_key=None):
 key=signing_key or os.getenv("GREYGUARD_REPORT_SIGNING_KEY","")
 if len(key)<32:raise RuntimeError("GREYGUARD_REPORT_SIGNING_KEY must contain at least 32 characters.")
 body={"report_id":report["report_id"],"evidence_hash":report["evidence_hash"],"exports":checksums,"issued_at":utc_now(),"algorithm":"HMAC-SHA256"};canonical=json.dumps(body,sort_keys=True,separators=(",",":"));body["signature"]=hmac.new(key.encode(),canonical.encode(),hashlib.sha256).hexdigest();return body
def verify_manifest(manifest,signing_key):
 supplied=str(manifest.get("signature",""));body={k:v for k,v in manifest.items() if k!="signature"};canonical=json.dumps(body,sort_keys=True,separators=(",",":"));expected=hmac.new(signing_key.encode(),canonical.encode(),hashlib.sha256).hexdigest();return hmac.compare_digest(supplied,expected)
def compliance_mapping():return list(CONTROL_MAPPING)
def retention_report():
 with sqlite3.connect(database_path) as c:
  tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")};rows=[]
  for table in ("compliance_reports","audit_events","administrator_audit_events","security_notifications","quarantined_artifacts"):
   if table in tables:rows.append({"data_set":table,"records":c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],"retention_action":"Review configured retention before deletion"})
 return {"generated_at":utc_now(),"data_sets":rows,"automatic_deletion":False}
def administrator_action_report(limit=200):
 events=get_administrator_audit_events(limit=min(max(int(limit),1),500))["events"];return {"generated_at":utc_now(),"actions":events,"count":len(events)}
def create_postmortem(incident_id,title,actor):
 incident_id=str(incident_id).strip();title=str(title).strip()
 if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}",incident_id):raise ValueError("Incident identifier is invalid.")
 if len(title)<3:raise ValueError("Postmortem title must contain at least 3 characters.")
 template={"summary":"","impact":"","timeline":[],"root_cause":"","controls_that_worked":[],"control_gaps":[],"corrective_actions":[],"evidence_references":[],"owner":"","review_date":""};pid="pm_"+uuid.uuid4().hex;now=utc_now()
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO incident_postmortems VALUES(?,?,?,?,?,?,?,?)",(pid,incident_id,title,"DRAFT",json.dumps(template),actor,now,now))
 return {"postmortem_id":pid,"incident_id":incident_id,"title":title,"status":"DRAFT","template":template,"created_by":actor,"created_at":now}
