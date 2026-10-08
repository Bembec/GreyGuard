# Addendum Reconciliation — Status Matrix

Reconciles `GreyGuard_Final_Product_Commercial_and_Launch_Roadmap_Addendum.md` against the current repository, the original engineering task list, and `stage-2-reconciliation.md`. Organized in the addendum's own P0–P10 order. Status values: **Verified** (done, tested, evidence below), **In progress** (started, not complete), **Planned** (scoped, not started), **Deferred** (explicitly held pending a checkpoint/approval per the addendum or Michael's instructions), **Not applicable**.

Nothing below duplicates already-completed work — where a requirement is already satisfied, the entry says so and points at the commit/file, rather than re-describing or re-implementing it.

---

## P0 — Finish current security milestones

| Requirement | Status | Evidence |
|---|---|---|
| Secure outbound delivery | **Verified** | `outbound_delivery.py`, `outbound_worker.py` + wiring into notification/incident/export/report queues. Commits `32722f1`…`39d053e`. 114 tests across the affected files; full backend suite green at the time. |
| Enterprise OIDC sign-in | **Verified** | `enterprise_sso.py` (Authorization Code + PKCE, RS256/ES256 only, nonce/state/PKCE single-use, fixed redirect URI). Commits `c95ec2c`…`d550e38`. 36 dedicated tests + full suite green. |
| Certificate-based agent authentication | **Verified — after fixing two real bugs the independent review below found** | `agent_certificate_auth.py`, `workload_identities.agent_name` binding, nginx header contract. Originally committed `ce79ddd`…`05ada59` (26 tests) and marked Verified in this matrix — **that was wrong**. The independent review (below) found that `deployment/nginx.conf`, the file `frontend.Dockerfile` actually bakes into the production image, never set `X-SSL-Client-Verify`/`X-SSL-Client-Cert` at all, so a client could forge them directly once mTLS trust was enabled (Critical — complete authentication bypass), and that the backend never un-escaped nginx's percent-escaped `$ssl_client_escaped_cert`, so a *legitimately* presented certificate could never match its registered fingerprint either (High — the honest path was also broken). Both are now fixed: `nginx.conf` forces both headers to a safe fixed value in every backend-proxying block, and `agent_certificate_auth.py` calls `urllib.parse.unquote()` before computing the thumbprint. A new test (`test_shipped_nginx_config_never_trusts_a_client_supplied_certificate_header`) asserts this against whichever config the Dockerfile actually ships, not just `nginx-tls.conf` in isolation — closing the "nothing keeps the two files in sync" gap that let this ship unnoticed. 29 tests now (27 in `test_agent_certificate_auth.py` + 2 new in `test_container_hardening.py`), all passing. |
| Credential history | **Verified** | `agent_credential_events` table, `GET /agents/{name}/credential-history`, UI pager on the agent detail page. Commits `12368d2`…`8b84353`. 9 tests, two of which independently confirm no credential/hash ever appears in the evidence. |
| Artifact scanning | **Verified** | `malware_scanner.py` (clamd INSTREAM adapter, disabled by default), quarantine/scan routes. Commits `e68e32e`…`662cfff`. 22 tests against a fake local clamd server, no live ClamAV required. |
| Full tests pass | **Verified** | Full backend suite re-run after each milestone; latest run **423 passed, 4 skipped** (skips are the Windows-only symlink tests that run for real on CI's `ubuntu-latest`), 0 failed. Frontend: lint clean, 87/87 unit tests, production build succeeds, each re-verified after every milestone in this session. |
| E2E covers every page | **Verified** | `frontend/e2e/every-page.spec.ts` + `security-smoke.spec.ts` — fresh run, 38/38 passing. |
| Production rehearsal and final security review pass | **Verified** | Fresh `scripts/run_final_security_review.py` run: pip-audit, bandit, npm audit, secret-scan, SBOM generate/verify, both container scans all passed. One pre-existing, correctly-handled item: a HIGH CVE (`CVE-2026-85091`, Debian base-image `zlib`, no upstream fix) is tracked as a time-boxed accepted risk with compensating controls and a 2026-11-07 review date — not GreyGuard's own code, not suppressed. |
| No security exception disguised as a pass | **Verified** | No `#nosec`, no suppressed bandit/pip-audit findings, no skipped security-relevant test introduced this session. Confirmed via `bandit -lll` (0 findings) after every milestone. |
| Independent review recorded for OIDC/JWT and other high-impact authentication logic | **Verified** | A fresh agent with no prior context on this codebase reviewed `enterprise_sso.py` and `agent_certificate_auth.py` cold, plus their supporting code (`admin_auth.py`, `enterprise_identity.py`, `nginx-tls.conf`, `nginx.conf`, `docker-compose.production.yml`, the API wiring, and existing tests). It found and I independently re-confirmed by reading the actual files: **Finding 1 (Critical)** — `nginx.conf`, the file actually shipped, never set the certificate-verdict headers the backend trusts, a complete authentication bypass; **Finding 2 (High)** — the backend never un-escaped nginx's percent-escaped certificate forwarding, so even a legitimate certificate could never authenticate; **Finding 3 (Medium)** — SSO provider email-domain restriction was fail-open by default, letting a misconfigured provider silently take over an existing local administrator's account by email match. All three are now fixed (see the certificate-authentication row above and Milestone-2-adjacent fix below) with new regression tests. The OIDC/JWT verification logic itself (algorithm allowlist, kid handling, JWKS caching, SSRF protections, nonce/state/PKCE handling) was reviewed line-by-line against every explicit requirement and found to hold up — no flaw found there. A fourth, Low-severity hardening suggestion (JWKS forced-refresh debounce) was logged but not acted on; it is not independently exploitable without IdP collusion. This is exactly the gap this line was meant to close, and exactly why it mattered: self-review had missed all three real findings. |
| SSO provider domain-restriction fail-open (admin-takeover risk) | **Verified (fixed)** | `enterprise_identity.save_provider()` now refuses to persist a provider with an empty `allowed_domains` unless the caller explicitly passes `allow_any_domain=true`, forcing a conscious choice instead of a silent default. Wired through `IdentityProviderRequest`/`configure_identity_provider` in `api.py` and a new checkbox in `EnterpriseIdentityPage.tsx`. 2 new tests in `test_enterprise_identity.py`; one pre-existing test updated to pass the explicit flag. Found by the same independent review (Finding 3) that found the certificate-auth bugs above. |

### Operations/structural corrections named in the original task but not in the addendum's P0 list

These were part of the original engineering task's "Operations and structural corrections" section. The addendum doesn't explicitly re-list them, but they're prerequisites the addendum assumes (e.g. P2 says "after a complete baseline Alembic migration").

| Requirement | Status | Evidence |
|---|---|---|
| Full `.env.production.example` audit | **Verified** | Documented every previously-undocumented variable actually read by the backend: `GREYGUARD_DATABASE_URL` (noted as auto-derived by `docker-compose.production.yml`), `GREYGUARD_ADMIN_PIN` (documented as forbidden in production, not as something to set), `GREYGUARD_REPORT_SIGNING_KEY`, `GREYGUARD_POLICY_SIGNING_KEY`, `GREYGUARD_BACKUP_KEY`, `GREYGUARD_RELEASE_SIGNING_KEY`, `VAULT_ADDR`/`VAULT_TOKEN`, `GREYGUARD_DELIVERY_WORKER_ENABLED`/`INTERVAL_SECONDS`/`BATCH_LIMIT`. Re-validated with `docker compose -f docker-compose.production.yml config` against the updated file (exit 0). |
| PostgreSQL-native backup/restore scripts | **Verified** | New `backend/app/postgres_backup_ops.py` (`pg_dump`/`pg_restore` custom-format, sha256 manifest, fail-closed on a failed dump or failed structural verification, `--confirm`-gated restore). 10 tests in `backend/tests/test_postgres_backup_ops.py` (subprocess stubbed - no live PostgreSQL available in this environment; a real end-to-end rehearsal still belongs in `deployment/postgresql-rehearsal.yml`-style CI). `docs/production-deployment.md` corrected: it previously told operators to run the SQLite-only `database_ops.py` against a deployment (`docker-compose.production.yml`) that actually runs PostgreSQL and that `db_compat.py` refuses to start as SQLite in production - that backup procedure would have backed up an unused, empty file while the real database went unprotected. Also corrected the doc's claim that the `greyguard-data` volume holds "persistent SQLite state" (it holds only isolated-workspace/quarantine files). |
| Docs correction: Alembic doesn't manage the full schema | **Not applicable — already accurate** | Checked `docs/deployment-operations-part1.md`, `docs/postgresql-migration.md`, `README.md`, and the migration file's own docstring (`20261005_01_migration_control.py`: "Create PostgreSQL migration control evidence table"). None overclaim Alembic's coverage; `deployment-operations-part1.md` already states explicitly "It does not claim that the existing application persistence code has already been converted." No false claim existed to fix. |
| Full baseline Alembic migration before Phase C | **Planned, and explicitly gates P2** | Not started, and not attempted this round even though Docker is available here (confirmed: `docker info` reports server 29.8.1). The real blocker is architectural, not environmental: `backend/migrations/env.py` sets `target_metadata = None`, so there is no SQLAlchemy model layer for `alembic revision --autogenerate` to diff against - the schema exists only as raw `CREATE TABLE`/`ALTER TABLE` calls scattered across ~28 modules. Producing this baseline means hand-transcribing all ~76 tables' columns, types, defaults, constraints, and indexes into Alembic `op.create_table()` calls (the same style the one existing migration already uses by hand), cross-checked against `db_compat.py`'s SQLite→PostgreSQL translation rules. That is a large, meticulous, high-stakes transcription with real risk of a subtle mistake (a missed `NOT NULL`, `UNIQUE`, or index) that any future real migration would then build on top of - exactly the kind of "major workstream" the addendum's P2 gate exists to make sure isn't rushed. Flagging rather than attempting it unreviewed in one pass. |
| Reconcile the two Python SDKs | **Verified (documented split + safety backport; not merged)** | Read both fully: `sdk/python/greyguard_sdk` (externally-distributable, agent-only, has its own `pyproject.toml`) and `backend/sdk/greyguard_client.py` (agent **and** admin client, used by GreyGuard's own docs/examples/tests, not separately packaged). They are not accidental duplicates - different audiences - but `backend.sdk.GreyGuardAgentClient` was missing a real safety property the public SDK has: it never sent the server's honored `Idempotency-Key` header on `/tool-requests` (confirmed server-side support at `backend/app/api.py:2755`), so a caller retrying after a timeout could create duplicate tool requests. Backported an optional `idempotency_key` parameter (`backend/sdk/greyguard_client.py`'s `request_tool`/`_request`), with 3 new tests in `backend/tests/test_agent_sdk.py` (send/omit/reject-short-key), all passing alongside the 12 pre-existing SDK tests. Added cross-referencing docstring/README notes in both packages so the split reads as intentional rather than drift. A full merge into one implementation was evaluated and rejected: the two clients' transport-callable signatures and exception hierarchies are genuinely incompatible at the call level, so unifying them would require rewriting `backend/tests/test_agent_sdk.py`'s contracts and `backend.sdk`'s documented constructor/transport shape - a public-API-visible change, not internal cleanup, so it's left for your call rather than done silently. |
| Pin FastAPI/Uvicorn | **Deferred — needs your explicit approval** | Not started; this is a dependency-version change, which the working instructions for this whole engagement require stopping for before doing. |
| Remove empty scaffolding (`routers/services/core/schemas/utils`) | **Verified** | Confirmed all five `__init__.py` files were 0 bytes and had zero references anywhere in the repository (`grep` for every plausible import form returned nothing), then `git rm -r` on all five directories. Targeted test run (`test_api_compatibility.py`) still passes after removal. |
| PostgreSQL parity tests for `db_compat.py` | **Verified (translator-level; no live-server rehearsal)** | Read every table/query this session added (`agent_credential_events`, `oidc_login_attempts`, `outbound_delivery_evidence`/`outbound_allowed_private_hosts`, `workload_identities`'s `ALTER TABLE` migration, `quarantined_artifacts`/`isolated_workspaces`) and confirmed none use a pattern `_translate()` doesn't already generically handle (no `BLOB`, no `COLLATE NOCASE`, no `INSERT OR REPLACE`/`OR IGNORE`, no unbounded `LIMIT -1 OFFSET`) - and confirmed neither new `AUTOINCREMENT` table (`agent_credential_events`, `enterprise_identity_events`) ever reads `cursor.lastrowid` the way the pre-existing special-cased `alert_notes` table does, so no new table-name special-casing was needed. Added 3 new `_translate()`-level tests to `backend/tests/test_database_compatibility.py` covering `ALTER TABLE ... ADD COLUMN`, a `FOREIGN KEY` clause, and a multi-statement `executescript`-style block with `AUTOINCREMENT` not in the first statement (mirrors `enterprise_identity.py`'s real initialization call) - all 7 tests in that file pass. This is string-level translator verification, the same technique the pre-existing tests in that file use; it is not a live-PostgreSQL rehearsal, which still needs the `postgresql-rehearsal.yml`/Docker path noted above. |

---

## P1 — Professional authenticated product experience

**Status: Deferred.** This is the "Phase B" branded-interface work from the original task, which Michael's standing instruction and the addendum both gate behind an explicit checkpoint: *"Do not begin the branded interface, commercial foundation or public website before reaching its stated checkpoint and receiving my approval."* Nothing in this category has been started. The current UI (dense, functional, per-page CSS, no unified design system, no mega-menu, no splash/install-wizard) is exactly as it was before this session, and Stage 3's frontend changes (SSO button, workload-certificate list, credential-history pager, artifact upload/scan controls) were deliberately minimal, additive, and styled to match the *existing* per-page convention rather than anticipating P1's design system — so none of that work will need to be redone or thrown away when P1 starts; it'll just be re-skinned along with everything else.

---

## P2 — Tenant and commercial platform foundation

**Status: Deferred**, same basis as P1, and additionally blocked on the Alembic baseline migration above. Not started. No organizations/tenancy/billing code exists anywhere in the repository (confirmed: no `organization`/`tenant`/`billing` tables or modules).

---

## P3 — Deployment packages and service reliability

**Status: Planned/Deferred (mixed).** Not started as a body of work. Partial, pre-existing infrastructure that P3 would build on:

| Sub-item | Status | Evidence |
|---|---|---|
| Node/gateway enrollment and workload identity | **In progress (foundation exists)** | `workload_identities` (this session's Milestone 3) is the closest existing primitive — it's agent-certificate identity, not yet a *gateway/node* enrollment concept. Would need extension, not duplication. |
| Signed versioned policy/configuration distribution | **Not applicable yet** | `policy_control.py`'s signed policy versions exist for the single-tenant control plane today; a distribution mechanism to external gateways doesn't exist. |
| HA/failure-mode matrix, load/benchmarks, regional data-placement | **Planned** | Not started. `scripts/benchmark_greyguard.py` exists for basic benchmarking but nothing matrix/multi-region shaped. |
| Status page, severity/escalation policy | **Planned** | Not started. |
| API/SDK compatibility matrix and deprecation policy | **In progress (foundation exists)** | `api_versioning.py` + `/api/version` discovery already exist (confirmed in the original review); a published compatibility matrix/deprecation policy document does not. |

---

## P4 — Buyer validation, packaging and pricing

**Status: Not applicable to engineering work in this repository.** This is customer-discovery and pricing-strategy work for Michael and any commercial team, not something resolved by writing code. No action taken, none planned by me.

---

## P5 — Customer onboarding and success

**Status: Deferred**, gated behind P1–P2 (there's no tenant/organization model yet to onboard anyone *into*). Not started.

---

## P6 — Vendor trust and procurement readiness

**Status: Planned/Deferred (mixed).**

| Sub-item | Status | Evidence |
|---|---|---|
| Security overview/architecture content | **In progress (source material exists)** | `docs/final-security-review.md`, `docs/threat-and-vulnerability-register.md`, `assurance/threat-model.md` already contain real, accurate content a Trust Center could draw from — assembling them into a public-facing page is separate, deferred work (part of P7's separate public site). |
| Subprocessor register, responsible-disclosure policy, `security.txt` | **Planned** | `SECURITY.md` exists at the repo root (confirmed in original review) covering responsible disclosure for the *codebase*; a public `security.txt`/subprocessor register for a commercial offering doesn't exist yet. |
| SOC 2/ISO 27001/insurance/certifications | **Not applicable** (per the addendum itself) | Addendum explicitly calls these "later gated programmes, not launch claims" — correctly not attempted. |
| Legal documents (Terms, DPA, AUP, etc.) | **Not applicable to engineering** | Requires qualified legal counsel per the addendum's own text; not something I should draft or imply completion of. |

---

## P7 — Separate public commercial website

**Status: Deferred.** Explicitly gated behind P1/P2 completion and your approval per both the addendum and your instruction. Not started — no separate site, no separate deployment, nothing in this repository changes for it yet.

---

## P8 — Proof, demonstrations and claims governance

**Status: Deferred**, depends on P1 (stable authenticated app) and P7 (site to host proof experiences) existing first. Not started. No claim register exists yet.

---

## P9 — Sales, pilot and partner enablement

**Status: Deferred**, explicitly sequenced by the addendum to start only "after the application and proof path are stable." Not started.

---

## P10 — Documentation and final acceptance

**Status: Planned**, corresponds to the original task's Phase D/E. Not started as its own pass, though some prerequisite material already exists and was strengthened this session:

| Sub-item | Status | Evidence |
|---|---|---|
| Tenant-isolation design and test evidence | **Not applicable yet** | No tenancy exists (see P2). |
| Trust Center source register, claim register | **Planned** | Not started (see P6/P8). |
| Complete source-code/security PDF | **Planned** | Not started — this is the original task's Phase D deliverable. |
| Independent security review | **Planned** | Same gap flagged under P0 above; applies here too as a final-acceptance gate. |
| Backup/restore/upgrade/rollback/tenant-deletion rehearsals | **In progress (partial)** | `scripts/rehearse_production.py`, `scripts/run_disaster_recovery_drill.py`, `scripts/verify_postgresql_parity.py` exist and have run successfully before (per `artifacts/production-rehearsal.json`, dated before this session's changes). The real PostgreSQL backup/restore gap this item depended on is now closed (`postgres_backup_ops.py`, above); tenant-deletion rehearsal remains open (no tenancy yet). |

---

## Summary

**Done this session, confirmed with evidence:** all five Stage 3 security milestones; six of the eight "operations and structural corrections" items (`.env.production.example` audit, PostgreSQL-native backup/restore tooling, the two-SDKs reconciliation, empty-scaffolding removal, `db_compat.py` parity tests — the Alembic-scope docs item needed no fix); a genuinely independent security review of the two highest-impact authentication modules, which found and got fixed one Critical (complete cert-auth bypass via the actually-shipped `nginx.conf`), one High (percent-escaping break that made legitimate cert auth non-functional), and one Medium (SSO admin-takeover via fail-open domain restriction) finding; a fresh full E2E run (38/38) and a fresh final-security-review run (all checks passed, one correctly-tracked pre-existing base-image CVE with no code impact). Full backend suite confirmed clean in 3 memory-safe batches (439 passed, 4 skipped, 0 failed) before this round's security fixes; every file touched by the fixes has its own passing targeted test run (85 tests across the five affected files) plus a clean frontend check (87/87 unit, build, bandit 0 High).

**Real open items before P0 can be called fully closed:**
1. The full baseline Alembic migration — not attempted; needs a deliberate, reviewed pass to hand-transcribe ~76 tables (no SQLAlchemy metadata layer exists for autogenerate), not something to rush through unreviewed.
2. Pinning FastAPI/Uvicorn — deferred, needs your explicit approval as a dependency-version change.
3. A fresh full-suite run specifically covering this round's three security fixes together with everything else (targeted runs all pass; a final combined run is recommended before calling this closed).

**A note on what the independent review changed:** this matrix previously marked certificate-based agent authentication "Verified" based on my own self-review and passing tests. It wasn't actually safe — the tests passed because they never exercised the real deployment wiring (which nginx config ships) or realistic nginx output (percent-escaping), exactly the kind of gap self-review tends to miss because it trusts its own design assumptions. Independent review is the reason this is caught before anyone relied on it.

**Everything from P1 onward is correctly untouched**, per your standing instruction and the addendum's own sequencing. I have not begun branded-interface, tenancy/billing, or public-website work, and will not without your explicit go-ahead at each checkpoint.

**Nothing has been pushed.** All work is in local commits on `main`, per your instruction.
