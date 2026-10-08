"""Production containers must run without root privileges or extra capabilities."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _service_block(compose: str, name: str) -> str:
    lines = compose.splitlines()
    start = lines.index(f"  {name}:")
    block = []
    for line in lines[start + 1:]:
        if line.startswith("  ") and not line.startswith("    ") and line.strip():
            break
        block.append(line)
    return "\n".join(block)


def test_frontend_image_runs_as_the_unprivileged_nginx_user():
    dockerfile = (ROOT / "deployment" / "frontend.Dockerfile").read_text(encoding="utf-8")
    runtime_stage = dockerfile.split("FROM nginx:", 1)[1]
    assert "\nUSER nginx" in runtime_stage
    assert "apk upgrade --no-cache" in runtime_stage


def test_frontend_service_has_no_added_capabilities():
    compose = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")
    frontend = _service_block(compose, "frontend")
    assert 'cap_drop: ["ALL"]' in frontend
    assert "cap_add" not in frontend
    assert "read_only: true" in frontend


def test_frontend_writable_folders_belong_to_the_nginx_user():
    compose = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")
    frontend = _service_block(compose, "frontend")
    for folder in ("/var/cache/nginx", "/var/run"):
        assert f"{folder}:uid=101,gid=101,mode=0700" in frontend


def test_backend_image_runs_as_a_non_root_user():
    dockerfile = (ROOT / "deployment" / "backend.Dockerfile").read_text(encoding="utf-8")
    assert "\nUSER " in dockerfile and "USER root" not in dockerfile


def test_both_proxy_configurations_send_a_strict_content_security_policy():
    for name in ("nginx.conf", "nginx-tls.conf"):
        config = (ROOT / "deployment" / name).read_text(encoding="utf-8")
        assert "Content-Security-Policy" in config
        policy = config.split("Content-Security-Policy", 1)[1].split("\n", 1)[0]
        assert "script-src 'self';" in policy and "unsafe-eval" not in policy
        assert "frame-ancestors 'none'" in policy and "object-src 'none'" in policy


def _nginx_conf_actually_shipped() -> str:
    """The exact file frontend.Dockerfile bakes into the production image - not just any file
    in deployment/ that happens to be named like an nginx config."""
    dockerfile = (ROOT / "deployment" / "frontend.Dockerfile").read_text(encoding="utf-8")
    for line in dockerfile.splitlines():
        if line.strip().startswith("COPY deployment/") and "/etc/nginx/" in line:
            return line.split("COPY deployment/", 1)[1].split()[0]
    raise AssertionError("frontend.Dockerfile has no COPY of an nginx config into /etc/nginx/ - update this test.")


def test_shipped_nginx_config_never_trusts_a_client_supplied_certificate_header():
    """agent_certificate_auth.py's entire trust model depends on the proxy unconditionally
    overwriting X-SSL-Client-Verify/X-SSL-Client-Cert on every request it forwards to the
    backend - see backend/app/agent_certificate_auth.py's module docstring. This must hold for
    whichever nginx config frontend.Dockerfile actually bakes into the production image, not
    just for nginx-tls.conf in isolation: a config that never terminates mTLS (nginx.conf) must
    still force these headers to a safe, non-client-controllable value, or a client could set
    X-SSL-Client-Verify: SUCCESS itself and impersonate any registered agent once an operator
    enables GREYGUARD_TRUST_CLIENT_CERT_HEADERS."""
    shipped_name = _nginx_conf_actually_shipped()
    config = (ROOT / "deployment" / shipped_name).read_text(encoding="utf-8")
    backend_locations = [block for block in config.split("location")[1:] if "proxy_pass" in block and "backend:8000" in block]
    assert backend_locations, "No backend-proxying location block found - update this test."
    for block in backend_locations:
        assert "proxy_set_header X-SSL-Client-Verify" in block, (
            f"{shipped_name} proxies to the backend without forcing X-SSL-Client-Verify - "
            "a client-supplied value would pass straight through."
        )
        assert "proxy_set_header X-SSL-Client-Cert" in block, (
            f"{shipped_name} proxies to the backend without forcing X-SSL-Client-Cert - "
            "a client-supplied value would pass straight through."
        )
        if shipped_name == "nginx.conf":
            # This config never does mTLS, so the override must be a fixed, safe value - never
            # a client-influenced nginx variable.
            assert 'X-SSL-Client-Verify "NONE"' in block
            assert 'X-SSL-Client-Cert ""' in block
