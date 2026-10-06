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

