"""Execute and record GreyGuard's final dependency and image security gate."""

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
CVE_BLOCK = re.compile(
    r"(?P<severity>CRITICAL|HIGH)\s+(?P<cve>CVE-\d{4}-\d+).*?"
    r"Fixed version\s*:\s*(?P<fixed>[^\r\n]+)",
    re.DOTALL,
)
FIXABLE_CVE = re.compile(r"\b(?:CRITICAL|HIGH)\s+CVE-\d{4}-\d+")


def result_record(name, command, return_code, started, report=None):
    return {
        "name": name,
        "command": command,
        "return_code": return_code,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "report": str(report.relative_to(ROOT)) if report else None,
    }


def run(name: str, command: list[str], cwd: Path = ROOT, report: Path | None = None) -> dict:
    started = datetime.now(timezone.utc)
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(result.stdout + result.stderr, encoding="utf-8")
    print(f"{name}: {'passed' if result.returncode == 0 else 'FAILED'}")
    return result_record(name, command, result.returncode, started, report)


def run_scout_gate(name: str, image: str) -> dict:
    """Fail on fixable Critical/High CVEs without trusting Scout exit-code filtering."""
    started = datetime.now(timezone.utc)
    command = [
        "docker", "scout", "cves", "--only-fixed", "--only-severity",
        "critical,high", f"local://{image}",
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    output = result.stdout + result.stderr
    report = ARTIFACTS / f"{name}-fixable-scan.txt"
    report.write_text(output, encoding="utf-8")
    if result.returncode != 0:
        effective_code = result.returncode
    else:
        effective_code = 2 if FIXABLE_CVE.search(output) else 0
    print(f"{name}: {'passed' if effective_code == 0 else 'FAILED'}")
    return result_record(name, command, effective_code, started, report)


def unfixed_risks(report_text: str, image: str, now: datetime) -> list[dict]:
    risks = []
    seen = set()
    for match in CVE_BLOCK.finditer(report_text):
        if match.group("fixed").strip().lower() != "not fixed":
            continue
        cve = match.group("cve")
        if cve in seen:
            continue
        seen.add(cve)
        risks.append({
            "cve": cve,
            "severity": match.group("severity"),
            "image": image,
            "status": "temporarily-accepted-upstream-no-fix",
            "owner": "Platform Security",
            "approved_by": "GreyGuard no-fix exception policy",
            "review_due": (now + timedelta(days=30)).date().isoformat(),
            "compensating_controls": [
                "minimal production image",
                "non-root application process where supported",
                "read-only and least-privilege runtime controls",
                "monthly rebuild and vulnerability review",
            ],
        })
    return risks


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    checks = [
        run("python-dependencies", [sys.executable, "-m", "pip_audit", "-r", "backend/requirements.txt"], report=ARTIFACTS / "pip-audit.txt"),
        run("python-static-security", [sys.executable, "-m", "bandit", "-r", "backend/app", "-x", "backend/tests", "-lll"], report=ARTIFACTS / "bandit-high.txt"),
        run("frontend-dependencies", [npm, "audit", "--audit-level=high"], ROOT / "frontend", ARTIFACTS / "npm-audit.txt"),
        run("secret-scan", [sys.executable, "scripts/scan_repository_secrets.py"]),
        run("generate-sbom", [sys.executable, "scripts/generate_sbom.py"]),
        run("verify-sbom", [sys.executable, "scripts/verify_sbom.py"]),
    ]
    scout = subprocess.run(["docker", "scout", "version"], capture_output=True, check=False)
    if scout.returncode != 0:
        raise SystemExit("Docker Scout is unavailable. Update/start Docker Desktop and rerun.")

    now = datetime.now(timezone.utc)
    accepted_risks = []
    for label, image in (
        ("backend-container", "greyguard-clean-rehearsal-backend:latest"),
        ("frontend-container", "greyguard-clean-rehearsal-frontend:latest"),
    ):
        inventory_report = ARTIFACTS / f"{label}-scan.txt"
        inventory = run(
            f"{label}-inventory",
            ["docker", "scout", "cves", "--only-severity", "critical,high", f"local://{image}"],
            report=inventory_report,
        )
        checks.append(inventory)
        if inventory["return_code"] == 0:
            accepted_risks.extend(unfixed_risks(inventory_report.read_text(encoding="utf-8"), image, now))
            checks.append(run_scout_gate(label, image))

    evidence = {
        "generated_at": now.isoformat(),
        "passed": all(check["return_code"] == 0 for check in checks),
        "policy": "Fixable Critical/High findings fail; upstream-unfixed findings receive a 30-day review exception.",
        "checks": checks,
        "accepted_risks": accepted_risks,
    }
    output = ARTIFACTS / "final-security-review.json"
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"temporarily accepted upstream-unfixed findings: {len(accepted_risks)}")
    print(output)
    if not evidence["passed"]:
        raise SystemExit("Final security review failed. Review the artifact reports.")


if __name__ == "__main__":
    main()
