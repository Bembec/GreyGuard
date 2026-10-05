"""Non-operational defensive simulations with no executable side effects."""
from __future__ import annotations
import json,sqlite3,uuid
from datetime import datetime,timezone
from .database import database_path

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
def utc_now():return datetime.now(timezone.utc).isoformat()
def initialize_simulations():
 with sqlite3.connect(database_path) as c:
  c.execute("CREATE TABLE IF NOT EXISTS simulation_config(config_id INTEGER PRIMARY KEY CHECK(config_id=1),enabled INTEGER NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT NOT NULL)")
  c.execute("INSERT OR IGNORE INTO simulation_config VALUES(1,0,?,?)",(utc_now(),"system"))
  c.execute("CREATE TABLE IF NOT EXISTS simulation_runs(run_id TEXT PRIMARY KEY,scenario_id TEXT NOT NULL,requested_by TEXT NOT NULL,created_at TEXT NOT NULL,result_json TEXT NOT NULL,simulated INTEGER NOT NULL CHECK(simulated=1))")
def scenario_catalog():return [{"scenario_id":row[0],"title":row[1],"attempt":row[2],"decision":row[3],"severity":row[4],"risk_added":row[5],"suspends_agent":row[6],"fictional_target":"reserved-target.example","operational":False} for row in SCENARIOS]
def simulation_status():
 initialize_simulations()
 with sqlite3.connect(database_path) as c:
  enabled=bool(c.execute("SELECT enabled FROM simulation_config WHERE config_id=1").fetchone()[0]);runs=[json.loads(r[0]) for r in c.execute("SELECT result_json FROM simulation_runs ORDER BY created_at DESC LIMIT 100")]
 return {"enabled":enabled,"simulation_only":True,"network_access":False,"production_executor_imported":False,"scenarios":scenario_catalog(),"runs":runs}
def set_enabled(enabled,actor):
 with sqlite3.connect(database_path) as c:c.execute("UPDATE simulation_config SET enabled=?,updated_at=?,updated_by=? WHERE config_id=1",(int(enabled),utc_now(),actor))
 return {"enabled":bool(enabled),"actor":actor}
def run_simulation(scenario_id,actor):
 status=simulation_status()
 if not status["enabled"]:raise PermissionError("The simulation lab is disabled.")
 scenario=next((item for item in status["scenarios"] if item["scenario_id"]==scenario_id),None)
 if not scenario:raise KeyError("Predefined simulation scenario not found.")
 run_id="simrun_"+uuid.uuid4().hex;created=utc_now();result={**scenario,"run_id":run_id,"created_at":created,"requested_by":actor,"simulated":True,"real_action_executed":False,"filesystem_side_effect":False,"process_side_effect":False,"network_side_effect":False,"alert_created":True,"evidence_preserved":True,"environment_reset":True,"recommended_response":"Keep the request blocked, suspend the synthetic agent, review evidence and validate controls.","hypothetical_impact":f"If operational, this prohibited behavior could cause {scenario['attempt'].lower()}. No real action was attempted."}
 with sqlite3.connect(database_path) as c:c.execute("INSERT INTO simulation_runs VALUES(?,?,?,?,?,1)",(run_id,scenario_id,actor,created,json.dumps(result,separators=(",",":"))))
 return result
def export_assessment(run_id):
 with sqlite3.connect(database_path) as c:row=c.execute("SELECT result_json FROM simulation_runs WHERE run_id=?",(run_id,)).fetchone()
 if not row:raise KeyError("Simulation run not found.")
 result=json.loads(row[0]);return {"title":"GreyGuard Non-Operational Defensive Assessment","simulation_banner":"SIMULATION ONLY — NO REAL ACTION","result":result}
