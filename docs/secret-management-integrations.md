# Secret-management integrations

GreyGuard stores provider references and lifecycle evidence, never secret values. Values are resolved just in time through the deployment's workload identity or configured environment and are returned only to the controlled server-side operation that requested them.

## Supported providers

| Provider | Reference format | Authentication |
| --- | --- | --- |
| Environment | `GREYGUARD_SERVICE_TOKEN` | Process environment |
| HashiCorp Vault | `secret/data/greyguard#api_key` | `VAULT_ADDR` plus Vault workload authentication or `VAULT_TOKEN` |
| AWS Secrets Manager | Secret ID, path, or ARN | AWS default credential chain |
| Azure Key Vault | `https://vault-name.vault.azure.net/secrets/name[/version]` | `DefaultAzureCredential` |
| Google Secret Manager | `projects/project/secrets/name/versions/latest` | Application Default Credentials |

Install optional provider clients with `python -m pip install -r backend/requirements-secrets.txt`, or install only the packages required by the deployment.

## Controls

- Provider references are validated before storage and rotation.
- Retrieval is just in time; plaintext values are not written to the GreyGuard database, API responses, or audit events.
- Access count, last-access time, rotations, revocations, and emergency actions are recorded without values.
- Rotation intervals schedule the next expected rotation.
- Platform administrators can revoke all active references or only one provider's references.
- Text and JSON responses pass through centralized secret redaction. Streaming and binary responses bypass transformation to preserve their integrity.
- Optional SDK availability is reported without exposing provider credentials.

## Production guidance

Prefer workload identity over static credentials. Grant GreyGuard read access only to the exact secrets it requires. Rotate provider credentials independently from reference rotation, and alert on overdue `next_rotation_at` timestamps and emergency-revocation events.

Do not put real values in `.env.production`, source control, policy documents, screenshots, support bundles, or test fixtures. The `.env.production.example` file should contain names and placeholders only.
