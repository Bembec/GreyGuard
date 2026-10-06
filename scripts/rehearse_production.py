"""Build, start, probe, evidence, and remove an isolated production stack."""

import json
import secrets
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.production"
COMPOSE = ROOT / "docker-compose.production.yml"
PROJECT = "greyguard-clean-rehearsal"


def compose(*arguments: str, check: bool = True):
    return subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(ENV_FILE),
            "--project-name",
            PROJECT,
            "-f",
            str(COMPOSE),
            *arguments,
        ],
        cwd=ROOT,
        check=check,
    )


def probe(url: str, attempts: int = 60) -> int:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return response.status
        except OSError:
            time.sleep(2)
    raise RuntimeError(f"Production rehearsal probe failed: {url}")


def main():
    if ENV_FILE.exists():
        raise SystemExit(
            "Refusing to overwrite .env.production; move it aside before an isolated rehearsal."
        )
    ENV_FILE.write_text(
        "\n".join(
            [
                "GREYGUARD_ENV=production",
                "GREYGUARD_BOOTSTRAP_EMAIL=rehearsal@example.com",
                f"GREYGUARD_BOOTSTRAP_PASSWORD={secrets.token_urlsafe(32)}",
                "GREYGUARD_BOOTSTRAP_NAME=Rehearsal Administrator",
                "GREYGUARD_ALLOWED_ORIGINS=http://localhost:8080",
                "GREYGUARD_TRUSTED_HOSTS=localhost,127.0.0.1",
                "GREYGUARD_DATA_DIR=/app/backend/data",
                "GREYGUARD_BEHIND_PROXY=true",
                f"GREYGUARD_POSTGRES_PASSWORD={secrets.token_urlsafe(32)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    evidence = {"started_at": datetime.now(timezone.utc).isoformat(), "project": PROJECT}
    try:
        compose("config", "-q")
        compose("up", "--build", "-d")
        try:
            evidence["frontend_health_status"] = probe(
                "http://127.0.0.1:8080/healthz"
            )
            evidence["api_health_status"] = probe(
                "http://127.0.0.1:8080/api/health/ready"
            )
        except Exception:
            compose("ps", check=False)
            compose("logs", "--no-color", "--tail", "200", check=False)
            raise
        evidence["passed"] = True
        evidence["completed_at"] = datetime.now(timezone.utc).isoformat()
        output = ROOT / "artifacts" / "production-rehearsal.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(output)
    finally:
        compose("down", "--volumes", "--remove-orphans", check=False)
        ENV_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
