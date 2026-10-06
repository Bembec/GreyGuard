"""Cross-platform final release-gate evidence runner."""

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(name: str, command: list[str], cwd: Path = ROOT) -> dict:
    started = datetime.now(timezone.utc)
    result = subprocess.run(command, cwd=cwd, check=False)
    return {
        "name": name,
        "command": command,
        "return_code": result.returncode,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    checks = [
        run("backend", [sys.executable, "-m", "pytest", "backend/tests", "-q"]),
        run("api-contract", [sys.executable, "scripts/export_api_contract.py"]),
        run("sbom", [sys.executable, "scripts/generate_sbom.py"]),
        run("frontend-tests", [npm, "test", "--", "--run"], ROOT / "frontend"),
        run("frontend-build", [npm, "run", "build"], ROOT / "frontend"),
    ]
    evidence = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": all(item["return_code"] == 0 for item in checks),
        "checks": checks,
    }
    output = ROOT / "artifacts" / "release-gate.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(output)
    if not evidence["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
