"""Agent runtime state is per-process, so only one server process may own a data directory.

Reproduced before the fix with the image's former `--workers 2`: an agent suspended by one worker
was still allowed by the other, whose next save wrote the suspension back to ACTIVE."""
import subprocess
import sys
import textwrap
import time

import pytest

from backend.app import main


def test_a_second_process_on_the_same_data_directory_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "state_path", tmp_path / "state.json")
    monkeypatch.setattr(main, "_RUNTIME_STATE_LOCKS", {})
    holder = subprocess.Popen([sys.executable, "-c", textwrap.dedent(f"""
        import sys, time
        from pathlib import Path
        from backend.app import main
        main.state_path = Path({str(tmp_path / 'state.json')!r})
        main.claim_runtime_state()
        print("held", flush=True)
        time.sleep(30)
    """)], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(RuntimeError, match="exactly one backend process"):
            main.claim_runtime_state()
    finally:
        holder.kill()
        holder.wait()
    # Once the owner is gone, this process can claim it - and claiming again is a no-op.
    time.sleep(0.2)
    main.claim_runtime_state()
    main.claim_runtime_state()


def test_the_shipped_image_runs_one_worker():
    from pathlib import Path
    dockerfile = (Path(__file__).resolve().parents[2] / "deployment" / "backend.Dockerfile").read_text()
    assert '"--workers","1"' in dockerfile
