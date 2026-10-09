"""Immutable compliance evidence snapshots and safe export formatting."""

import csv
import hashlib
import html
import io
import json
from . import db_compat as sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .admin_auth import list_administrators
from .alerts import get_alerts
from .database import database_path, get_administrator_audit_events
from .policy_control import list_policy_versions
from . import organizations
from . import tenant_guard


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize_compliance_reports() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS compliance_reports (
                report_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                filters_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                evidence_hash TEXT NOT NULL
            )
        """)


def _within(timestamp: str | None, date_from: str | None, date_to: str | None) -> bool:
    if not timestamp:
        return True
    day = str(timestamp)[:10]
    return (not date_from or day >= date_from) and (not date_to or day <= date_to)


def _privileged_activity(date_from: str | None, date_to: str | None, org_id: str = organizations.DEFAULT_ORG_ID) -> list[dict[str, Any]]:
    tables = [
        ("policy_change_events", "timestamp", "actor", "event_type", "note", "policy_id"),
        ("secret_events", "timestamp", "actor", "event_type", "detail", "secret_id"),
        ("service_account_events", "timestamp", "actor", "event_type", "detail", "account_id"),
    ]
    activity: list[dict[str, Any]] = []
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        existing = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for table, timestamp, actor, event_type, detail, subject in tables:
            if table not in existing:
                continue
            # compliance_reports itself is not yet tenant-scoped (it also pulls from
            # audit_events/security_alerts/policy_versions, none of which are scoped either -
            # that is its own future P2.2 batch). This table-by-table check exists only so this
            # generic query never re-trips tenant_guard the moment one of these source tables
            # gets its own org_id column in an earlier batch, as service_account_events and
            # secret_events already have - defaulting to DEFAULT_ORG_ID until compliance_reports
            # gets its own batch to thread a real org_id all the way through.
            if table in tenant_guard.ORG_SCOPED_TABLES:
                query = (
                    f"SELECT {timestamp}, {actor}, {event_type}, {detail}, {subject} "
                    f"FROM {table} WHERE org_id=? ORDER BY {timestamp} DESC LIMIT 500"
                )
                rows = connection.execute(query, (org_id,)).fetchall()
            else:
                rows = connection.execute(
                    f"SELECT {timestamp}, {actor}, {event_type}, {detail}, {subject} "
                    f"FROM {table} ORDER BY {timestamp} DESC LIMIT 500"
                ).fetchall()
            for row in rows:
                if _within(row[0], date_from, date_to):
                    activity.append({
                        "timestamp": row[0], "actor": row[1], "event_type": row[2],
                        "detail": row[3], "subject_id": row[4], "source": table,
                    })
    return sorted(activity, key=lambda item: item["timestamp"], reverse=True)


def build_evidence(filters: dict[str, Any], org_id: str = organizations.DEFAULT_ORG_ID) -> dict[str, Any]:
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    severities = {str(value).upper() for value in filters.get("severities", [])}
    event_types = {str(value).upper() for value in filters.get("event_types", [])}

    events = get_administrator_audit_events(limit=500)["events"]
    events = [
        event for event in events
        if _within(event.get("timestamp"), date_from, date_to)
        and (not severities or str(event.get("severity", "")).upper() in severities)
        and (not event_types or str(event.get("event_type", "")).upper() in event_types)
    ]
    alerts = [
        alert for alert in get_alerts(limit=500)["alerts"]
        if _within(alert.get("created_at"), date_from, date_to)
        and (not severities or str(alert.get("severity", "")).upper() in severities)
    ]
    policies = [
        policy for policy in list_policy_versions()
        if _within(policy.get("created_at"), date_from, date_to)
    ]
    administrators = [
        {
            "admin_id": admin["admin_id"], "email": admin["email"],
            "display_name": admin["display_name"], "role": admin["role"],
            "status": admin["status"], "created_at": admin["created_at"],
            "last_login_at": admin["last_login_at"],
        }
        for admin in list_administrators()
    ]
    activity = _privileged_activity(date_from, date_to, org_id)
    return {
        "generated_at": utc_now(),
        "filters": filters,
        "audit_events": events,
        "security_alerts": alerts,
        "policy_versions": policies,
        "administrator_roster": administrators,
        "privileged_activity": activity,
    }


def evidence_summary(evidence: dict[str, Any]) -> dict[str, int]:
    events = evidence["audit_events"]
    alerts = evidence["security_alerts"]
    return {
        "audit_events": len(events),
        "critical_events": sum(str(item.get("severity", "")).upper() == "CRITICAL" for item in events),
        "security_alerts": len(alerts),
        "open_alerts": sum(item.get("status") not in {"RESOLVED", "DISMISSED"} for item in alerts),
        "policy_versions": len(evidence["policy_versions"]),
        "administrators": len(evidence["administrator_roster"]),
        "privileged_actions": len(evidence["privileged_activity"]),
    }


def _digest(evidence: dict[str, Any]) -> str:
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_compliance_report(title: str, filters: dict[str, Any], actor: str, org_id: str = organizations.DEFAULT_ORG_ID) -> dict[str, Any]:
    initialize_compliance_reports()
    normalized_title = str(title).strip()
    if len(normalized_title) < 3:
        raise ValueError("Compliance report title must contain at least 3 characters.")
    if filters.get("date_from") and filters.get("date_to") and filters["date_from"] > filters["date_to"]:
        raise ValueError("Report start date cannot be after the end date.")
    evidence = build_evidence(filters, org_id)
    summary = evidence_summary(evidence)
    report_id = "rpt_" + uuid.uuid4().hex
    created_at = utc_now()
    digest = _digest(evidence)
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            INSERT INTO compliance_reports (
                report_id, title, created_by, created_at, filters_json,
                summary_json, evidence_json, evidence_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report_id, normalized_title, actor, created_at,
            json.dumps(filters, separators=(",", ":")),
            json.dumps(summary, separators=(",", ":")),
            json.dumps(evidence, separators=(",", ":"), default=str), digest,
        ))
    return get_compliance_report(report_id, include_evidence=False)


def _serialize(row: sqlite3.Row, include_evidence: bool) -> dict[str, Any]:
    result = {
        "report_id": row["report_id"], "title": row["title"],
        "created_by": row["created_by"], "created_at": row["created_at"],
        "filters": json.loads(row["filters_json"]),
        "summary": json.loads(row["summary_json"]),
        "evidence_hash": row["evidence_hash"],
    }
    if include_evidence:
        result["evidence"] = json.loads(row["evidence_json"])
        result["integrity_verified"] = _digest(result["evidence"]) == row["evidence_hash"]
    return result


def list_compliance_reports() -> list[dict[str, Any]]:
    initialize_compliance_reports()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM compliance_reports ORDER BY created_at DESC"
        ).fetchall()
    return [_serialize(row, False) for row in rows]


def get_compliance_report(report_id: str, include_evidence: bool = True) -> dict[str, Any]:
    initialize_compliance_reports()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM compliance_reports WHERE report_id = ?", (report_id,)
        ).fetchone()
    if row is None:
        raise KeyError("Compliance report not found.")
    return _serialize(row, include_evidence)


def export_json(report_id: str) -> bytes:
    report = get_compliance_report(report_id, include_evidence=True)
    return json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8")


def export_csv(report_id: str) -> bytes:
    report = get_compliance_report(report_id, include_evidence=True)
    evidence = report["evidence"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "section", "timestamp", "type", "severity", "actor", "subject", "status", "summary",
    ])
    writer.writeheader()
    for event in evidence["audit_events"]:
        writer.writerow(_safe_csv_row({"section": "audit_event", "timestamp": event.get("timestamp"), "type": event.get("event_type"), "severity": event.get("severity"), "actor": event.get("agent_name"), "subject": event.get("action"), "status": event.get("outcome"), "summary": event.get("summary")}))
    for alert in evidence["security_alerts"]:
        writer.writerow(_safe_csv_row({"section": "security_alert", "timestamp": alert.get("created_at"), "type": alert.get("event_type"), "severity": alert.get("severity"), "actor": alert.get("assigned_to"), "subject": alert.get("agent_name"), "status": alert.get("status"), "summary": alert.get("summary")}))
    for activity in evidence["privileged_activity"]:
        writer.writerow(_safe_csv_row({"section": "privileged_activity", "timestamp": activity.get("timestamp"), "type": activity.get("event_type"), "actor": activity.get("actor"), "subject": activity.get("subject_id"), "summary": activity.get("detail")}))
    return output.getvalue().encode("utf-8-sig")


def _safe_csv_value(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _safe_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _safe_csv_value(value) for key, value in row.items()}


def evidence_catalog(report_id: str) -> list[dict[str, Any]]:
    evidence = get_compliance_report(report_id, include_evidence=True)["evidence"]
    return [
        {"key": "agent_security_assessment", "label": "Agent security assessment", "count": len({item.get("agent_name") for item in evidence["audit_events"] if item.get("agent_name")})},
        {"key": "risk_timeline", "label": "Risk timeline", "count": len(evidence["security_alerts"])},
        {"key": "decision_statistics", "label": "Decision statistics", "count": len(evidence["audit_events"])},
        {"key": "approval_evidence", "label": "Approval evidence", "count": sum(str(item.get("event_type", "")).upper() == "APPROVAL" for item in evidence["audit_events"])},
        {"key": "containment_evidence", "label": "Containment evidence", "count": sum("SUSPEND" in str(item.get("event_type", "")).upper() or "CONTAIN" in str(item.get("event_type", "")).upper() for item in evidence["audit_events"])},
        {"key": "authentication_evidence", "label": "Authentication evidence", "count": sum("AUTH" in str(item.get("event_type", "")).upper() for item in evidence["audit_events"])},
        {"key": "policy_version_evidence", "label": "Policy version evidence", "count": len(evidence["policy_versions"])},
    ]


def export_html(report_id: str) -> bytes:
    report = get_compliance_report(report_id, include_evidence=True)
    rows = "".join(f"<tr><th>{html.escape(item['label'])}</th><td>{item['count']}</td></tr>" for item in evidence_catalog(report_id))
    title = html.escape(report["title"]); digest = html.escape(report["evidence_hash"])
    document = f"""<!doctype html><html><head><meta charset=\"utf-8\"><title>{title}</title><style>body{{font:14px Arial;color:#172033;margin:40px}}h1{{color:#102a43}}table{{border-collapse:collapse;width:100%}}th,td{{padding:10px;border:1px solid #cbd5e1;text-align:left}}code{{word-break:break-all}}@media print{{button{{display:none}}}}</style></head><body><button onclick=\"print()\">Print report</button><h1>{title}</h1><p>Generated {html.escape(report['created_at'])} by {html.escape(report['created_by'])}</p><p>Integrity: <strong>{'VERIFIED' if report['integrity_verified'] else 'FAILED'}</strong></p><table>{rows}</table><h2>Evidence checksum</h2><code>{digest}</code></body></html>"""
    return document.encode("utf-8")


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def export_pdf(report_id: str) -> bytes:
    report = get_compliance_report(report_id, include_evidence=True)
    lines = [report["title"], f"Generated: {report['created_at']}", f"Created by: {report['created_by']}", f"Integrity: {'VERIFIED' if report['integrity_verified'] else 'FAILED'}"]
    lines.extend(f"{item['label']}: {item['count']}" for item in evidence_catalog(report_id)); lines.append(f"SHA-256: {report['evidence_hash']}")
    stream = "BT /F1 12 Tf 50 790 Td " + " ".join(f"({_pdf_escape(line)}) Tj 0 -24 Td" for line in lines) + " ET"
    objects = ["1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj", "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj", "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 842]/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>endobj", f"4 0 obj<</Length {len(stream.encode('latin-1','replace'))}>>stream\n{stream}\nendstream endobj", "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj"]
    data = bytearray(b"%PDF-1.4\n"); offsets = [0]
    for obj in objects: offsets.append(len(data)); data.extend(obj.encode("latin-1", "replace") + b"\n")
    xref = len(data); data.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer<</Size {len(objects)+1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF".encode()); return bytes(data)
