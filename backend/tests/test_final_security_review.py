from datetime import datetime, timezone

from scripts import run_final_security_review, scan_repository_secrets, verify_sbom


def test_secret_scanner_detects_supported_credentials(tmp_path):
    source = tmp_path / "unsafe.py"
    source.write_text('token = "ghp_abcdefghijklmnopqrstuvwxyz1234"\n', encoding="utf-8")  # nosecret
    findings = scan_repository_secrets.scan([source])
    assert findings and findings[0]["rule"] == "github-token"


def test_sbom_verifier_accepts_unique_cyclonedx_components():
    result = verify_sbom.verify(
        {
            "bomFormat": "CycloneDX",
            "components": [
                {"type": "library", "name": "fastapi", "version": "1", "purl": "pkg:pypi/fastapi@1"}
            ],
        }
    )
    assert result == {"passed": True, "component_count": 1, "errors": []}


def test_unfixed_container_findings_become_time_limited_risks():
    report = """x HIGH CVE-2026-12345
      Affected range : >0
      Fixed version  : not fixed
    x HIGH CVE-2026-54321
      Fixed version  : 2.0
    """
    now = datetime(2026, 10, 6, tzinfo=timezone.utc)
    risks = run_final_security_review.unfixed_risks(report, "example:latest", now)
    assert [risk["cve"] for risk in risks] == ["CVE-2026-12345"]
    assert risks[0]["review_due"] == "2026-11-05"

