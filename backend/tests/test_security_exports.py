import json

import pytest

from backend.app import security_exports


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(security_exports, "database_path", tmp_path / "exports.db")
    security_exports.initialize_security_exports()
    return security_exports


def destination(module, **overrides):
    values = {
        "name": "Primary SIEM", "destination_type": "SPLUNK",
        "endpoint": "https://siem.example.com/ingest", "enabled": True,
        "signing_key_reference": None, "minimization_profile": "STANDARD",
        "rate_limit_per_minute": 60, "max_attempts": 3, "actor": "owner",
    }
    values.update(overrides)
    return module.save_destination(**values)


def test_destinations_start_disabled_and_store_no_credentials(isolated):
    item = destination(isolated, enabled=False)
    assert item["enabled"] is False
    assert item["credentials_stored"] is False
    with pytest.raises(PermissionError, match="disabled"):
        isolated.enqueue_export(item["destination_id"], {"event_type": "AUTH"}, "owner")


def test_minimization_and_redaction_happen_before_queueing(isolated):
    item = destination(isolated, minimization_profile="MINIMAL")
    queued = isolated.enqueue_export(item["destination_id"], {
        "timestamp": "2026-10-05T00:00:00+00:00", "event_type": "AUTH",
        "severity": "HIGH", "outcome": "BLOCKED", "correlation_id": "corr_12345678",
        "password": "must-not-leave", "unnecessary": "remove-me",
    }, "owner")
    payload = json.loads(queued["payload_json"])["event"]
    assert "password" not in payload
    assert "unnecessary" not in payload
    assert payload["outcome"] == "BLOCKED"


def test_signed_webhook_uses_external_key_reference(isolated, monkeypatch):
    monkeypatch.setenv("GREYGUARD_EXPORT_SIGNING_KEY", "a-secure-test-signing-key")
    item = destination(isolated, destination_type="SIGNED_WEBHOOK", signing_key_reference="GREYGUARD_EXPORT_SIGNING_KEY")
    queued = isolated.enqueue_export(item["destination_id"], {"event_type": "POLICY"}, "owner")
    assert queued["signature"].startswith("sha256=")
    assert "a-secure-test-signing-key" not in str(queued)


def test_delivery_failure_retries_then_dead_letters(isolated):
    item = destination(isolated, max_attempts=1)
    queued = isolated.enqueue_export(item["destination_id"], {"event_type": "EXECUTION"}, "owner")
    isolated.process_queue(lambda *_, **__: (_ for _ in ()).throw(RuntimeError("offline")))
    failed = isolated.get_export(queued["export_id"])
    assert failed["status"] == "DEAD_LETTER"
    assert failed["attempts"] == 1
    assert isolated.export_summary()["counts"]["DEAD_LETTER"] == 1


@pytest.mark.parametrize("destination_type", sorted(security_exports.DESTINATION_TYPES))
def test_every_destination_has_an_adapter_payload(isolated, destination_type):
    item = destination(isolated, name=destination_type, destination_type=destination_type,
                       endpoint="tls://syslog.example.com:6514" if destination_type == "SYSLOG" else "https://security.example.com/ingest")
    queued = isolated.enqueue_export(item["destination_id"], {"event_type": "TEST", "severity": "INFO"}, "owner")
    assert json.loads(queued["payload_json"])


def test_destinations_can_share_a_name_across_organizations(isolated):
    default_item = destination(isolated, org_id="org_default")
    other_item = destination(isolated, org_id="org_other")
    assert default_item["destination_id"] != other_item["destination_id"]
    assert [d["destination_id"] for d in isolated.list_destinations("org_default")] == [default_item["destination_id"]]
    assert [d["destination_id"] for d in isolated.list_destinations("org_other")] == [other_item["destination_id"]]
    # Saving the same name again within one org still updates in place rather than duplicating.
    updated = destination(isolated, org_id="org_other", max_attempts=5)
    assert updated["destination_id"] == other_item["destination_id"]
    assert isolated.list_destinations("org_default")[0]["max_attempts"] == 3


