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
    isolated.process_queue(lambda *_: (_ for _ in ()).throw(RuntimeError("offline")))
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
