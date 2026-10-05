"""Just-in-time secret provider adapters with no stored credentials or values."""

from __future__ import annotations

import os
import re


PROVIDERS = {"ENVIRONMENT", "HASHICORP_VAULT", "AWS", "AZURE", "GCP"}


def validate_reference(provider, reference):
    provider = provider.upper()
    if provider not in PROVIDERS:
        raise ValueError("Unsupported secret provider.")
    patterns = {
        "ENVIRONMENT": r"[A-Z][A-Z0-9_]{2,127}",
        "HASHICORP_VAULT": r"[A-Za-z0-9_./-]{3,250}#[A-Za-z0-9_.-]{1,100}",
        "AWS": r"[A-Za-z0-9_./+=,@-]{3,512}",
        "AZURE": r"https://[A-Za-z0-9-]+\.vault\.azure\.net/secrets/[A-Za-z0-9-]+(?:/[A-Za-z0-9]+)?",
        "GCP": r"projects/[A-Za-z0-9_-]+/secrets/[A-Za-z0-9_-]+/versions/(?:latest|[0-9]+)",
    }
    if not re.fullmatch(patterns[provider], reference):
        raise ValueError(f"Invalid {provider} secret reference format.")


def provider_status():
    statuses = []
    for provider in sorted(PROVIDERS):
        available = True
        detail = "Built in."
        try:
            if provider == "HASHICORP_VAULT":
                import hvac  # noqa: F401
                detail = "Uses VAULT_ADDR and VAULT_TOKEN or workload authentication."
            elif provider == "AWS":
                import boto3  # noqa: F401
                detail = "Uses the AWS default credential chain."
            elif provider == "AZURE":
                from azure.identity import DefaultAzureCredential  # noqa: F401
                detail = "Uses Azure DefaultAzureCredential."
            elif provider == "GCP":
                from google.cloud import secretmanager  # noqa: F401
                detail = "Uses Google Application Default Credentials."
            else:
                detail = "Reads a named process environment variable."
        except ImportError:
            available = False
            detail = "Optional provider SDK is not installed."
        statuses.append({"provider": provider, "available": available, "credentials_stored": False, "detail": detail})
    return statuses


def resolve(provider, reference):
    """Resolve one value through the provider's standard workload identity chain."""
    provider = provider.upper()
    validate_reference(provider, reference)
    if provider == "ENVIRONMENT":
        value = os.getenv(reference)
        if value is None:
            raise ValueError("Referenced environment secret is unavailable.")
        return value
    if provider == "HASHICORP_VAULT":
        try:
            import hvac
        except ImportError as error:
            raise RuntimeError("Install the optional hvac dependency to use HashiCorp Vault.") from error
        path, field = reference.rsplit("#", 1)
        client = hvac.Client(url=os.environ.get("VAULT_ADDR"), token=os.environ.get("VAULT_TOKEN"))
        response = client.secrets.kv.v2.read_secret_version(path=path)
        return response["data"]["data"][field]
    if provider == "AWS":
        try:
            import boto3
        except ImportError as error:
            raise RuntimeError("Install the optional boto3 dependency to use AWS Secrets Manager.") from error
        response = boto3.client("secretsmanager").get_secret_value(SecretId=reference)
        return response.get("SecretString") or response["SecretBinary"]
    if provider == "AZURE":
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError as error:
            raise RuntimeError("Install the optional Azure identity and Key Vault dependencies.") from error
        vault_url, tail = reference.split("/secrets/", 1)
        name, *version = tail.split("/")
        return SecretClient(vault_url=vault_url, credential=DefaultAzureCredential()).get_secret(name, version[0] if version else None).value
    if provider == "GCP":
        try:
            from google.cloud import secretmanager
        except ImportError as error:
            raise RuntimeError("Install the optional Google Secret Manager dependency.") from error
        response = secretmanager.SecretManagerServiceClient().access_secret_version(request={"name": reference})
        return response.payload.data.decode("utf-8")
    raise ValueError("Unsupported secret provider.")

