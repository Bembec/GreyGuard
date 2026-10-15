# Trust Center source register

Every statement in the Trust Center source pages, the evidence it rests on, who owns it and when it was last checked against that evidence. `backend/tests/test_trust_center.py` keeps this register and the pages in step: every ID used on a page is listed here, every ID listed here is used on a page, and every cited path exists.

**Owners:** *Engineering* keeps a statement true to the code. *Project owner* holds the business or legal decision behind it.

**Review rule:** re-check a statement whenever its evidence changes, and in any case before publication (P7) and at every release.

| ID | Statement | Evidence | Owner | Last reviewed |
|---|---|---|---|---|
| TC-ARCH-1 | Production runs three containers (frontend, backend, PostgreSQL) on one host | `docker-compose.production.yml`, `docs/reliability.md` | Engineering | 2026-10-15 |
| TC-ARCH-2 | The production containers run as non-root users with all capabilities dropped and a read-only root filesystem | `docker-compose.production.yml`, `deployment/frontend.Dockerfile`, `deployment/backend.Dockerfile`, `docs/final-security-review.md` | Engineering | 2026-10-15 |
| TC-ARCH-3 | The backend has no published port and sits on an internal-only network reachable only by the frontend | `docker-compose.production.yml`, `docs/agent-certificate-authentication.md` | Engineering | 2026-10-15 |
| TC-ARCH-4 | PostgreSQL is the database of record; production refuses to start without it | `docs/production-deployment.md`, `backend/app/db_compat.py` | Engineering | 2026-10-15 |
| TC-ARCH-5 | Agent actions fail closed when the database is unavailable | `docs/reliability.md` | Engineering | 2026-10-15 |
| TC-ARCH-6 | Gateway bundles are Ed25519-signed; gateways refuse bad, replayed or expired bundles and deny all after the offline allowance | `docs/gateway-distribution.md`, `backend/app/gateways.py`, `sdk/python/greyguard_sdk/gateway.py` | Engineering | 2026-10-15 |
| TC-ARCH-7 | The sandbox is off by default, accepts only predefined jobs, and has no network and a read-only root | `docs/controlled-execution-isolation.md` | Engineering | 2026-10-15 |
| TC-ARCH-8 | A register tracks 30 threats and does not replace independent assessment | `docs/threat-and-vulnerability-register.md` | Engineering | 2026-10-15 |
| TC-ARCH-9 | Four deployment models, each with a documented data boundary and responsibilities | `docs/deployment-models.md` | Engineering | 2026-10-15 |
| TC-DP-1 | The shipped image serves HTTP on loopback; TLS 1.2/1.3 and HSTS are configured at the operator's proxy from a template | `docker-compose.production.yml`, `deployment/nginx.conf`, `deployment/nginx-tls.conf`, `docs/production-deployment.md` | Engineering | 2026-10-15 |
| TC-DP-2 | The shipped configuration sets CSP, frame, content-type, referrer and permissions headers | `deployment/nginx.conf` | Engineering | 2026-10-15 |
| TC-DP-3 | Outbound requests are HTTPS-only, address-pinned and refuse internal and metadata addresses | `backend/app/outbound_delivery.py`, `backend/tests/test_outbound_delivery.py` | Engineering | 2026-10-15 |
| TC-DP-4 | GreyGuard does not encrypt the live database; at-rest encryption is the operator's | `docs/deployment-models.md`, `docs/production-deployment.md` | Engineering | 2026-10-15 |
| TC-DP-5 | Production PostgreSQL backups are not encrypted by GreyGuard; AES-256-GCM backups are SQLite-only | `backend/app/postgres_backup_ops.py`, `backend/app/encrypted_backups.py`, `docs/production-deployment.md`, `docs/deployment-operations-part1.md` | Engineering | 2026-10-15 |
| TC-DP-6 | Passwords and agent keys are PBKDF2 hashes; session and gateway tokens are SHA-256 hashes | `backend/app/admin_auth.py`, `backend/app/main.py`, `docs/gateway-distribution.md` | Engineering | 2026-10-15 |
| TC-DP-7 | TOTP seeds are stored unencrypted and are redacted from exports | `backend/app/admin_auth.py`, `backend/app/org_lifecycle.py` | Engineering | 2026-10-15 |
| TC-DP-8 | Integration secrets are stored as references and resolved just in time, never stored as values | `docs/secret-management-integrations.md`, `backend/app/secret_providers.py` | Engineering | 2026-10-15 |
| TC-DP-9 | Signing keys and database credentials are operator-held; customer-managed keys are not offered | `docs/deployment-models.md` | Engineering | 2026-10-15 |
| TC-DP-10 | Secrets are redacted before telemetry is logged, retained, displayed or exported | `docs/observability.md` | Engineering | 2026-10-15 |
| TC-IAM-1 | Individual accounts; local or OIDC PKCE sign-in with verified tokens and a fixed redirect | `docs/enterprise-identity.md`, `backend/app/enterprise_sso.py` | Engineering | 2026-10-15 |
| TC-IAM-2 | 15-minute access tokens; rotating 7-day refresh tokens with reuse detection | `docs/enterprise-session-security.md`, `backend/app/admin_auth.py` | Engineering | 2026-10-15 |
| TC-IAM-3 | TOTP MFA is enforced per account once enabled, not install-wide; the readiness checklist reports it | `backend/app/admin_auth.py`, `docs/organization-lifecycle.md` | Engineering | 2026-10-15 |
| TC-IAM-4 | Three roles: Platform Administrator, Security Analyst, Auditor | `backend/app/admin_auth.py` | Engineering | 2026-10-15 |
| TC-IAM-5 | Elevation needs a second administrator; break-glass is restricted, reasoned, expiring and recorded | `docs/enterprise-identity.md` | Engineering | 2026-10-15 |
| TC-IAM-6 | Optional agent mTLS is off by default, stores only thumbprints, and returns generic failures | `docs/agent-certificate-authentication.md` | Engineering | 2026-10-15 |
| TC-IAM-7 | The tenant guard rejects org-scoped queries without an org predicate | `backend/app/tenant_guard.py`, `backend/tests/test_tenant_guard.py` | Engineering | 2026-10-15 |
| TC-IAM-8 | A route-generated acceptance suite tests every route for cross-org leaks | `backend/tests/test_tenant_acceptance.py`, `docs/testing-and-assurance.md` | Engineering | 2026-10-15 |
| TC-SDL-1 | CI runs the test suites and container builds on pull requests and pushes to main | `.github/workflows/ci.yml` | Engineering | 2026-10-15 |
| TC-SDL-2 | Security checks (pip-audit, npm audit, Bandit, CodeQL, Gitleaks, Trivy, SBOM, E2E) run on pull requests and weekly | `.github/workflows/security.yml` | Engineering | 2026-10-15 |
| TC-SDL-3 | The 2026-10-12 scheduled run failed in three jobs; the causes are fixed and pass locally; GitHub confirmation pending | `.github/workflows/security.yml`, `.gitleaksignore`, `docs/roadmap/addendum-reconciliation.md` | Engineering | 2026-10-15 |
| TC-SDL-4 | The final review gate blocks fixable critical/high findings; unfixed ones expire after 30 days | `docs/final-security-review.md`, `scripts/run_final_security_review.py` | Engineering | 2026-10-15 |
| TC-SDL-5 | Releases come from protected tags with provenance and an Ed25519-signed manifest | `.github/workflows/release.yml`, `docs/deployment-operations-part2.md`, `scripts/create_release_manifest.py` | Engineering | 2026-10-15 |
| TC-SDL-6 | Dependabot opens update pull requests for Python, npm and Actions | `.github/dependabot.yml` | Engineering | 2026-10-15 |
| TC-AV-1 | No SLA and no committed RPO or RTO | `docs/reliability.md` | Project owner | 2026-10-15 |
| TC-AV-2 | Single host, not HA; replicas are safe; multi-host HA is remaining work | `docs/reliability.md` | Engineering | 2026-10-15 |
| TC-AV-3 | Database loss, gateway isolation and delivery failures fail closed or retry with evidence | `docs/reliability.md` | Engineering | 2026-10-15 |
| TC-AV-4 | Backups are whole-install and verified; single-org restore is not supported | `docs/deployment-models.md`, `backend/app/postgres_backup_ops.py` | Engineering | 2026-10-15 |
| TC-AV-5 | The scripted DR drill exercises the SQLite path; no PostgreSQL DR drill is recorded | `scripts/run_disaster_recovery_drill.py`, `docs/deployment-operations-part2.md` | Engineering | 2026-10-15 |
| TC-AV-6 | A public status page shows component health and severity definitions | `docs/deployment-models.md` | Engineering | 2026-10-15 |
| TC-AV-7 | Data stays in the install's region; per-org regions are not built | `docs/reliability.md` | Engineering | 2026-10-15 |
| TC-AV-8 | Published load figures are observations, not commitments | `docs/reliability.md` | Engineering | 2026-10-15 |
| TC-IR-1 | A runbook covers readiness failure, evidence preservation, restore and rollback; there is no formal security-incident response plan | `docs/operations-runbook.md`, `docs/deployment-operations-part2.md` | Project owner | 2026-10-15 |
| TC-PR-1 | Analytics are counts only, collect one fixed-path page-view count, honour Do Not Track and exclude content | `docs/product-analytics.md`, `backend/app/product_analytics.py` | Engineering | 2026-10-15 |
| TC-PR-2 | Analytics can be disabled install-wide or per org, deleting collected counts | `docs/product-analytics.md` | Engineering | 2026-10-15 |
| TC-PR-3 | Audit retention defaults to 365 days, legal holds block deletion, and a SHA-256 chain records erasures | `docs/audit-integrity-and-retention.md` | Engineering | 2026-10-15 |
| TC-PR-4 | Export is never withheld, is digested, and redacts credentials | `docs/organization-lifecycle.md`, `backend/app/org_lifecycle.py` | Engineering | 2026-10-15 |
| TC-PR-5 | Offboarding stops all activity; deletion is operator-only, gated and certified | `docs/organization-lifecycle.md` | Engineering | 2026-10-15 |
| TC-PR-6 | Deleted data remains in backups until they age out | `docs/deployment-models.md` | Engineering | 2026-10-15 |
| TC-SUB-1 | The backend has no built-in external destination and sends no telemetry out | `backend/tests/test_trust_center.py` | Engineering | 2026-10-15 |
| TC-SUB-2 | Outbound connections go only to operator- or customer-configured endpoints | `backend/app/outbound_delivery.py`, `backend/app/secret_providers.py`, `backend/app/enterprise_sso.py` | Engineering | 2026-10-15 |
| TC-SUB-3 | Only a sandbox billing provider exists, refused in production; card data is never stored | `backend/app/billing.py`, `docs/deployment-models.md` | Engineering | 2026-10-15 |
| TC-SUB-4 | Email delivery is not built and refuses to send | `backend/app/notification_delivery.py` | Engineering | 2026-10-15 |
| TC-SUB-5 | Hosted-offering vendors are not chosen; none is claimed | `docs/roadmap/p6-decision-package.md` | Project owner | 2026-10-15 |
| TC-SUB-6 | Source, CI and registry are on GitHub, which does not process data from a running install | `.github/workflows/release.yml` | Engineering | 2026-10-15 |
| TC-VD-1 | Private reports via GitHub Security Advisories; five-business-day acknowledgement target | `SECURITY.md` | Project owner | 2026-10-15 |
| TC-VD-2 | security.txt waits for a named security contact (T3) | `docs/roadmap/p6-decision-package.md` | Project owner | 2026-10-15 |
| TC-VD-3 | Safe-harbour terms are for counsel and not offered yet | `docs/roadmap/p6-decision-package.md` | Project owner | 2026-10-15 |
| TC-CERT-1 | No certification or insurance is held or claimed; no compliance claim is made | `docs/roadmap/GreyGuard_Final_Product_Commercial_and_Launch_Roadmap_Addendum.md` | Project owner | 2026-10-15 |
| TC-CERT-2 | No independent penetration test yet; one is to be commissioned before the first paid pilot | `docs/roadmap/p6-decision-package.md`, `docs/threat-and-vulnerability-register.md` | Project owner | 2026-10-15 |
| TC-ER-1 | The evidence-request process waits for T8 | `docs/roadmap/p6-decision-package.md` | Project owner | 2026-10-15 |
| TC-ER-2 | The listed evidence exists or is produced by repository scripts | `scripts/generate_sbom.py`, `scripts/create_release_manifest.py`, `scripts/run_final_security_review.py`, `docs/threat-and-vulnerability-register.md`, `backend/tests/test_tenant_acceptance.py` | Engineering | 2026-10-15 |
