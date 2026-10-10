import pytest

from backend.app import compliance_reports


@pytest.fixture
def isolated_reports(tmp_path, monkeypatch):
    database = tmp_path / "reports.db"
    monkeypatch.setattr(compliance_reports, "database_path", database)
    monkeypatch.setattr(compliance_reports, "get_administrator_audit_events", lambda limit=500, org_id=None: {"events": [{"event_id": "e1", "timestamp": "2026-10-02T10:00:00Z", "event_type": "POLICY", "severity": "HIGH", "agent_name": "agent", "action": "send_email", "outcome": "BLOCK", "summary": "Blocked."}]})
    monkeypatch.setattr(compliance_reports, "get_alerts", lambda limit=500, org_id=None: {"alerts": [{"alert_id": "a1", "created_at": "2026-10-02T10:00:00Z", "event_type": "POLICY", "severity": "HIGH", "status": "OPEN", "summary": "Review.", "agent_name": "agent"}]})
    monkeypatch.setattr(compliance_reports, "list_policy_versions", lambda org_id: [])
    monkeypatch.setattr(compliance_reports, "list_administrators", lambda: [])
    compliance_reports.initialize_compliance_reports()
    return database


def test_report_snapshot_and_integrity(isolated_reports):
    report = compliance_reports.create_compliance_report("October evidence", {}, "admin")
    stored = compliance_reports.get_compliance_report(report["report_id"])
    assert stored["integrity_verified"] is True
    assert stored["summary"]["audit_events"] == 1
    assert len(stored["evidence_hash"]) == 64


def test_report_history_does_not_embed_evidence(isolated_reports):
    compliance_reports.create_compliance_report("Audit evidence", {}, "admin")
    history = compliance_reports.list_compliance_reports()
    assert len(history) == 1
    assert "evidence" not in history[0]


def test_date_range_is_validated(isolated_reports):
    with pytest.raises(ValueError, match="start date"):
        compliance_reports.create_compliance_report("Bad range", {"date_from": "2026-10-03", "date_to": "2026-10-01"}, "admin")


def test_json_export_contains_integrity_result(isolated_reports):
    report = compliance_reports.create_compliance_report("JSON evidence", {}, "admin")
    exported = compliance_reports.export_json(report["report_id"])
    assert b'"integrity_verified": true' in exported


def test_csv_export_has_expected_sections(isolated_reports):
    report = compliance_reports.create_compliance_report("CSV evidence", {}, "admin")
    exported = compliance_reports.export_csv(report["report_id"])
    assert b"audit_event" in exported
    assert b"security_alert" in exported


def test_printable_html_and_pdf_exports(isolated_reports):
    report = compliance_reports.create_compliance_report("Printable evidence", {}, "admin")
    assert compliance_reports.export_html(report["report_id"]).startswith(b"<!doctype html>")
    assert compliance_reports.export_pdf(report["report_id"]).startswith(b"%PDF-1.4")


def test_csv_formula_injection_is_neutralized():
    assert compliance_reports._safe_csv_value("=cmd()") == "'=cmd()"


def test_evidence_catalog_covers_required_assessments(isolated_reports):
    report = compliance_reports.create_compliance_report("Evidence catalog", {}, "admin")
    keys = {item["key"] for item in compliance_reports.evidence_catalog(report["report_id"])}
    assert {"agent_security_assessment", "risk_timeline", "approval_evidence", "containment_evidence", "authentication_evidence", "policy_version_evidence"} <= keys


def test_privileged_activity_does_not_crash_once_its_source_tables_are_tenant_scoped(isolated_reports):
    # Regression test: service_account_events and secret_events both gained an org_id column
    # in earlier P2.2 batches. _privileged_activity() queried them with no org_id predicate at
    # all, which the tenant_guard correctly refused once both tables actually existed in the
    # same database - a real crash in any deployment that had ever created a service account or
    # secret reference, not caught by the other tests here because their isolated database
    # never creates those tables.
    from backend.app import service_accounts, secret_manager
    service_accounts.database_path = isolated_reports
    secret_manager.database_path = isolated_reports
    service_accounts.initialize_service_accounts()
    service_accounts.create_service_account("Deploy Bot", "CI", ["tools:execute"], 30, "admin")
    secret_manager.initialize_secret_manager()
    secret_manager.create_secret("Demo", "ENV_VAR_NAME", "admin")
    evidence = compliance_reports.build_evidence({})
    sources = {item["source"] for item in evidence["privileged_activity"]}
    assert "service_account_events" in sources
    assert "secret_events" in sources
