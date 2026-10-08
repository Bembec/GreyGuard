from pathlib import Path

import os

import pytest
from fastapi.testclient import TestClient

os.environ["GREYGUARD_ADMIN_PIN"] = (
    "greyguard-test-admin-pin"
)

from backend.app import main
from backend.app.api import app
from backend.app.tool_gateway import (
    ToolGatewayError,
    get_supported_tools,
    initialize_sandbox,
    normalize_target,
)


@pytest.fixture
def client():
    """Return an initialized GreyGuard test client."""

    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_v10_control_plane(client):
    """The public health endpoint reports core readiness."""

    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "healthy"
    assert body["version"] == "10.0"
    assert body["controlled_tools"] >= 4
    assert body["sandbox_initialized"] is True


def test_admin_endpoint_rejects_missing_pin(client):
    """Administrative data is never public."""

    response = client.get("/agents")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Administrator authentication is required."
    )


def test_admin_endpoint_rejects_wrong_pin(client):
    """An incorrect administrator PIN is refused."""

    response = client.get(
        "/agents",
        headers={
            "x-admin-pin": "incorrect-pin",
        },
    )

    assert response.status_code == 401


def test_admin_endpoint_accepts_configured_pin(client):
    """The configured administrator PIN grants access."""

    response = client.get(
        "/agents",
        headers={
            "x-admin-pin": (
                "greyguard-test-admin-pin"
            ),
        },
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_live_stream_requires_administrator(client):
    """The live security stream is admin protected."""

    response = client.get("/live-events")

    assert response.status_code == 401


def test_unified_audit_requires_administrator(client):
    """Unified evidence cannot be read anonymously."""

    response = client.get("/audit-events")

    assert response.status_code == 401


def test_controlled_tools_report_safe_boundaries(client):
    """Tool metadata confirms containment controls."""

    response = client.get("/tools")

    assert response.status_code == 200

    body = response.json()

    assert body["sandbox_only"] is True
    assert body["network_access"] is False
    assert (
        body["arbitrary_command_execution"]
        is False
    )
    assert body["absolute_paths_allowed"] is False
    assert body["path_escape_allowed"] is False


def test_supported_tools_are_explicitly_allowlisted():
    """The gateway exposes only known controlled tools."""

    tools = set(get_supported_tools())

    assert {
        "list_files",
        "read_file",
        "search_logs",
        "write_note",
    }.issubset(tools)


def test_sandbox_initializes_successfully():
    """Safe sandbox resources can be initialized."""

    result = initialize_sandbox()

    assert "sandbox_root" in result
    assert Path(result["sandbox_root"]).exists()


def test_path_traversal_is_blocked():
    """A target cannot escape the GreyGuard sandbox."""

    with pytest.raises(
        ToolGatewayError,
        match="escapes",
    ):
        normalize_target("../README.md")


def test_absolute_path_is_blocked():
    """Absolute filesystem paths are prohibited."""

    with pytest.raises(ToolGatewayError):
        normalize_target(
            "C:/Windows/System32/config/SAM"
        )


def test_risk_levels_progress_to_critical():
    """Risk classification has safe outer bounds."""

    assert main.get_risk_level(0) == "LOW"
    assert (
        main.get_risk_level(
            main.max_risk_score
        )
        == "CRITICAL"
    )


def test_unknown_action_defaults_to_block():
    """Unknown capabilities never receive permission."""

    assert (
        main.permissions.get(
            "unknown_action",
            "BLOCK",
        )
        == "BLOCK"
    )


def test_setup_status_is_public_and_structurally_valid(client):
    response = client.get("/auth/setup-status")
    assert response.status_code == 200
    assert isinstance(response.json()["needs_setup"], bool)


def test_setup_rejects_when_an_administrator_already_exists(client):
    # This runs against the shared dev database (not isolated), so don't assume its starting
    # state - admin_auth.setup_first_administrator's own fresh-install logic is covered in
    # isolation by test_admin_auth.py; this just confirms the route wiring is deterministic
    # regardless of whether an administrator already existed before this test ran.
    if client.get("/auth/setup-status").json()["needs_setup"]:
        first = client.post("/auth/setup", json={
            "email": "setup-wiring-check@example.com",
            "display_name": "Setup Wiring Check",
            "password": "SecureSetup!12345",
        })
        assert first.status_code == 201
    response = client.post("/auth/setup", json={
        "email": "second-setup-attempt@example.com",
        "display_name": "Second Attempt",
        "password": "SecureSetup!12345",
    })
    assert response.status_code == 409
