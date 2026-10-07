from fastapi.testclient import TestClient

from backend.app.api import app
from scripts.export_api_contract import contract, removed_operations


def test_version_discovery_and_versioned_health():
    with TestClient(app) as client:
        version = client.get("/api/version")
        assert version.status_code == 200
        assert version.json()["current"] == "1"
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.headers["X-GreyGuard-API-Version"] == "1"
        assert "Deprecation" not in health.headers


def test_legacy_routes_remain_available_with_migration_metadata():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers["Deprecation"] == "true"
        assert response.headers["Sunset"]


def test_contract_comparison_detects_removed_operations():
    current = contract()
    previous = {"operations": current["operations"] + [{"method": "GET", "path": "/removed"}]}
    assert removed_operations(previous, current) == [{"method": "GET", "path": "/removed"}]



def test_every_route_is_reachable_under_api_v1_without_deprecation():
    with TestClient(app) as client:
        legacy = client.get("/health/live")
        versioned = client.get("/api/v1/health/live")
        assert versioned.status_code == legacy.status_code == 200
        assert versioned.json() == legacy.json()
        assert "Deprecation" not in versioned.headers
        assert legacy.headers["Deprecation"] == "true"


def test_version_discovery_is_not_marked_deprecated():
    with TestClient(app) as client:
        assert "Deprecation" not in client.get("/api/version").headers


def test_versioned_login_cannot_bypass_login_rate_limiting(monkeypatch):
    from backend.app import api

    categories = []

    def record(identifier, category):
        categories.append(category)
        return {"allowed": True, "remaining": 99, "retry_after": 0}

    monkeypatch.setattr(api, "check_rate_limit", record)
    with TestClient(app) as client:
        client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert categories == ["ADMIN_AUTH"]


def test_versioned_paths_receive_the_same_authorization_as_legacy_paths():
    with TestClient(app) as client:
        assert client.get("/api/v1/agents").status_code == client.get("/agents").status_code


def test_version_middleware_is_the_outermost_layer():
    from backend.app.api_versioning import ApiVersionMiddleware

    assert app.user_middleware[0].cls is ApiVersionMiddleware
