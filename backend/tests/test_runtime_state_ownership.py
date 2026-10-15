"""Agent runtime state lives in the database, so every server process sees the same state.

Before, it was per-process: with the image's `--workers 2`, an agent suspended by one worker was
still allowed by the other, whose next save wrote the suspension back to ACTIVE."""
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app import database, main


@pytest.fixture()
def shared(tmp_path, monkeypatch):
    monkeypatch.setenv("GREYGUARD_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(database, "database_path", tmp_path / "greyguard.db")
    monkeypatch.setattr(main, "state_path", tmp_path / "state.json")
    main.initialize_greyguard()
    main.issue_agent_credential("shared_agent", ["read_file"])
    return tmp_path


def other_process(data_dir, code):
    script = textwrap.dedent(f"""
        from pathlib import Path
        from backend.app import database, main
        database.database_path = Path({str(data_dir / 'greyguard.db')!r})
        main.state_path = Path({str(data_dir / 'state.json')!r})
        main.initialize_greyguard()
    """) + textwrap.dedent(code)
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True).stdout.strip()


def test_a_suspension_in_one_process_is_enforced_by_another(shared):
    # Another process (another worker or replica) pushes the agent into suspension...
    assert other_process(shared, """
        for _ in range(10):
            main.submit_tool_request("shared_agent", "delete_file", "x")
        print(main.get_agent_state("shared_agent")["agent_status"])
    """) == "SUSPENDED"
    # ...and this process, which loaded the agent before that happened, refuses it.
    assert main.submit_tool_request("shared_agent", "read_file", "notes.txt")["policy_decision"] == "REFUSED"
    # A reset in this process is seen by another.
    main.reset_agent("shared_agent")
    assert other_process(shared, 'print(main.get_agent_state("shared_agent")["agent_status"])') == "ACTIVE"


def test_concurrent_decisions_never_lose_an_increment(shared):
    org_id = main.agent_org_id("shared_agent")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: database.record_runtime_decision("shared_agent", org_id, 1, 1, 10_000, 10_000), range(40)))
    state = main.get_agent_state("shared_agent")
    assert state["blocked_attempts"] == 40 and state["risk_score"] == 40


def test_state_kept_in_the_old_state_file_is_imported_once_and_never_overrides(shared):
    import json
    main.state_path.write_text(json.dumps({"active_agent": "default_agent", "agents": {
        "legacy_bot": {"agent_status": "SUSPENDED", "risk_score": 90, "blocked_attempts": 3},
        "shared_agent": {"agent_status": "SUSPENDED", "risk_score": 999, "blocked_attempts": 99}}}))
    main.initialize_greyguard()
    assert main.get_agent_state("legacy_bot")["agent_status"] == "SUSPENDED"
    assert main.get_agent_state("shared_agent") == {"agent_status": "ACTIVE", "risk_score": 0, "blocked_attempts": 0}


def test_the_shipped_image_runs_several_workers():
    from pathlib import Path
    dockerfile = (Path(__file__).resolve().parents[2] / "deployment" / "backend.Dockerfile").read_text()
    assert '"--workers","2"' in dockerfile
