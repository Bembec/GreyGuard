import asyncio

import pytest

from backend.app import secret_manager, secret_providers


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(secret_manager, "database_path", tmp_path / "secrets.db")
    secret_manager.initialize_secret_manager()


@pytest.mark.parametrize(
    ("provider", "reference"),
    [
        ("ENVIRONMENT", "GREYGUARD_SERVICE_TOKEN"),
        ("HASHICORP_VAULT", "secret/data/greyguard#api_key"),
        ("AWS", "prod/greyguard/service-token"),
        ("AZURE", "https://greyguard.vault.azure.net/secrets/service-token"),
        ("GCP", "projects/greyguard-prod/secrets/service-token/versions/latest"),
    ],
)
def test_supported_provider_references_are_valid(provider, reference):
    secret_providers.validate_reference(provider, reference)


def test_invalid_provider_reference_is_rejected():
    with pytest.raises(ValueError, match="Invalid AZURE"):
        secret_providers.validate_reference("AZURE", "plain-text-secret")


def test_just_in_time_resolution_never_persists_value(isolated, monkeypatch):
    value = "never-store-this-secret-value"
    monkeypatch.setenv("GREYGUARD_JIT_TOKEN", value)
    item = secret_manager.create_secret(
        "JIT token", "GREYGUARD_JIT_TOKEN", "owner", rotation_interval_days=30
    )
    assert secret_manager.resolve_secret(item["secret_id"], "runtime") == value
    assert item["next_rotation_at"]
    assert value not in str(secret_manager.list_secrets())
    assert value not in str(secret_manager.secret_events())


def test_provider_status_never_reports_stored_credentials():
    statuses = secret_providers.provider_status()
    assert {item["provider"] for item in statuses} == secret_providers.PROVIDERS
    assert all(item["credentials_stored"] is False for item in statuses)


def test_emergency_revocation_can_be_provider_scoped(isolated):
    env_item = secret_manager.create_secret("Environment", "GREYGUARD_ENV_TOKEN", "owner")
    aws_item = secret_manager.create_secret("AWS", "prod/greyguard/token", "owner", "AWS")
    result = secret_manager.emergency_revoke_all("owner", "AWS")
    assert result == {"revoked": 1, "provider": "AWS", "values_exposed": False}
    assert secret_manager.get_secret(aws_item["secret_id"])["status"] == "REVOKED"
    assert secret_manager.get_secret(env_item["secret_id"])["status"] == "ACTIVE"


def test_redaction_middleware_redacts_json_but_preserves_binary(monkeypatch):
    monkeypatch.setenv("SERVICE_API_TOKEN", "abcdefgh-secret-value")

    async def run(content_type, body):
        sent = []

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", content_type)]})
            await send({"type": "http.response.body", "body": body})

        async def receive():
            return {"type": "http.request"}

        async def send(message):
            sent.append(message)

        await secret_manager.SecretRedactionMiddleware(app)({"type": "http"}, receive, send)
        return sent

    textual = asyncio.run(run(b"application/json", b'{"token":"abcdefgh-secret-value"}'))
    binary = asyncio.run(run(b"application/octet-stream", b"abcdefgh-secret-value"))
    assert b"abcdefgh-secret-value" not in textual[-1]["body"]
    assert binary[-1]["body"] == b"abcdefgh-secret-value"
