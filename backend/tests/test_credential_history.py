import json
import sqlite3

import pytest

from backend.app import database, main


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "database_path", tmp_path / "creds.db")
    monkeypatch.setattr(main, "state_path", tmp_path / "state.json")
    main.initialize_greyguard()
    return tmp_path


def _raw_events(agent_name):
    with sqlite3.connect(database.database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(
            "SELECT * FROM agent_credential_events WHERE agent_name=? ORDER BY id", (agent_name,),
        )]


def test_issuing_a_credential_records_an_issued_event(isolated):
    result = main.issue_agent_credential("cred_agent", ["read_file"], actor="adm_owner")
    history = main.get_agent_credential_history(result["agent_name"])
    assert history["total"] == 1
    assert history["events"][0]["event_type"] == "ISSUED"
    assert history["events"][0]["actor"] == "adm_owner"


def test_rotating_a_credential_records_a_rotated_event(isolated):
    main.issue_agent_credential("cred_agent", ["read_file"], actor="adm_owner")
    main.rotate_agent_credential("cred_agent", actor="adm_rotator")
    history = main.get_agent_credential_history("cred_agent")
    assert history["total"] == 2
    # Newest first.
    assert history["events"][0]["event_type"] == "ROTATED"
    assert history["events"][0]["actor"] == "adm_rotator"
    assert history["events"][1]["event_type"] == "ISSUED"


def test_revoking_a_credential_records_a_revoked_event(isolated):
    main.issue_agent_credential("cred_agent", ["read_file"], actor="adm_owner")
    main.revoke_agent_credential("cred_agent", actor="adm_security")
    history = main.get_agent_credential_history("cred_agent")
    assert history["events"][0]["event_type"] == "REVOKED"
    assert history["events"][0]["actor"] == "adm_security"


def test_default_actor_is_system_when_unspecified(isolated):
    main.issue_agent_credential("cred_agent", ["read_file"])
    history = main.get_agent_credential_history("cred_agent")
    assert history["events"][0]["actor"] == "system"


def test_history_never_contains_a_credential_or_its_hash(isolated):
    issued = main.issue_agent_credential("cred_agent", ["read_file"], actor="adm_owner")
    rotated = main.rotate_agent_credential("cred_agent", actor="adm_rotator")
    main.revoke_agent_credential("cred_agent", actor="adm_security")

    history = main.get_agent_credential_history("cred_agent")
    serialized = json.dumps(history)
    assert issued["credential"] not in serialized
    assert rotated["credential"] not in serialized
    for event in history["events"]:
        assert set(event.keys()) == {"id", "agent_name", "timestamp", "event_type", "actor"}

    # Also check the raw table directly, independent of the serializer above.
    raw = _raw_events("cred_agent")
    raw_text = json.dumps(raw)
    assert issued["credential"] not in raw_text
    assert rotated["credential"] not in raw_text
    assert "credential_hash" not in raw_text
    assert "credential_salt" not in raw_text


def test_pagination_limit_and_offset(isolated):
    main.issue_agent_credential("cred_agent", ["read_file"], actor="adm_owner")
    main.rotate_agent_credential("cred_agent", actor="adm_rotator")
    main.revoke_agent_credential("cred_agent", actor="adm_security")

    first_page = main.get_agent_credential_history("cred_agent", limit=2, offset=0)
    assert first_page["total"] == 3
    assert len(first_page["events"]) == 2
    assert [event["event_type"] for event in first_page["events"]] == ["REVOKED", "ROTATED"]

    second_page = main.get_agent_credential_history("cred_agent", limit=2, offset=2)
    assert second_page["total"] == 3
    assert len(second_page["events"]) == 1
    assert second_page["events"][0]["event_type"] == "ISSUED"


def test_limit_is_bounded_to_a_safe_range(isolated):
    main.issue_agent_credential("cred_agent", ["read_file"])
    history = main.get_agent_credential_history("cred_agent", limit=10_000, offset=-5)
    # Never raises, never applies a negative offset or an unbounded limit.
    assert history["total"] == 1
    assert len(history["events"]) == 1


def test_history_for_unknown_agent_raises(isolated):
    with pytest.raises(KeyError):
        main.get_agent_credential_history("no_such_agent")


def test_history_is_scoped_to_one_agent(isolated):
    main.issue_agent_credential("agent_one", ["read_file"], actor="adm_owner")
    main.issue_agent_credential("agent_two", ["read_file"], actor="adm_owner")
    main.rotate_agent_credential("agent_two", actor="adm_rotator")

    assert main.get_agent_credential_history("agent_one")["total"] == 1
    assert main.get_agent_credential_history("agent_two")["total"] == 2
