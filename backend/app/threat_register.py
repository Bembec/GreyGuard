"""Persistent threat and vulnerability governance register."""
from __future__ import annotations

import json
from . import db_compat as sqlite3
from datetime import date, datetime, timezone

from .database import database_path
from .threat_assessments import ASSESSMENTS
from . import organizations

THREATS = (
    "CREDENTIAL_THEFT", "CREDENTIAL_REPLAY", "TOKEN_REUSE", "SCOPE_ESCALATION",
    "CROSS_AGENT_ACCESS", "APPROVAL_BYPASS", "CONFUSED_DEPUTY",
    "PROMPT_INJECTION", "MALICIOUS_TOOL_OUTPUT", "PATH_TRAVERSAL",
    "SYMLINK_ESCAPE", "SANDBOX_ESCAPE", "SERVER_SIDE_REQUEST_FORGERY",
    "COMMAND_INJECTION", "SQL_INJECTION", "CROSS_SITE_SCRIPTING",
    "CROSS_SITE_REQUEST_FORGERY", "INSECURE_DIRECT_OBJECT_REFERENCE",
    "SENSITIVE_DATA_LEAKAGE", "AUDIT_LOG_TAMPERING", "RACE_DOUBLE_EXECUTION",
    "DENIAL_OF_SERVICE", "DEPENDENCY_COMPROMISE", "MALICIOUS_INTEGRATION_WEBHOOK",
    "EXCESSIVE_DATA_RETENTION", "MISCONFIGURED_ADMIN_CAPABILITY", "INSIDER_MISUSE",
    "UNSAFE_AUTOMATIC_RESPONSE", "KILL_SWITCH_FAILURE", "BACKUP_RECOVERY_FAILURE",
)

