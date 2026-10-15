"""RFC 9116 security.txt (P6 decision T3): the shipped file must name the private advisory channel
from SECURITY.md, stay unexpired, and be served as text by the nginx config the image ships."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECURITY_TXT = ROOT / "frontend" / "public" / ".well-known" / "security.txt"
ADVISORY_URL = "https://github.com/Bembec/GreyGuard/security/advisories/new"
LOCATION = re.compile(r"location = /\.well-known/security\.txt \{([^}]*)\}")


def fields():
    parsed = {}
    for line in SECURITY_TXT.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            name, _, value = line.partition(": ")
            parsed.setdefault(name, []).append(value)
    return parsed


def test_contact_is_the_private_advisory_channel_named_in_the_security_policy():
    assert fields()["Contact"] == [ADVISORY_URL]
    assert "GitHub Security Advisories" in (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert all(url.startswith("https://") for url in fields()["Policy"])


def test_expires_is_present_once_in_the_future_and_within_a_year():
    """RFC 9116 requires exactly one Expires and recommends under a year. This test starts failing
    when the file lapses, which is the reminder to renew it."""
    (expires,) = fields()["Expires"]
    expiry = datetime.strptime(expires, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    assert now < expiry <= now + timedelta(days=366)


def test_only_known_rfc_9116_fields_are_used():
    known = {"Acknowledgments", "Canonical", "Contact", "Encryption", "Expires", "Hiring", "Policy", "Preferred-Languages", "CSAF"}
    assert set(fields()) <= known


def test_both_nginx_configs_serve_it_as_text_without_the_app_fallback_or_dropping_headers():
    for config in ("deployment/nginx.conf", "deployment/nginx-tls.conf"):
        match = LOCATION.search((ROOT / config).read_text(encoding="utf-8"))
        assert match, config
        block = match.group(1)
        assert "try_files $uri =404" in block and "index.html" not in block, config
        assert "charset utf-8" in block, config
        # An add_header here would discard the server-level security headers for this location.
        assert "add_header" not in block, config
    assert "deployment/nginx.conf" in (ROOT / "deployment" / "frontend.Dockerfile").read_text(encoding="utf-8")


def test_the_service_worker_never_answers_well_known_paths_with_the_app_shell():
    assert r"/^\/\.well-known\//" in (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
