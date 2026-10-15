# Deployment models

GreyGuard supports four commercial deployment models. This page states, for each model, where the data lives and who is responsible for what.

It describes the software as it exists today. Where a capability is not built or not verified, the page says so instead of promising it.

| | Hosted | Hybrid | Dedicated | Self-hosted |
|---|---|---|---|---|
| **Control plane runs** | GreyGuard-operated, multi-tenant | GreyGuard-operated, multi-tenant | GreyGuard-operated, single tenant | Customer infrastructure |
| **Enforcement runs** | Control plane | Customer-hosted gateway ([gateway-distribution.md](gateway-distribution.md)) | Control plane, or a customer gateway | Customer infrastructure |
| **Tenant isolation** | Org-scoped data, guarded by `tenant_guard` and the P2.6 acceptance suite | Same | A separate install and database | A separate install |
| **Licence** | Billing ([billing-and-licensing.md](billing-and-licensing.md)) | Billing | Billing | Signed licence lease |
| **Edition** | Foundation / Enterprise | Enterprise (gateways are an Enterprise feature) | Dedicated | Any, per lease |

## Hosted

- **Data boundary.** All customer data lives in GreyGuard's PostgreSQL database, scoped to the customer's org: agents, requests, evidence, policies, integrations and billing references. Card data is never stored. Payload content is redacted before storage where the product redacts it.
- **Customer responsibilities.**
  - Administrator accounts, MFA and SSO configuration.
  - Agent credentials held by the customer's agents.
  - Integration endpoints and the secrets those endpoints need, held as secret references.
  - Policy content and approvals.
- **Secrets.** Signing keys (policy, report, distribution) and the database credentials are operator-held environment secrets. Customer integration secrets are stored as references to a secret manager ([secret-management-integrations.md](secret-management-integrations.md)), not as values.
- **Backups.** `postgres_backup_ops.py` produces verified PostgreSQL backups ([production-deployment.md](production-deployment.md)). Backups are whole-install. Restoring one org alone is not supported; that org's export is the per-org copy.
- **Telemetry.** Operational metrics and traces ([observability.md](observability.md)). Product analytics must exclude prompts, secrets and payloads.
- **Upgrades and rollback.** Alembic migrations, each rehearsed in both directions against PostgreSQL before release. Rollback is a downgrade plus the previous image, after a backup.
- **Deletion.** Org export, offboarding and deletion, with a deletion certificate ([organization-lifecycle.md](organization-lifecycle.md)). Deleted rows remain in backups until those backups age out.
- **Support.** Severity definitions and escalation are listed by `GET /status/severities` and shown on the public status page (`/status`).

## Hybrid

The same as Hosted, with these differences:

- **Data boundary.** Agents call a customer-hosted gateway, which enforces signed policy bundles locally. The control plane holds policy, evidence the gateway reports, and node records.
- **Bundle contents.** Bundles carry permissions, emergency controls and the names of revoked agents. They do not carry evidence or other customers' data.
- **Customer responsibilities.**
  - Running the gateway.
  - Storing its node credential in a secret store.
  - Keeping it able to refresh within its offline allowance. If it can't, it fails closed and denies everything.
- **Revocation freshness.** A revocation or emergency stop reaches a gateway at the latest within that node's offline allowance (5 minutes to 7 days; default 1 hour).
- **Not yet built.** A gateway runtime package. The SDK provides bundle verification and the local decision (`greyguard_sdk.gateway`), but the transport around it is the customer's or integrator's code today.

## Dedicated

A single-tenant install operated by GreyGuard, which isolates the customer at the database and process level.

- **Region.** Any region where the operator can run the stack; see [reliability.md](reliability.md#regional-data-placement).
- **Customer-managed keys and private connectivity.** These are **not offered**. They are not implemented or verified, and the roadmap forbids offering them before they are.

## Self-hosted

- **Data boundary.** Everything stays in the customer's environment. GreyGuard receives nothing unless the customer sends it, for example in a support bundle.
- **Customer responsibilities.** Everything the operator does in the hosted model:
  - PostgreSQL, backups and restore drills;
  - signing keys;
  - TLS;
  - upgrades;
  - monitoring;
  - capacity.
- **Licence.** A signed, install-bound lease with a grace period. When a lease lapses, new growth pauses but enforcement and evidence continue.
- **Update path.** Releases are signed (`scripts/create_release_manifest.py`, [supply-chain-security.md](supply-chain-security.md)). Upgrade by verifying the release, taking a backup, running the migrations and replacing the images.
- **Process model.** Run **exactly one backend process per data directory** (`--workers 1`, which the shipped image does). See [reliability.md](reliability.md).
