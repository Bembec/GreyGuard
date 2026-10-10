"""Scheduling, signed manifests, control mapping, and governance reports."""
from __future__ import annotations
import calendar,hashlib,hmac,json,os,re,uuid
from . import db_compat as sqlite3
from datetime import datetime,timedelta,timezone
from typing import Callable
from .database import database_path,get_administrator_audit_events
from .outbound_delivery import new_claim_token,record_evidence,safe_error
from . import organizations
from . import tenant_guard

def utc_now():return datetime.now(timezone.utc).isoformat()
LEASE_SECONDS=120
CONTROL_MAPPING=(
 {"framework":"NIST CSF 2.0","control":"DE.CM-01","evidence":"Security alerts and monitored events"},
 {"framework":"NIST CSF 2.0","control":"PR.AA-05","evidence":"Authorization and least-privilege decisions"},
 {"framework":"ISO 27001:2022","control":"A.8.15","evidence":"Tamper-evident logging and administrator actions"},
 {"framework":"SOC 2","control":"CC7.2","evidence":"Security-event monitoring and evaluation"},
)
def initialize_report_governance():
 with sqlite3.connect(database_path) as c:
  c.execute("""CREATE TABLE IF NOT EXISTS report_schedules(schedule_id TEXT PRIMARY KEY,title TEXT NOT NULL,
   frequency TEXT NOT NULL,enabled INTEGER NOT NULL,next_run_at TEXT NOT NULL,created_by TEXT NOT NULL,
   created_at TEXT NOT NULL,disabled_at TEXT,claim_token TEXT,claimed_at TEXT,last_run_at TEXT,
   last_status TEXT,last_error TEXT,notify_destination_id TEXT,org_id TEXT NOT NULL DEFAULT 'org_default')""")
  c.execute("CREATE TABLE IF NOT EXISTS incident_postmortems(postmortem_id TEXT PRIMARY KEY,incident_id TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,template_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,org_id TEXT NOT NULL DEFAULT 'org_default')")
  # The CREATE TABLE above already defines every column, including org_id, so none of these
  # ALTERs ever fire against a freshly created table - they exist only to upgrade a database
  # that predates this shape. Each ALTER ADD COLUMN statement is checked by tenant_guard like
  # any other query; only the org_id-adding one below can ever mention the literal "org_id" a
  # scoped table requires, so a database old enough to still be missing one of the other five
  # columns would need its schema caught up by hand before upgrading straight to org-scoped
  # code - not a realistic path for this codebase's own dev/test databases, which have carried
  # these columns since they were introduced.
  columns={row[1] for row in c.execute("PRAGMA table_info(report_schedules)")}
  for name,definition in (("claim_token","TEXT"),("claimed_at","TEXT"),("last_run_at","TEXT"),
                           ("last_status","TEXT"),("last_error","TEXT"),("notify_destination_id","TEXT"),
                           ("org_id","TEXT NOT NULL DEFAULT 'org_default'")):
   if name not in columns:c.execute(f"ALTER TABLE report_schedules ADD COLUMN {name} {definition}")
  postmortem_columns={row[1] for row in c.execute("PRAGMA table_info(incident_postmortems)")}
  if "org_id" not in postmortem_columns:c.execute("ALTER TABLE incident_postmortems ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
def _schedule_row(row):
 return {"schedule_id":row["schedule_id"],"title":row["title"],"frequency":row["frequency"],"enabled":bool(row["enabled"]),"next_run_at":row["next_run_at"],
         "created_by":row["created_by"],"created_at":row["created_at"],"disabled_at":row["disabled_at"],"last_run_at":row["last_run_at"],
         "last_status":row["last_status"],"last_error":row["last_error"],"notify_destination_id":row["notify_destination_id"]}
def list_schedules(org_id=organizations.DEFAULT_ORG_ID):
 initialize_report_governance()
 with sqlite3.connect(database_path) as c:
  c.row_factory=sqlite3.Row
  return [_schedule_row(row) for row in c.execute("SELECT * FROM report_schedules WHERE org_id=? ORDER BY created_at DESC",(org_id,))]
def create_schedule(title,frequency,next_run_at,actor,notify_destination_id=None,org_id=organizations.DEFAULT_ORG_ID):
 title=str(title).strip();frequency=str(frequency).upper();next_run_at=str(next_run_at).strip()
 if len(title)<3:raise ValueError("Schedule title must contain at least 3 characters.")
 if frequency not in {"DAILY","WEEKLY","MONTHLY"}:raise ValueError("Frequency must be DAILY, WEEKLY, or MONTHLY.")
 try:datetime.fromisoformat(next_run_at.replace("Z","+00:00"))
 except ValueError as error:raise ValueError("Next run time must be an ISO-8601 timestamp.") from error
 sid="sch_"+uuid.uuid4().hex;now=utc_now()
 initialize_report_governance()
 with sqlite3.connect(database_path) as c:
  c.execute("""INSERT INTO report_schedules(schedule_id,title,frequency,enabled,next_run_at,created_by,created_at,
   disabled_at,notify_destination_id,org_id) VALUES(?,?,?,?,?,?,?,?,?,?)""",
   (sid,title,frequency,1,next_run_at,actor,now,None,notify_destination_id,org_id))
 return next(item for item in list_schedules(org_id) if item["schedule_id"]==sid)
def _next_run_after(current_iso,frequency):
 current=datetime.fromisoformat(str(current_iso).replace("Z","+00:00"))
 if frequency=="DAILY":return (current+timedelta(days=1)).isoformat()
 if frequency=="WEEKLY":return (current+timedelta(days=7)).isoformat()
 month=current.month+1;year=current.year+(1 if month>12 else 0);month=1 if month>12 else month
 day=min(current.day,calendar.monthrange(year,month)[1])
 return current.replace(year=year,month=month,day=day).isoformat()
def run_due_schedules(generator=None,exporter=None,notifier=None,limit=10,worker_id=None):
 """Generate and sign the evidence for every due, enabled schedule; optionally notify a destination.

 `generator`/`exporter` default to the real compliance-report pipeline; tests inject stubs the
 same way the outbound queues inject a stub `sender`, so this never needs network or disk access
 to verify the scheduling/claiming/evidence logic in isolation.
 """
 if generator is None or exporter is None:
  from .compliance_reports import create_compliance_report,export_json
  generator=generator or create_compliance_report;exporter=exporter or export_json
 initialize_report_governance();now=utc_now();claim_token=new_claim_token()
 stale_before=(datetime.now(timezone.utc)-timedelta(seconds=LEASE_SECONDS)).isoformat()
 with sqlite3.connect(database_path) as c:
  # This worker services every org's due schedules in one pass: the claim below is
  # intentionally cross-org (one background process, every org's queue), so it carries no
  # org_id predicate by design - each claimed row's own org_id is read afterward and passed to
  # the generator, so the per-org report itself is still correctly scoped.
  c.execute("""-- intentional cross-org claim, no org_id filter: see run_due_schedules() docstring
   UPDATE report_schedules SET claim_token=?,claimed_at=? WHERE schedule_id IN (
   SELECT schedule_id FROM report_schedules WHERE enabled=1 AND next_run_at<=?
   AND (claimed_at IS NULL OR claimed_at<=?) ORDER BY next_run_at LIMIT ?)""",
   (claim_token,now,now,stale_before,limit))
  c.row_factory=sqlite3.Row
  rows=c.execute("SELECT schedule_id,title,frequency,enabled,next_run_at,created_by,created_at,disabled_at,claim_token,claimed_at,last_run_at,last_status,last_error,notify_destination_id,org_id FROM report_schedules WHERE claim_token=?",(claim_token,)).fetchall()
 results=[]
 for row in rows:
  record_evidence("REPORT_SCHEDULE",row["schedule_id"],"ATTEMPT",org_id=row["org_id"],worker_id=worker_id)
  try:
   date_from=str(row["last_run_at"] or row["created_at"])[:10]
   report=generator(f"{row['title']} — {now[:10]}",{"date_from":date_from,"date_to":now[:10]},"system-schedule",org_id=row["org_id"])
   checksums=export_checksums(report["report_id"],{"json":exporter})
   manifest=signed_manifest(report,checksums)
   next_run=_next_run_after(row["next_run_at"],row["frequency"])
   with sqlite3.connect(database_path) as c:
    c.execute("""UPDATE report_schedules SET next_run_at=?,last_run_at=?,last_status='COMPLETED',last_error=NULL,
     claim_token=NULL,claimed_at=NULL WHERE schedule_id=? AND org_id=?""",(next_run,now,row["schedule_id"],row["org_id"]))
   record_evidence("REPORT_SCHEDULE",row["schedule_id"],"SUCCESS",org_id=row["org_id"],detail={"report_id":report["report_id"]},worker_id=worker_id)
   if notifier and row["notify_destination_id"]:
    try:notifier(row["notify_destination_id"],{"event_type":"REPORT_READY","severity":"INFO","title":f"{row['title']} is ready","summary":f"Report {report['report_id']} was generated and signed.","source_id":report["report_id"]},org_id=row["org_id"])
    except Exception as error:record_evidence("REPORT_SCHEDULE",row["schedule_id"],"NOTIFY_FAILED",org_id=row["org_id"],detail={"error":safe_error(error)},worker_id=worker_id)
   results.append({"schedule_id":row["schedule_id"],"report_id":report["report_id"],"signature":manifest["signature"]})
  except Exception as error:
   with sqlite3.connect(database_path) as c:
    c.execute("UPDATE report_schedules SET last_status='FAILED',last_error=?,claim_token=NULL,claimed_at=NULL WHERE schedule_id=? AND org_id=?",(safe_error(error),row["schedule_id"],row["org_id"]))
   record_evidence("REPORT_SCHEDULE",row["schedule_id"],"FAILURE",org_id=row["org_id"],detail={"error":safe_error(error)},worker_id=worker_id)
 return {"processed":len(rows),"results":results}
def disable_schedule(schedule_id,actor,org_id=organizations.DEFAULT_ORG_ID):
 with sqlite3.connect(database_path) as c:changed=c.execute("UPDATE report_schedules SET enabled=0,disabled_at=? WHERE schedule_id=? AND org_id=? AND enabled=1",(utc_now(),schedule_id,org_id)).rowcount
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
def retention_report(org_id=organizations.DEFAULT_ORG_ID):
 # Several of these data sets are not tenant-scoped at all yet (compliance_reports,
 # audit_events, administrator_audit_events, security_notifications - each its own future
 # P2.2 batch); quarantined_artifacts has carried org_id since batch 7. Same stopgap as
 # compliance_reports._privileged_activity(): filter only the tables that actually have the
 # column, defaulting to DEFAULT_ORG_ID, rather than crashing against tenant_guard or silently
 # counting every org's rows.
 with sqlite3.connect(database_path) as c:
  tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")};rows=[]
  for table in ("compliance_reports","audit_events","administrator_audit_events","security_notifications","quarantined_artifacts"):
   if table not in tables:continue
   if table in tenant_guard.ORG_SCOPED_TABLES:
    count=c.execute(f"SELECT COUNT(*) FROM {table} WHERE org_id=?",(org_id,)).fetchone()[0]
   else:
    count=c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
   rows.append({"data_set":table,"records":count,"retention_action":"Review configured retention before deletion"})
 return {"generated_at":utc_now(),"data_sets":rows,"automatic_deletion":False}
def administrator_action_report(limit=200,org_id=organizations.DEFAULT_ORG_ID):
 events=get_administrator_audit_events(limit=min(max(int(limit),1),500),org_id=org_id)["events"];return {"generated_at":utc_now(),"actions":events,"count":len(events)}
def create_postmortem(incident_id,title,actor,org_id=organizations.DEFAULT_ORG_ID):
 initialize_report_governance()
 incident_id=str(incident_id).strip();title=str(title).strip()
 if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}",incident_id):raise ValueError("Incident identifier is invalid.")
 if len(title)<3:raise ValueError("Postmortem title must contain at least 3 characters.")
 template={"summary":"","impact":"","timeline":[],"root_cause":"","controls_that_worked":[],"control_gaps":[],"corrective_actions":[],"evidence_references":[],"owner":"","review_date":""};pid="pm_"+uuid.uuid4().hex;now=utc_now()
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO incident_postmortems (postmortem_id,incident_id,title,status,template_json,created_by,created_at,updated_at,org_id) VALUES(?,?,?,?,?,?,?,?,?)",(pid,incident_id,title,"DRAFT",json.dumps(template),actor,now,now,org_id))
 return {"postmortem_id":pid,"incident_id":incident_id,"title":title,"status":"DRAFT","template":template,"created_by":actor,"created_at":now}
