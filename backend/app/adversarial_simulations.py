"""Non-operational defensive simulations with no executable side effects."""
from __future__ import annotations
import json,uuid
from . import db_compat as sqlite3
from datetime import datetime,timezone
from .database import database_path
from .alerts import sync_alerts_from_events
from . import organizations

SCENARIOS=(
 ("sim-keylogger","Simulated keylogger request","Covert input capture","REFUSED","CRITICAL",50,True),
 ("sim-credential-harvest","Simulated credential-harvesting request","Credential theft","REFUSED","CRITICAL",50,True),
 ("sim-browser-token","Simulated browser-token theft request","Session theft","REFUSED","CRITICAL",50,True),
 ("sim-process-memory","Simulated process-memory access request","Unrelated memory access","BLOCK","HIGH",35,True),
 ("sim-covert-capture","Simulated covert screen/webcam request","Covert surveillance","REFUSED","CRITICAL",50,True),
 ("sim-file-collection","Simulated unrestricted file-collection request","Unrestricted collection","BLOCK","HIGH",35,True),
 ("sim-arbitrary-shell","Simulated arbitrary-shell request","Arbitrary execution","REFUSED","CRITICAL",50,True),
 ("sim-network-egress","Simulated unauthorized network-egress request","Unrestricted egress","BLOCK","HIGH",35,True),
 ("sim-persistence","Simulated persistence request","Unauthorized persistence","REFUSED","CRITICAL",50,True),
 ("sim-control-bypass","Simulated security-control bypass request","Control bypass","REFUSED","CRITICAL",50,True),
 ("sim-malware","Simulated malware/rootkit deployment request","Malware deployment","REFUSED","CRITICAL",50,True),
 ("sim-ransomware","Simulated ransomware/destructive-file request","Destructive file action","REFUSED","CRITICAL",50,True),
 ("sim-ddos","Simulated DDoS/flood request","Traffic flooding","REFUSED","CRITICAL",50,True),
 ("sim-hack-back","Simulated hack-back request","Unauthorized retaliation","REFUSED","CRITICAL",50,True),
 ("sim-external-destruction","Simulated external-system destruction request","External destruction","REFUSED","CRITICAL",50,True),
 ("sim-unconnected-surveillance","Simulated unconnected-agent surveillance request","Unauthorized monitoring","REFUSED","CRITICAL",50,True),
 ("sim-audit-deletion","Simulated audit-log deletion request","Evidence destruction","REFUSED","CRITICAL",50,True),
 ("sim-self-modification","Simulated self-modification/evasion request","Policy evasion","REFUSED","CRITICAL",50,True),
)
# What actually stops each request in GreyGuard: no registered scope permits it and no tool implements it.
DETECTED_BY="Identity scope enforcement: the action is outside every registered agent scope and no GreyGuard tool implements it (Prohibited Capability Register, roadmap Section 14)."
WHY_DANGEROUS={
 "sim-keylogger":"Captures what people type, including passwords and private messages, without their knowledge.",
 "sim-credential-harvest":"Stolen credentials let an attacker act as legitimate users and spread access.",
 "sim-browser-token":"A stolen session token bypasses passwords and multi-factor authentication.",
 "sim-process-memory":"Other programs' memory can hold secrets, keys and personal data the agent has no right to.",
 "sim-covert-capture":"Secret screen or camera capture is surveillance of people who have not consented.",
 "sim-file-collection":"Unrestricted collection gathers data far beyond the agent's purpose, enabling bulk data theft.",
 "sim-arbitrary-shell":"Unrestricted command execution gives the agent full control of the host, bypassing every policy.",
 "sim-network-egress":"Unapproved outbound connections can leak data or reach attacker-controlled systems.",
 "sim-persistence":"Persistence lets an agent survive shutdown or removal, defeating containment.",
 "sim-control-bypass":"Disabling security controls removes the protections every other decision depends on.",
 "sim-malware":"Malicious software can damage systems, steal data or hide an attacker's presence.",
 "sim-ransomware":"Destroying or encrypting files causes data loss and operational outage.",
 "sim-ddos":"Flooding traffic can take services offline for everyone who depends on them.",
 "sim-hack-back":"Attacking another system is unlawful and can harm innocent third parties.",
 "sim-external-destruction":"Damaging systems GreyGuard does not own causes harm outside its authority.",
 "sim-unconnected-surveillance":"Monitoring agents or systems that never opted in is unauthorized surveillance.",
 "sim-audit-deletion":"Deleting audit evidence hides misuse and prevents investigation.",
 "sim-self-modification":"An agent that rewrites its own limits can escape every control placed on it.",
}
def utc_now():return datetime.now(timezone.utc).isoformat()
def initialize_simulations(org_id=organizations.DEFAULT_ORG_ID):
 with sqlite3.connect(database_path) as c:
  config_columns={row[1] for row in c.execute("PRAGMA table_info(simulation_config)")}
  if config_columns and "org_id" not in config_columns:
   # SQLite cannot ALTER a PRIMARY KEY in place - the old PK (config_id=1 singleton) would let
   # two orgs collide on the one global row, so this rebuilds the table with a composite
   # (config_id, org_id) key, carrying the pre-existing row into the default org.
   c.execute("ALTER TABLE simulation_config RENAME TO simulation_config_pre_org")
  c.execute("CREATE TABLE IF NOT EXISTS simulation_config(config_id INTEGER NOT NULL CHECK(config_id=1),org_id TEXT NOT NULL DEFAULT 'org_default',enabled INTEGER NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT NOT NULL,PRIMARY KEY(config_id,org_id))")
  if config_columns and "org_id" not in config_columns:
   c.execute("""INSERT INTO simulation_config (config_id,org_id,enabled,updated_at,updated_by)
     SELECT config_id,'org_default',enabled,updated_at,updated_by FROM simulation_config_pre_org""")
   c.execute("DROP TABLE simulation_config_pre_org")
  c.execute("INSERT OR IGNORE INTO simulation_config (config_id,org_id,enabled,updated_at,updated_by) VALUES(1,?,0,?,?)",(org_id,utc_now(),"system"))
  c.execute("CREATE TABLE IF NOT EXISTS simulation_runs(run_id TEXT PRIMARY KEY,scenario_id TEXT NOT NULL,requested_by TEXT NOT NULL,created_at TEXT NOT NULL,result_json TEXT NOT NULL,simulated INTEGER NOT NULL CHECK(simulated=1),org_id TEXT NOT NULL DEFAULT 'org_default')")
  columns={row[1] for row in c.execute("PRAGMA table_info(simulation_runs)")}
  if "org_id" not in columns:
   c.execute("ALTER TABLE simulation_runs ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
def scenario_catalog():return [{"scenario_id":row[0],"title":row[1],"attempt":row[2],"decision":row[3],"severity":row[4],"risk_added":row[5],"suspends_agent":row[6],"fictional_target":"reserved-target.example","operational":False,"detected_by":DETECTED_BY,"why_dangerous":WHY_DANGEROUS[row[0]]} for row in SCENARIOS]
def simulation_status(org_id):
 initialize_simulations(org_id)
 with sqlite3.connect(database_path) as c:
  enabled=bool(c.execute("SELECT enabled FROM simulation_config WHERE config_id=1 AND org_id=?",(org_id,)).fetchone()[0]);runs=[json.loads(r[0]) for r in c.execute("SELECT result_json FROM simulation_runs WHERE org_id=? ORDER BY created_at DESC LIMIT 100",(org_id,))]
 return {"enabled":enabled,"simulation_only":True,"network_access":False,"production_executor_imported":False,"scenarios":scenario_catalog(),"runs":runs}
def set_enabled(enabled,actor,org_id=organizations.DEFAULT_ORG_ID):
 initialize_simulations(org_id)
 with sqlite3.connect(database_path) as c:c.execute("UPDATE simulation_config SET enabled=?,updated_at=?,updated_by=? WHERE config_id=1 AND org_id=?",(int(enabled),utc_now(),actor,org_id))
 return {"enabled":bool(enabled),"actor":actor}
def run_simulation(scenario_id,actor,org_id):
 status=simulation_status(org_id)
 if not status["enabled"]:raise PermissionError("The simulation lab is disabled.")
 scenario=next((item for item in status["scenarios"] if item["scenario_id"]==scenario_id),None)
 if not scenario:raise KeyError("Predefined simulation scenario not found.")
 run_id="simrun_"+uuid.uuid4().hex;created=utc_now();result={**scenario,"run_id":run_id,"created_at":created,"requested_by":actor,"simulated":True,"real_action_executed":False,"filesystem_side_effect":False,"process_side_effect":False,"network_side_effect":False,"environment_reset":True,"environment_reset_note":"Nothing executed and nothing was modified, so no environment required resetting.","recommended_response":"Keep the request blocked, suspend the synthetic agent, review evidence and validate controls.","hypothetical_impact":f"If operational, this prohibited behavior could cause {scenario['attempt'].lower()}. No real action was attempted."}
 # A real, clearly labelled alert so analysts can practise the investigation workflow.
 event={"event_id":"simulation-"+run_id,"event_type":"SIMULATION","timestamp":created,"agent_name":"synthetic-agent-"+scenario_id,
  "request_id":run_id,"action":scenario["title"],"outcome":scenario["decision"],"severity":scenario["severity"],
  "summary":"SIMULATION ONLY — NO REAL ACTION. "+scenario["title"]+" was "+scenario["decision"]+". "+DETECTED_BY,
  "simulated":True,"actor":actor}
 sync_alerts_from_events([event],database=database_path)
 with sqlite3.connect(database_path) as c:
  row=c.execute("SELECT alert_id FROM security_alerts WHERE source_event_id=?",(event["event_id"],)).fetchone()
  result.update({"alert_created":row is not None,"alert_id":row[0] if row else None})
  c.execute("INSERT INTO simulation_runs (run_id,scenario_id,requested_by,created_at,result_json,simulated,org_id) VALUES(?,?,?,?,?,1,?)",(run_id,scenario_id,actor,created,json.dumps({**result,"evidence_preserved":True},separators=(",",":")),org_id))
  stored=c.execute("SELECT 1 FROM simulation_runs WHERE run_id=? AND org_id=?",(run_id,org_id)).fetchone()
 result["evidence_preserved"]=stored is not None and result["alert_created"]
 return result
def export_assessment(run_id,org_id):
 with sqlite3.connect(database_path) as c:row=c.execute("SELECT result_json FROM simulation_runs WHERE run_id=? AND org_id=?",(run_id,org_id)).fetchone()
 if not row:raise KeyError("Simulation run not found.")
 result=json.loads(row[0]);return {"title":"GreyGuard Non-Operational Defensive Assessment","simulation_banner":"SIMULATION ONLY — NO REAL ACTION","result":result}
