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


def test_backend_image_runs_as_a_non_root_user():
    dockerfile = (ROOT / "deployment" / "backend.Dockerfile").read_text(encoding="utf-8")
    assert "\nUSER " in dockerfile and "USER root" not in dockerfile