DEFAULTS = {
    "status": "NEEDS_REVIEW", "severity": "HIGH", "residual_risk": "HIGH",
    "asset": "GreyGuard control plane", "threat_actor": "External or insider actor",
    "attack_path": "Requires documented assessment",
    "existing_controls": ["Server-side authorization", "Audit evidence"],
    "test_evidence": [], "incident_response": "Contain, preserve evidence, investigate, and recover.",
    "owner": "Platform Security", "review_date": None,
}

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def initialize_threat_register(org_id: str = organizations.DEFAULT_ORG_ID) -> None:
    with sqlite3.connect(database_path) as connection:
        existing_columns = {row[1] for row in connection.execute("PRAGMA table_info(threat_register)")}
        if existing_columns and "org_id" not in existing_columns:
            # SQLite cannot ALTER a PRIMARY KEY in place - the old PK (threat_id alone) would
            # let two orgs collide on the same fixed threat_id, so this rebuilds the table with
            # a composite (threat_id, org_id) key, carrying every pre-existing row into the
            # default org. Mirrors universal_controls.py's initialize_universal_controls().
            connection.execute("ALTER TABLE threat_register RENAME TO threat_register_pre_org")
        connection.execute("""CREATE TABLE IF NOT EXISTS threat_register(
            threat_id TEXT NOT NULL, org_id TEXT NOT NULL DEFAULT 'org_default',
            title TEXT NOT NULL, status TEXT NOT NULL,
            severity TEXT NOT NULL, asset TEXT NOT NULL, threat_actor TEXT NOT NULL,
            attack_path TEXT NOT NULL, existing_controls_json TEXT NOT NULL,
            residual_risk TEXT NOT NULL, test_evidence_json TEXT NOT NULL,
            incident_response TEXT NOT NULL, owner TEXT NOT NULL, review_date TEXT,
            updated_at TEXT NOT NULL, updated_by TEXT NOT NULL,
            PRIMARY KEY(threat_id, org_id))""")
        if existing_columns and "org_id" not in existing_columns:
            connection.execute("""INSERT INTO threat_register
                (threat_id,org_id,title,status,severity,asset,threat_actor,attack_path,
                 existing_controls_json,residual_risk,test_evidence_json,incident_response,
                 owner,review_date,updated_at,updated_by)
                SELECT threat_id,'org_default',title,status,severity,asset,threat_actor,attack_path,
                       existing_controls_json,residual_risk,test_evidence_json,incident_response,
                       owner,review_date,updated_at,updated_by
                FROM threat_register_pre_org""")
            connection.execute("DROP TABLE threat_register_pre_org")
        connection.execute("""CREATE TABLE IF NOT EXISTS threat_register_history(
            history_id INTEGER PRIMARY KEY AUTOINCREMENT, threat_id TEXT NOT NULL,
            changed_at TEXT NOT NULL, changed_by TEXT NOT NULL, snapshot_json TEXT NOT NULL,
            org_id TEXT NOT NULL DEFAULT 'org_default')""")
        history_columns = {row[1] for row in connection.execute("PRAGMA table_info(threat_register_history)")}
        if "org_id" not in history_columns:
            connection.execute("ALTER TABLE threat_register_history ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")
        for threat_id in THREATS:
            seed = {**DEFAULTS, **ASSESSMENTS.get(threat_id, {})}
            values = (seed["severity"], seed["asset"], seed["threat_actor"], seed["attack_path"],
                      json.dumps(seed["existing_controls"]), seed["residual_risk"],
                      json.dumps(seed["test_evidence"]), seed["incident_response"])
            connection.execute(
                """INSERT OR IGNORE INTO threat_register
                   (threat_id,org_id,title,status,severity,asset,threat_actor,attack_path,
                    existing_controls_json,residual_risk,test_evidence_json,incident_response,
                    owner,review_date,updated_at,updated_by)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (threat_id, org_id, threat_id.replace("_", " ").title(), DEFAULTS["status"], *values[:6],
                 values[6], values[7], DEFAULTS["owner"], None, utc_now(), "system-seed"),
            )
            # Upgrade only untouched placeholder rows; never overwrite a reviewer's edits.
            connection.execute(
                """UPDATE threat_register SET severity=?,asset=?,threat_actor=?,attack_path=?,
                   existing_controls_json=?,residual_risk=?,test_evidence_json=?,incident_response=?,updated_at=?
                   WHERE threat_id=? AND org_id=? AND updated_by='system-seed' AND attack_path=?""",
                (*values, utc_now(), threat_id, org_id, DEFAULTS["attack_path"]),
            )

def _row(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["existing_controls"] = json.loads(item.pop("existing_controls_json"))
    item["test_evidence"] = json.loads(item.pop("test_evidence_json"))
    item["overdue"] = bool(item["review_date"] and item["review_date"] < date.today().isoformat())
    return item

def list_threats(status: str | None = None, severity: str | None = None, org_id: str = organizations.DEFAULT_ORG_ID) -> list[dict]:
    initialize_threat_register(org_id)
    query, values = "SELECT * FROM threat_register WHERE org_id=?", [org_id]
    if status:
        query += " AND status=?"; values.append(status.upper())
    if severity:
        query += " AND severity=?"; values.append(severity.upper())
    query += " ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END,title"
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [_row(row) for row in connection.execute(query, values)]

def get_threat(threat_id: str, org_id: str = organizations.DEFAULT_ORG_ID) -> dict:
    initialize_threat_register(org_id)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM threat_register WHERE threat_id=? AND org_id=?", (threat_id.upper(), org_id)).fetchone()
    if not row:
        raise KeyError("Threat record not found.")
    return _row(row)

def update_threat(threat_id: str, payload: dict, actor: str, org_id: str = organizations.DEFAULT_ORG_ID) -> dict:
    current = get_threat(threat_id, org_id)
    allowed_status = {"NEEDS_REVIEW", "OPEN", "MONITORED", "MITIGATED", "ACCEPTED"}
    allowed_risk = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    status = str(payload.get("status", "")).upper()
    severity = str(payload.get("severity", "")).upper()
    residual = str(payload.get("residual_risk", "")).upper()
    if status not in allowed_status or severity not in allowed_risk or residual not in allowed_risk:
        raise ValueError("Status, severity, or residual risk is invalid.")
    required = ("asset", "threat_actor", "attack_path", "incident_response", "owner")
    if any(len(str(payload.get(field, "")).strip()) < 3 for field in required):
        raise ValueError("Asset, actor, attack path, response, and owner are required.")
    controls = [str(value).strip() for value in payload.get("existing_controls", []) if str(value).strip()]
    evidence = [str(value).strip() for value in payload.get("test_evidence", []) if str(value).strip()]
    review_date = payload.get("review_date")
    if review_date:
        date.fromisoformat(str(review_date))
    if status in {"MITIGATED", "ACCEPTED"} and (not controls or not evidence or not review_date):
        raise ValueError("Closure requires controls, test evidence, and a review date.")
    snapshot = {**current, **payload, "changed_by": actor}
    with sqlite3.connect(database_path) as connection:
        connection.execute("INSERT INTO threat_register_history(threat_id,changed_at,changed_by,snapshot_json,org_id) VALUES(?,?,?,?,?)", (threat_id.upper(), utc_now(), actor, json.dumps(snapshot), org_id))
        connection.execute("""UPDATE threat_register SET status=?,severity=?,asset=?,threat_actor=?,attack_path=?,
            existing_controls_json=?,residual_risk=?,test_evidence_json=?,incident_response=?,owner=?,review_date=?,updated_at=?,updated_by=? WHERE threat_id=? AND org_id=?""",
            (status, severity, payload["asset"].strip(), payload["threat_actor"].strip(), payload["attack_path"].strip(),
             json.dumps(controls), residual, json.dumps(evidence), payload["incident_response"].strip(),
             payload["owner"].strip(), review_date, utc_now(), actor, threat_id.upper(), org_id))
    return get_threat(threat_id, org_id)

def threat_summary(org_id: str = organizations.DEFAULT_ORG_ID) -> dict:
    items = list_threats(org_id=org_id)
    return {
        "total": len(items), "needs_review": sum(item["status"] == "NEEDS_REVIEW" for item in items),
        "critical": sum(item["severity"] == "CRITICAL" for item in items),
        "high_residual_risk": sum(item["residual_risk"] in {"HIGH", "CRITICAL"} for item in items),
        "overdue": sum(item["overdue"] for item in items),
    }

def threat_history(threat_id: str, org_id: str = organizations.DEFAULT_ORG_ID) -> list[dict]:
    get_threat(threat_id, org_id)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT history_id,changed_at,changed_by,snapshot_json FROM threat_register_history WHERE threat_id=? AND org_id=? ORDER BY history_id DESC", (threat_id.upper(), org_id))]