def test_an_organization_cannot_queue_to_another_organizations_destination(isolated):
    other_item = destination(isolated, org_id="org_other")
    with pytest.raises(KeyError):
        isolated.enqueue_export(other_item["destination_id"], {"event_type": "AUTH"}, "owner", org_id="org_default")
    queued = isolated.enqueue_export(other_item["destination_id"], {"event_type": "AUTH"}, "owner", org_id="org_other")
    with pytest.raises(KeyError):
        isolated.get_export(queued["export_id"], org_id="org_default")
    assert isolated.export_summary("org_default") == {"counts": {}, "recent": [], "raw_secrets_exposed": False}
    assert isolated.export_summary("org_other")["counts"] == {"QUEUED": 1}


def test_worker_delivers_every_organizations_exports_to_their_own_destinations(isolated):
    default_item = destination(isolated, org_id="org_default", endpoint="https://default.example.com/ingest")
    other_item = destination(isolated, org_id="org_other", endpoint="https://other.example.com/ingest")
    default_export = isolated.enqueue_export(default_item["destination_id"], {"event_type": "AUTH"}, "owner", org_id="org_default")
    other_export = isolated.enqueue_export(other_item["destination_id"], {"event_type": "AUTH"}, "owner", org_id="org_other")
    sent = []
    result = isolated.process_queue(lambda endpoint, *_, idempotency_key=None: sent.append((endpoint, idempotency_key)))
    assert result == {"processed": 2}
    assert sorted(sent) == sorted([("https://default.example.com/ingest", default_export["export_id"]),
                                   ("https://other.example.com/ingest", other_export["export_id"])])
    assert isolated.get_export(default_export["export_id"], org_id="org_default")["status"] == "DELIVERED"
    assert isolated.get_export(other_export["export_id"], org_id="org_other")["status"] == "DELIVERED"
    assert isolated.list_destinations("org_other")[0]["last_success_at"]


def test_legacy_database_is_rebuilt_without_breaking_the_queue_foreign_key(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE export_destinations (
            destination_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            destination_type TEXT NOT NULL, endpoint TEXT NOT NULL, enabled INTEGER NOT NULL,
            signing_key_reference TEXT, minimization_profile TEXT NOT NULL,
            rate_limit_per_minute INTEGER NOT NULL, max_attempts INTEGER NOT NULL,
            created_at TEXT NOT NULL, created_by TEXT NOT NULL, last_success_at TEXT,
            last_failure_at TEXT, last_error TEXT)""")
        connection.execute("""CREATE TABLE export_queue (
            export_id TEXT PRIMARY KEY, destination_id TEXT NOT NULL, created_at TEXT NOT NULL,
            available_at TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL,
            event_type TEXT NOT NULL, payload_json TEXT NOT NULL, signature TEXT,
            delivered_at TEXT, last_error TEXT, claim_token TEXT, claimed_at TEXT,
            FOREIGN KEY(destination_id) REFERENCES export_destinations(destination_id))""")
        connection.execute("INSERT INTO export_destinations VALUES('dst_legacy','Primary SIEM','SPLUNK',"
                           "'https://siem.example.com/ingest',1,NULL,'STANDARD',60,3,'2026-01-01','owner',NULL,NULL,NULL)")
        connection.execute("INSERT INTO export_queue VALUES('exp_legacy','dst_legacy','2026-01-01','2026-01-01',"
                           "'QUEUED',0,'AUTH','{}',NULL,NULL,NULL,NULL,NULL)")
    monkeypatch.setattr(security_exports, "database_path", path)
    security_exports.initialize_security_exports()

    with sqlite3.connect(path) as connection:
        queue_sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='export_queue'").fetchone()[0]
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert "REFERENCES export_destinations(" in queue_sql
    assert "export_destinations_org" not in tables
    assert [d["destination_id"] for d in security_exports.list_destinations("org_default")] == ["dst_legacy"]
    assert security_exports.get_export("exp_legacy", org_id="org_default")["org_id"] == "org_default"
    other = destination(security_exports, org_id="org_other")
    assert other["destination_id"] != "dst_legacy"
