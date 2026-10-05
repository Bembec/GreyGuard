"""Persistent threat and vulnerability governance register."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone

from .database import database_path

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

def initialize_threat_register() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS threat_register(
            threat_id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL,
            severity TEXT NOT NULL, asset TEXT NOT NULL, threat_actor TEXT NOT NULL,
            attack_path TEXT NOT NULL, existing_controls_json TEXT NOT NULL,
            residual_risk TEXT NOT NULL, test_evidence_json TEXT NOT NULL,
            incident_response TEXT NOT NULL, owner TEXT NOT NULL, review_date TEXT,
            updated_at TEXT NOT NULL, updated_by TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS threat_register_history(
            history_id INTEGER PRIMARY KEY AUTOINCREMENT, threat_id TEXT NOT NULL,
            changed_at TEXT NOT NULL, changed_by TEXT NOT NULL, snapshot_json TEXT NOT NULL)""")
        for threat_id in THREATS:
            connection.execute(
                """INSERT OR IGNORE INTO threat_register VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (threat_id, threat_id.replace("_", " ").title(), DEFAULTS["status"],
                 DEFAULTS["severity"], DEFAULTS["asset"], DEFAULTS["threat_actor"],
                 DEFAULTS["attack_path"], json.dumps(DEFAULTS["existing_controls"]),
                 DEFAULTS["residual_risk"], "[]", DEFAULTS["incident_response"],
                 DEFAULTS["owner"], None, utc_now(), "system-seed"),
            )

def _row(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["existing_controls"] = json.loads(item.pop("existing_controls_json"))
    item["test_evidence"] = json.loads(item.pop("test_evidence_json"))
    item["overdue"] = bool(item["review_date"] and item["review_date"] < date.today().isoformat())
    return item

def list_threats(status: str | None = None, severity: str | None = None) -> list[dict]:
    initialize_threat_register()
    query, values = "SELECT * FROM threat_register WHERE 1=1", []
    if status:
        query += " AND status=?"; values.append(status.upper())
    if severity:
        query += " AND severity=?"; values.append(severity.upper())
    query += " ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END,title"
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [_row(row) for row in connection.execute(query, values)]

def get_threat(threat_id: str) -> dict:
    initialize_threat_register()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM threat_register WHERE threat_id=?", (threat_id.upper(),)).fetchone()
    if not row:
        raise KeyError("Threat record not found.")
    return _row(row)

def update_threat(threat_id: str, payload: dict, actor: str) -> dict:
    current = get_threat(threat_id)
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
        connection.execute("INSERT INTO threat_register_history(threat_id,changed_at,changed_by,snapshot_json) VALUES(?,?,?,?)", (threat_id.upper(), utc_now(), actor, json.dumps(snapshot)))
        connection.execute("""UPDATE threat_register SET status=?,severity=?,asset=?,threat_actor=?,attack_path=?,
            existing_controls_json=?,residual_risk=?,test_evidence_json=?,incident_response=?,owner=?,review_date=?,updated_at=?,updated_by=? WHERE threat_id=?""",
            (status, severity, payload["asset"].strip(), payload["threat_actor"].strip(), payload["attack_path"].strip(),
             json.dumps(controls), residual, json.dumps(evidence), payload["incident_response"].strip(),
             payload["owner"].strip(), review_date, utc_now(), actor, threat_id.upper()))
    return get_threat(threat_id)

def threat_summary() -> dict:
    items = list_threats()
    return {
        "total": len(items), "needs_review": sum(item["status"] == "NEEDS_REVIEW" for item in items),
        "critical": sum(item["severity"] == "CRITICAL" for item in items),
        "high_residual_risk": sum(item["residual_risk"] in {"HIGH", "CRITICAL"} for item in items),
        "overdue": sum(item["overdue"] for item in items),
    }

def threat_history(threat_id: str) -> list[dict]:
    get_threat(threat_id)
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT history_id,changed_at,changed_by,snapshot_json FROM threat_register_history WHERE threat_id=? ORDER BY history_id DESC", (threat_id.upper(),))]
