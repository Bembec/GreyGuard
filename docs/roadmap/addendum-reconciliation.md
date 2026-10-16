# Addendum Reconciliation — Status Matrix

> **Plan of record: Master Roadmap v3, adopted 2026-10-15.** See [`v3-adoption.md`](v3-adoption.md) for how v3 maps onto this matrix, the corrections to its status section, and the four decisions it left open (V1–V4). This matrix stays the evidence record.

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
| Full baseline Alembic migration before Phase C | **Verified** | `backend/migrations/versions/20261008_02_baseline_schema.py` creates all 80 tables. Written by capturing, not hand-transcribing: started a disposable rehearsal PostgreSQL container (`deployment/postgresql-rehearsal.yml`, Docker confirmed available), ran every `initialize_*()` function in `backend/app` against it, and used `pg_dump --schema-only` as the ground truth - avoiding exactly the hand-transcription risk flagged earlier in this document. That process itself caught a real, independent bug: the real startup lifespan (`backend/app/api.py`'s `lifespan()`) never calls `admin_auth.initialize_admin_auth()` - those 4 tables are lazy-only, created on first admin operation, not at startup - so the first capture attempt silently missed them (76 instead of 80). Caught by cross-checking every `CREATE TABLE IF NOT EXISTS` in the codebase against the capture (80 defined, 80 captured, zero missing either direction after the fix) before writing the migration, not after. Verified three ways: (1) that cross-check; (2) wiping the rehearsal database, running `alembic upgrade head` alone, and diffing the resulting schema against the original capture - zero unexpected differences; (3) `scripts/verify_postgresql_parity.py` (the project's own existing Postgres-parity check) passes (20/20) against a database created purely by the migration, with no imperative initialization ever run. Downgrade path also verified (drops all 80 tables and the extension cleanly). Rehearsal container and all scratch files torn down afterward; `artifacts/baseline-schema-verified.sql` kept as committed evidence of the capture. |
| Reconcile the two Python SDKs | **Verified (documented split + safety backport; not merged)** | Read both fully: `sdk/python/greyguard_sdk` (externally-distributable, agent-only, has its own `pyproject.toml`) and `backend/sdk/greyguard_client.py` (agent **and** admin client, used by GreyGuard's own docs/examples/tests, not separately packaged). They are not accidental duplicates - different audiences - but `backend.sdk.GreyGuardAgentClient` was missing a real safety property the public SDK has: it never sent the server's honored `Idempotency-Key` header on `/tool-requests` (confirmed server-side support at `backend/app/api.py:2755`), so a caller retrying after a timeout could create duplicate tool requests. Backported an optional `idempotency_key` parameter (`backend/sdk/greyguard_client.py`'s `request_tool`/`_request`), with 3 new tests in `backend/tests/test_agent_sdk.py` (send/omit/reject-short-key), all passing alongside the 12 pre-existing SDK tests. Added cross-referencing docstring/README notes in both packages so the split reads as intentional rather than drift. A full merge into one implementation was evaluated and rejected: the two clients' transport-callable signatures and exception hierarchies are genuinely incompatible at the call level, so unifying them would require rewriting `backend/tests/test_agent_sdk.py`'s contracts and `backend.sdk`'s documented constructor/transport shape - a public-API-visible change, not internal cleanup, so it's left for your call rather than done silently. |
| Pin FastAPI/Uvicorn | **Verified** | Approved and done. Pinned to `fastapi==0.141.1`/`uvicorn[standard]==0.53.0` - the exact versions already installed and exercised by every test this session has run, not latest-on-PyPI. pip-audit clean; confirmed the production Docker image resolves and installs these exact versions with no surprises. Regenerating the SBOM for this change exposed and fixed a separate, real bug: the generator's parser mishandled `[extras]` brackets, silently producing invalid version strings for every extras-using dependency since PyJWT was added (`psycopg`, `PyJWT`, now `fastapi`/`uvicorn`) - fixed with 3 new tests. |
| Multi-worker SQLite startup race (found while verifying the pin, unrelated to it) | **Verified (fixed)** | Smoke-testing the pinned image in a real container crash-looped on every boot: `security_exports.py` and 6 other modules check a column's presence via `PRAGMA table_info` before `ALTER TABLE ADD COLUMN`, and `initialization_lock` only ever protected PostgreSQL (a no-op for SQLite) - yet `backend.Dockerfile`'s own default command runs 2 workers regardless of backend. Both workers' checks race: one adds the column, the other's identical check-then-add hits "duplicate column name," and uvicorn treats that worker's startup failure as fatal to the whole container. Reproduced directly on both first boot and every restart against the already-migrated database. Fixed at the root in `db_compat.initialization_lock`: SQLite now also acquires a real, file-backed exclusive lock (SQLite's own cross-platform locking, no new dependency) around the entire `initialize_*()` block, mirroring what PostgreSQL already got via an advisory lock. Verified three ways: new tests reproduce the exact race with concurrent threads (fail without the fix, pass with it); rebuilt the Docker image and confirmed a fresh container boots and reports healthy; restarted that same container against the already-migrated database (the scenario that previously crash-looped forever) and confirmed it also boots cleanly. This was latent in the repository before this session and is unrelated to the dependency pin itself - just surfaced by actually running the pinned image end-to-end instead of only running the test suite. |
| Remove empty scaffolding (`routers/services/core/schemas/utils`) | **Verified** | Confirmed all five `__init__.py` files were 0 bytes and had zero references anywhere in the repository (`grep` for every plausible import form returned nothing), then `git rm -r` on all five directories. Targeted test run (`test_api_compatibility.py`) still passes after removal. |
| PostgreSQL parity tests for `db_compat.py` | **Verified (translator-level; no live-server rehearsal)** | Read every table/query this session added (`agent_credential_events`, `oidc_login_attempts`, `outbound_delivery_evidence`/`outbound_allowed_private_hosts`, `workload_identities`'s `ALTER TABLE` migration, `quarantined_artifacts`/`isolated_workspaces`) and confirmed none use a pattern `_translate()` doesn't already generically handle (no `BLOB`, no `COLLATE NOCASE`, no `INSERT OR REPLACE`/`OR IGNORE`, no unbounded `LIMIT -1 OFFSET`) - and confirmed neither new `AUTOINCREMENT` table (`agent_credential_events`, `enterprise_identity_events`) ever reads `cursor.lastrowid` the way the pre-existing special-cased `alert_notes` table does, so no new table-name special-casing was needed. Added 3 new `_translate()`-level tests to `backend/tests/test_database_compatibility.py` covering `ALTER TABLE ... ADD COLUMN`, a `FOREIGN KEY` clause, and a multi-statement `executescript`-style block with `AUTOINCREMENT` not in the first statement (mirrors `enterprise_identity.py`'s real initialization call) - all 7 tests in that file pass. This is string-level translator verification, the same technique the pre-existing tests in that file use; it is not a live-PostgreSQL rehearsal, which still needs the `postgresql-rehearsal.yml`/Docker path noted above. |

---

## P1 — Professional authenticated product experience

**Status: Verified — Phase 1 (design system + shell/nav/login/splash/wizard), Phase 2 (per-page retrofits) and Phase 3 (PWA + accessibility hardening) all complete.** Michael approved beginning P1 and supplied the approved brand pack (`GreyGuard_Brand_Assets.zip`: brand guide, exact palette, logo system, interface asset mapping, prohibited-usage rules). Sequencing (Michael's choice): Phase 1 first as its own reviewable unit, then page retrofits in batches, then PWA/a11y polish last. **P1.4, the information architecture redesign, is Planned and is a firm final-acceptance requirement (see below).**

| Requirement | Status | Evidence |
|---|---|---|
| Consistent design system (palette, typography) | **Verified** | `tokens.css` re-pointed at the exact approved hex values (not the near-but-not-exact values it held before); Inter/Saira self-hosted via `@fontsource` (Inter was referenced in CSS but never actually loaded before - relied on coincidentally being an OS font; Saira didn't exist in the codebase at all). Status-color tokens (violet/green/amber/red/rose) deliberately untouched - functional, not brand-identity. Commits `8967007`. |
| Branded shell (real logo assets) | **Verified** | `Logo.tsx` covers all three brand-pack interface mappings (primary/horizontal/symbol) through one component; replaces the sidebar's Lucide-icon-and-text placeholder, the login/SSO wordmarks, and the dashboard/agents watermarks. Commits `9385b28`, `b4b2efc`, `b278382`. |
| Splash/readiness screen | **Verified** | `AuthContext.isResumingSession` + `SplashScreen` replace the previous flash-of-`LoginPage` on every hard reload with a live session. Verified end-to-end (reload with session → splash → dashboard; reload without one → login, no splash frame). Commit `9385b28`. |
| One-time first-installation wizard | **Verified** | Trigger is real (zero rows in `administrators`), not invented - `count_administrators()`/`setup_first_administrator()` plus `GET /auth/setup-status`/`POST /auth/setup`. 2-step flow (a planned third "done" step was removed once it became clear it's unreachable - completing setup authenticates immediately and the route tree swaps away). 5 backend tests; verified end-to-end against a real browser and a genuinely empty database. Commit `07d3c9b`. |
| Professional password, MFA and configured SSO login | **Verified (brand polish only; flow intentionally unchanged)** | Logo swap and token consistency only - inline MFA (password + conditional 6-digit field, same form) was evaluated and deliberately kept as-is; the splash screen already fixed this area's real defect, and restructuring a working pattern into a multi-screen wizard would add a step for non-MFA users with no benefit. Commit `b278382`. |
| Organization/user menu | **Verified** | `UserMenu.tsx` replaces the static, non-interactive "Administrator / Verified session" topbar label with a real dropdown (identity, role, Account security / Settings / Sign out). Also closed a real bug found while building it: `SettingsPage`'s own logout button skipped the backend revoke call and left the refresh token behind in storage - both entry points now call the one correct `AuthContext.logout()`. Commits `b4b2efc`, `b278382`. |
| Permission-aware navigation | **Verified (primitive + nav usage; page-level migration deferred)** | `usePermission`/`RequirePermission` support role, anyRole, permission and anyPermission checks - `Administrator.permissions` existed end-to-end already but was never read client-side; nav filtering could previously only match one exact role. `RequirePermission`'s three prop combinations cover the three ad hoc page-guard patterns already in the codebase, so migrating individual pages onto it is a mechanical follow-up, not a redesign - intentionally not done in this phase. 8 tests. Commit `83d07db`. |
| Deep mega-menu and contextual navigation | **Verified** | Replaced the flat 34-item list (icons covering only 17) with 5 groups mirroring the commercial roadmap's own Gate/Watch/Respond/Evidence buyer-facing product groups plus Administration - every item accounted for, cross-checked for zero omissions/duplicates. `SidebarNavGroup` (expanded) and `NavFlyout` (collapsed - the actual mega-menu surface, keyboard-operable with a Tab trap) both reuse a new `useDismissableLayer` hook extracted from `ConfirmDialog`/`GlobalSearchDialog`'s previously-duplicated focus-handling code. Commits `83d07db`, `b4b2efc`. |
| Mobile, tablet, keyboard and screen-reader support | **Verified (dialog keyboard/focus behavior, accessible names, persisted motion preference; full page-by-page a11y audit not attempted)** | Three concrete, verified gaps rather than a speculative broad pass. (1) The reduced-motion/density/accent preference only ever applied while `SettingsPage` itself was mounted - `applySettings()` was never called at boot, so a saved preference silently reverted to defaults on every hard reload; extracted the settings logic into `src/lib/interfaceSettings.ts` and call `applySettings(loadSettings())` synchronously in `main.tsx` before first render. (2) 8 pages built their own custom `role="dialog"` overlay instead of reusing the Phase 1 `useDismissableLayer` pattern, so none of them had Escape-to-close, a Tab focus trap, or focus restore on close - migrated `AgentsPage`, `ApprovalsPage`, `IncidentCenterPage`, `RiskCenterPage`, `ServiceAccountsPage`, `ThreatRegisterPage`, `TeamAccessPage` (which additionally had no `role="dialog"`/`aria-modal` at all) and `ComplianceReportsPage` (both its modals). (3) 4 icon-only buttons across pages touched this phase had no accessible name at all (no text, `aria-label`, or `title`) - fixed each. Commit `d5b15d9`. |
| PWA packaging and safe update/offline behavior | **Verified** | `vite-plugin-pwa` added with `registerType: "prompt"` (not `autoUpdate`) and manual registration via a new `PwaUpdatePrompt` component - an operator is never silently swapped onto new app code; a dismissible "reload now" banner appears only when a build update is actually available. The generated service worker precaches only the built app shell (JS/CSS/HTML/icons/manifest) - there is no `runtimeCaching` entry for `/api/*` at all, so every API request always goes straight to the network; a security console must never serve cached/stale security data while appearing live. Verified directly against `dist/sw.js`'s precache manifest and `dist/manifest.webmanifest`, plus a new `pwa.spec.ts` e2e check against the real built output. Commit `5a74e9a`. |
| Every page a complete operational workspace (drill-downs, filters, history, states) | **Verified (loading/error states and permission gating; color-token convergence deferred)** | A maturity survey of all ~38 remaining page files (15 mature / 6 partial / 13 thin / 2 sub-panels / 1 orphaned) found two concrete classes of defect, fixed page-by-page rather than assumed uniformly: (1) five already-mature pages (`ServiceAccountsPage`, `AbuseProtectionPage`, `RiskCenterPage`, `IncidentCenterPage`, `ApprovalsPage`) had real mutation controls - rotate/revoke credentials, policy saves, approve/deny, risk resets - with zero client-side permission awareness, cross-referenced against `admin_auth.py`'s `required_permission()` and gated with the Phase 1 `usePermission` primitive; (2) 16 pages called `fetch()` in their load effect with no error branch at all, silently leaving the page empty forever on a failed request - fixed with a consistent loading/error/content gate using the pre-existing `AsyncState` components. Also closed: `AbuseProtectionPage`'s initial mutation-only gate was corrected to a page-level redirect once fixing its silent-failure bug surfaced that the backend's `GET /abuse-protection` itself requires `PLATFORM_ADMIN`, not just the writes; `PolicyGovernancePanel`'s "Save draft"/"Submit for approval" buttons had no gate at all even though the backend's `require_policy_editor()` blocks AUDITOR from both; `DashboardPage`'s risk table had no drill-down into `AgentDetailPage`; an orphaned, unused `SectionPage.tsx` placeholder was removed. `ComplianceReportsPage`'s Generate/Export was flagged by the survey but confirmed correct as-is (`require_admin()` intentionally allows all roles to capture compliance evidence). Normalizing the ~44 stylesheets' hardcoded/drifted color values onto design tokens was evaluated and explicitly deferred - most of the remaining hex values are gradient/shadow ramps whose visual intent can't be safely flattened without rendering verification; scoped conservatively to exact-token-match replacements only during Phase 1, broader convergence left as a genuine design-review task. Commits `09c730e`, `98939aa`, `1edb9b0`, `b537d20`. |

**Verification run for Phase 1:** `npm run check` (lint/101 unit tests/build) clean; full Playwright e2e suite (38/38, including `every-page.spec.ts` and `security-smoke.spec.ts`) passes unmodified; a standalone end-to-end check against a real browser and a genuinely empty database confirmed the install wizard's full fresh-install path (redirect → welcome → create → immediate authentication → dashboard → reload shows splash, not a login flash).

**Verification run for Phase 2:** `npm run check` (lint/101 unit tests/build) clean after each of the four batches; full Playwright e2e suite passing (40-42 tests depending on batch, 1 consistently skipped - no agents registered in this environment) after each batch, including a new `permission-gating.spec.ts` that creates a real AUDITOR administrator and confirms the gating holds in a real browser rather than relying solely on unit-level hook tests.

**Verification run for Phase 3:** `npm run check` (lint/109 unit tests/build) clean after both batches; full Playwright e2e suite passing after each batch (42/43, 1 consistently skipped), split into smaller per-file runs for the accessibility batch due to this machine's own memory constraints rather than any test instability.

### P1.4 — Information architecture redesign (owner requirement, 2026-10-15)

**Status: Verified (2026-10-15). This is a firm final-acceptance requirement.** The open light-theme item was resolved by owner decision (a): the console is dark-only. The project owner accepted the current interface as functional but not final. The release can't pass final acceptance (P10) while every capability is still an equal item in one long sidebar. The owner approved decisions W0–W11 of [`p7-decision-package.md`](p7-decision-package.md) as recommended, so P1.4 runs before P7.

**Baseline (2026-10-15, `frontend/src/config/navigation.ts`):** 35 navigation entries. One is pinned (Command Center) and 34 sit in five groups: Gate 12, Watch 9, Respond 5, Evidence 4, Administration 4. Groups collapse, but every capability inside a group is a top-level item of equal weight. No page uses page-level tabs.

**Acceptance criteria.** All of these must hold:

1. **Navigation by product domain.** Navigation is grouped by product domain into expandable sections. Related capabilities are consolidated under domain workspaces rather than listed as equal siblings. For example, agent identity, service accounts, adapters and enterprise identity sit together under Gate. No section is a long flat list.
2. **Page-level tabs and contextual actions.** Related views of one subject are tabs on one page, each with a deep link. Actions appear where the record or task is, not only in a global location.
3. **Role-based visibility retained.** Every section, tab and action is shown or hidden by the same permission checks used today (`usePermission` / `RequirePermission`, mirroring `admin_auth.required_permission()`). Server-side authorization stays authoritative and unchanged. `permission-gating.spec.ts` is extended to cover tabs and contextual actions.
4. **Rich operational dashboard.** The Command Center shows only real data, never placeholder metrics. It covers pending approvals, recent decisions, agent risk and suspensions, open incidents, evidence-integrity status and org readiness, and each panel drills through to its source page.
5. **Every page professionally structured, not only the dashboard.** Each page has:
   - a summary header with meaningful counts or status;
   - its primary workflow and actions;
   - filters, plus tables with sorting and paging where the data is tabular;
   - loading, empty, error, permission and offline states;
   - inline guidance.
6. **No functionality lost.** Every route, action and API call that exists today is still reachable. Old URLs redirect to their new location. A route-inventory test proves there are no omissions.
7. **Security boundaries unchanged.** Backend authorization, CSP and the session and token handling stay as they are. Client-side gating never replaces a server check.
8. **Accessibility and mobile.** New sections, tabs and menus work by keyboard and screen reader, on mobile and tablet, and with reduced motion.
9. **Verification bar.** `npm run check`; the full Playwright suite, including `every-page.spec.ts`, `permission-gating.spec.ts` and the new route-inventory test; and a review against a real browser at desktop and phone widths.

**Sub-phases.** Each one gets a `feat:` commit and a `docs:` commit recording its verification run.

| Sub-phase | Scope | Status |
|---|---|---|
| P1.4.1 | Domain workspaces, page tabs, mega-menu, permission-filtered page search, route inventory | **Verified** (below) |
| P1.4.2 | Shared page kit (header, stats, panels, filters, sortable and paged tables, guidance, offline state) and a Command Center that shows only real data | **Verified** (below) |
| P1.4.3 | Gate pages: Agents & Identity, Requests & Approvals, Policies & Controls | **Verified** (below) |
| P1.4.4 | Watch pages: Live Monitoring, Risk & Threats, Telemetry & Sensors | **Verified** (below) |
| P1.4.5 | Respond and Evidence pages | **Verified** (below) |
| P1.4.6 | Administration pages and the two investigation pages | **Verified** (below) |
| P1.4.7 | Acceptance: every criterion above, checked in a real browser at desktop and phone widths | **Verified, one open item** (below) |

**P1.4.1 (commit `374e378`).** `frontend/src/config/workspaces.ts` gathers the 34 pages into 12 workspaces across the five domains: Gate 3, Watch 3, Respond 2, Evidence 2 and Administration 2. The sidebar now has 13 entries, down from 35, Command Center included. Abuse Protection moved from Gate to Administration, because it protects the install rather than gating agents.
- A workspace's pages are tabs (`WorkspaceTabs`). Each tab is a link to the page's existing URL, so every bookmark and deep link still works.
- Each tab, workspace and page search result uses its page's existing `navigationPermission()` check. A workspace with no permitted tab is hidden: for example, an AUDITOR doesn't see Containment.
- Domain sections expand and collapse, and the section holding the open page always shows. The open/closed choice is remembered per device.
- The collapsed sidebar's mega-menu shows each workspace with its pages. The breadcrumb reads domain › workspace. Ctrl+K search now jumps to pages by name.
- Backend, routes and API calls are unchanged.

**Verification run for P1.4.1:**
- `npm run check`: lint clean; 150 unit tests pass, including 13 new route-inventory and visibility tests; build clean.
- Mutation checks. Each of these mutations made a test fail:
  - removing the permission filter from tabs;
  - removing it from page search;
  - dropping a page from its workspace;
  - breaking the mapping from a detail route to its page.
- Full Playwright suite on the P1.4.1 build: 53 passed, 1 skipped (no agents registered). The 4 new navigation tests first failed at sign-in: by signing in before every test they hit the admin sign-in rate limit (20 per 5 minutes), which is the abuse-protection control working. The spec now signs in once and reuses the session, as the other specs do. On the committed tree, the navigation and permission specs then passed 9 of 9, with the same agent test skipped. Those specs now cover:
  - the domain sections and remembered collapse;
  - tabs keeping their URLs;
  - page search;
  - the mega-menu;
  - an AUDITOR seeing only permitted workspaces and tabs;
  - an org PLATFORM_ADMIN never seeing install-operator tabs.

**P1.4.2 (commit `b1ec08e`).** The shared page kit is in `frontend/src/components/page/`: page header, stat cards, panels, filter bar, sortable and paged table, status badges, collapsible guidance and an offline banner. The Command Center was rebuilt on data the backend already serves:
- pending approvals, active incidents and unread critical signals;
- agents ranked by risk, blocked attempts, readiness and service-component status;
- the latest audit evidence.

Every figure links to its source page. It refreshes every minute, a deliberate choice explained in the second bullet below. The previous version showed fixed claims as if they were live: "Protected", "Enforced", a five-step pipeline that was always ticked, and "Good afternoon, Administrator". All of these were removed.

Two shell defects were found in a real browser and fixed:
- **The collapsed-sidebar mega-menu never appeared on screen.** It was clipped by the sidebar's `overflow: hidden`. This dates from P1, and its e2e test passed only because Playwright's visibility check ignores clipping. The panel is now fixed-positioned. A new hit test, which checks that the menu item is the topmost element at its own centre, fails without the fix and passes with it.
- **At 390 px every page scrolled sideways (417–437 px).** The top bar's action group was the cause; a phone rule was still hiding a class from before the user menu. `every-page.spec.ts` now checks every page for horizontal scroll at 390 px.

Two things were found in the e2e suite, and neither needs a product change:
- **Sign-in rate limit.** The admin sign-in limit is 20 requests per 5 minutes, and each sign-in costs two: the SSO lookup and the login. The new specs pushed the suite over it. The suite now signs the administrator in once, in Playwright global setup (`e2e/global-setup.ts`), and the admin specs reuse that session.
- **General request limit.** The per-client limit is 300 requests a minute, and the e2e backend recorded `RATE_LIMIT_EXCEEDED`. This came from page sweeps combined with the Command Center's 12 requests per load. The Command Center now refreshes once a minute, and the new specs do their checks on a single page load.

Neither rate limit was changed. A related note, not changed: `GET /tool-requests` counts against the `AGENT_ACTION` limit by client address even when an administrator calls it. Several pages and the Command Center poll it.

**P1.4.3 (commit `d57265b`).** All 11 Gate pages now have the shared header with page-wide actions, inline guidance, and the page gutter.
- **Rebuilt on the kit:** Secrets, Universal Controls, Capability Removal, Agent Adapters and Enterprise Identity, each with summary figures, filters, and sortable tables or record cards.
  - Native `confirm()` and `prompt()` dialogs became accessible confirmation dialogs; the rotate and revoke dialogs collect the new reference or the reason inline.
  - Enterprise Identity now shows its claim mappings, which the API already returned but no page displayed.
  - Universal Controls' authorize and kill request bodies are byte-for-byte the same as before.
- **Service Accounts** gains summaries, search and status filters, an "expiring soon" flag, and a confirmation before key rotation, which revokes the previous key.
- **Agents, Approvals, Tool Requests, Policies and Sandbox** keep their existing layouts and data handling. The Sandbox network badge is now read from `/sandbox/resources` instead of being fixed text.

Every permission redirect and request body is unchanged.

**Verification run for P1.4.2 and P1.4.3:**
- `npm run check`: lint clean; 158 unit tests pass, including 8 page-kit tests covering sorting, paging, empty state, relative time and status tones.
- Full Playwright suite: 58 passed, 1 skipped (no agents registered). The new tests cover:
  - Command Center figures matching the API and linking through;
  - the panels and their links;
  - the offline notice;
  - the mega-menu hit test;
  - no horizontal scroll at 390 px on every page.

  This run was on a tree that also contained the first four Watch pages of P1.4.4, then still in progress.
- Reviewed by screenshot at 1440 px and 390 px: the Command Center, the collapsed mega-menu, and every Gate page.
- Known gap, carried to P1.4.7: the policy-governance section at the foot of Policies still uses its older, larger type.

**P1.4.4 (commit `a1f5461`).** All nine Watch pages now share the page structure.
- **Rebuilt on the kit:** Threat Register, Simulation Lab, Endpoint Telemetry, Defensive Integrations and Observability, with summaries, filters, sortable tables or record cards, and guidance. Their native `confirm()` dialogs became confirmation dialogs.
- **Two silent failures fixed:** Simulation Lab and Endpoint Telemetry used to ignore a failed lab-state or uninstall request. They now report the error.
- **Header and guidance added:** Live Operations, Notifications, Authentication and Risk Center. Authentication and Risk Center had fixed "Live … telemetry" badges; these now show the real polling interval (15 s and 10 s) and the last-update time.

A screenshot review found that Live Operations' fixed, full-viewport background layer painted over the shell's tab bar and plan banner. The shell's bands now sit in their own stacking layer. A hit test can't detect this, because the layer has `pointer-events: none`. A spec assertion therefore guards only the stacking rule itself, and the screenshot review remains the real check.

**Verification run for P1.4.4:**
- `npm run check`: lint clean; 158 unit tests pass.
- Full Playwright suite: 59 passed, 1 skipped (no agents registered), including the 390 px horizontal-scroll check on every page.
- Reviewed by screenshot at 1440 px and 390 px: all nine Watch pages.

**P1.4.5 (commit `2f23ee6`).** All nine Respond and Evidence pages now share the page structure.
- **Rebuilt on the kit:** Incident Integrations, Communications, Execution Isolation, Isolation Operations, Audit Integrity and Security Exports. Native `confirm()` dialogs became confirmation dialogs.
- **Destination pages** (incident, notification and SIEM) now show every destination by default. A screenshot review had found that defaulting to "current" hid an archived destination straight after it was archived. The P4 D6 rule is that an archived destination stays listed as history, and the existing archive e2e test enforces it.
- **Data newly shown:** Communications shows each destination's critical bypass, and Security Exports shows its recent export queue. Both were already returned by the API.
- **Header and guidance added:** Incident Center, Audit Trail and Compliance Reports.

A phone-width review found content being cut off, not scrolled. The shell's content area clips its overflow, so the earlier page-level scroll check couldn't see it.
- **Isolation Operations** was widened by a long environment variable name in its guidance.
- **Settings** was widened to 843 px by a no-wrap API URL in a grid; this predates P1.4.

Long identifiers now wrap, the Settings value is constrained, and every-page also checks that nothing inside the content area is wider than it. That check fails on both pages without the fixes and passes with them.

**Verification run for P1.4.5:**
- `npm run check`: lint clean; 158 unit tests pass.
- Full Playwright suite: 59 passed, 1 skipped (no agents registered), including the archive test and the strengthened 390 px check on every page.
- Reviewed by screenshot at 1440 px and 390 px: all nine Respond and Evidence pages.

**P1.4.6 (commit `55eb8c2`).** The five Administration pages and the two investigation pages now share the page structure.
- **Rebuilt on the kit:** Account Security and Abuse Protection.
  - Revoking a session now needs confirmation, because the list includes the current device.
  - Abuse Protection warns when a category's enforcement is switched off.
- **Header, summaries and guidance added:** Getting Started, Settings and Team & Access.
  - Team's fixed "Enforced roles: 3" is now counted from the role list.
  - Install operators are counted, with a nudge to keep two, so one can reset the other's password.
- **Investigation pages** for agents and requests gain the shared header, with their back links and export as page actions.

Two defects were found and fixed:
- **Agent investigation error for legacy identities.** An agent with a legacy identity showed "Something went wrong: Identity not found", because the page requested credential history for an agent that has no scoped credential. This predates P1.4. The request is now skipped and the panel says there is no credential to manage. A new e2e test opens a real registered agent's investigation and waits for the separately loaded panel to settle. It fails without the fix and passes with it.
- **Getting Started summary.** The "next step" card showed the step's whole sentence in the large figure font. It now shows a count of remaining steps, with the next step as its hint.

**Verification run for P1.4.6:**
- `npm run check`: lint clean; 158 unit tests pass.
- Full Playwright suite: 60 passed, 1 skipped (no agents registered).
- Reviewed by screenshot at 1440 px and 390 px: all five Administration pages and the agent investigation page.

**P1.4.7 acceptance (commit `4bdaefc`).** The policy change-control and report-governance panels moved onto the kit, which closes the gap carried from P1.4.3. The policy panel's actions used to throw on a server error with no handler, so a rejected draft, approval or emergency change failed silently. Each change now reports its outcome. No native `confirm()` or `prompt()` dialog remains in the console.

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Navigation by product domain | **Met** | 12 workspaces in 5 expandable domains; 13 sidebar entries, down from 35. Route-inventory unit tests; `workspace-navigation.spec.ts`. |
| 2 | Page-level tabs and contextual actions | **Met** | Every workspace with 2+ permitted pages has deep-linkable tabs. Page actions sit in each page header, and record actions in each row or card. |
| 3 | Role-based visibility retained | **Met** | Tabs, workspaces and search use the existing `navigationPermission()`. New e2e tests: an AUDITOR sees only permitted workspaces and tabs, and sees records without the actions its role can't take (with an administrator control check); an org PLATFORM_ADMIN never sees install-operator tabs. |
| 4 | Rich operational dashboard, real data only | **Met** | Command Center figures come from existing APIs and link to their source pages. Fixed claims were removed. `command-center.spec.ts`. |
| 5 | Every page professionally structured | **Met** | All 34 pages and both investigation pages have the shared header, guidance and states. Thin pages are rebuilt with summaries, filters and sortable or paged tables. |
| 6 | No functionality lost | **Met** | Every pre-redesign URL is still routed (unit test). Request bodies are unchanged. The suite's existing behavioural tests pass unmodified, apart from the selector updates recorded under P1.4.1. |
| 7 | Security boundaries unchanged | **Met** | `git diff 2c4b3d1 HEAD` is empty for `backend/`, `scripts/`, `deployment/`, `frontend/src/api`, `frontend/src/context`, `frontend/src/routes` and `usePermission.ts`. No rate limit was changed; the e2e suite was adapted to the limits instead. |
| 8 | Accessibility and mobile | **Met** (light theme hidden by owner decision) | Keyboard operation of sections and tabs is tested. Dialogs trap and restore focus. Every page is checked at 390 px for sideways scroll and clipped content. Reduced motion disables the stat-card lift. **Open: light theme.** The shell and many older page stylesheets hard-code dark colours, so with the light toggle on some labels become unreadable (seen on the Command Center and Policies). This predates P1.4: P1 deferred converging colours onto tokens. |
| 9 | Verification bar | **Met** | Below. |

**Open item needing an owner decision: the light theme.** Two options:
- **(a) Hide the light toggle until the colours converge.** This is small and immediate, and the console stays dark-only.
- **(b) Converge the shell and the roughly 40 page stylesheets onto the existing tokens.** This is a sizable piece of work, to be scheduled as its own task.

**Owner decision (2026-10-15): option (a).** The appearance toggle was removed and the console is dark-only (commit `1a30559`). An e2e test checks that the toggle is gone and the page renders dark. The light tokens are kept in `tokens.css`. Converging every stylesheet onto them (option (b)) remains a possible later task; it is not scheduled.

**Verification run after the decision:** `npm run check` clean (158 unit tests); full Playwright suite 64 passed, 1 skipped.

**Verification run for P1.4.7:**
- `npm run check`: lint clean; 158 unit tests pass.
- Full Playwright suite: 63 passed, 1 skipped (no agents registered).
- Screenshot review at 1440 px and 390 px across every workspace during P1.4.2–P1.4.6.
- Light-theme screenshots of the Command Center, Threat Register and Policies, which show the open item.

---

## P2 — Tenant and commercial platform foundation

**Status: Verified — all six sub-phases complete (organizations and membership, the tenant-scoping sweep, entitlements, billing and licensing, organization lifecycle, and the acceptance suite).** Commercial and policy values (plan limits, grace and retention lengths, a live billing provider) remain business decisions, listed in each spec. Michael approved beginning this workstream ("Phase C"). The Alembic baseline migration this phase was blocked on is now done (see above), so P2 is unblocked at the infrastructure level. Split into 6 reviewable sub-phases mirroring P1's cadence - each gets its own explicit go-ahead before work starts. Two decisions made up front: (1) one administrator account can belong to multiple organizations, not one-org-per-account; (2) billing is a provider-neutral interface plus a mock/sandbox implementation only (P2.4), no live payment processor.

| Sub-phase | Status | Evidence |
|---|---|---|
| P2.1 — Organizations, membership, invitations, auth-chain plumbing, tenant-scoping safety net | **Verified** | New `organizations`/`org_memberships`/`org_invitations` tables (SQLite via `organizations.py`, PostgreSQL via a new Alembic revision verified against a real rehearsal container in both directions). Default org seeded, every pre-existing administrator backfilled with role carried over verbatim. Two orthogonal roles per membership (operational_role reuses the existing PLATFORM_ADMIN/SECURITY_ANALYST/AUDITOR enum unchanged; governance_role OWNER/BILLING_ADMIN/MEMBER is new) rather than a collapsed enum - zero changes needed to any existing permission-check function. `admin_auth.validate_session()` now resolves role from the session's active org membership when one exists, falling back to the legacy global role otherwise - every pre-P2.1 test fixture keeps working unchanged. New `POST /auth/active-org` switches without re-authenticating; `UserMenu` grows an org switcher (hidden when there is only one org). The structural safety net this whole phase's biggest risk depends on - `tenant_guard.py`, routing every query through both database backends - is built and proven now, while empty, rather than after P2.2's real per-table sweep already depends on it. Commit `0331616`. |
| P2.2 — Tenant-scoping sweep (org_id on ~60 resource tables + the 7 singleton configs) | **Verified — complete: batches 1-12, 14-18, agent batches A-C, the policy batch and the final batch (57 tables migrated: simulation_runs, capability_removals, capability_removal_steps, universal_capability_controls, universal_control_events, adapter_configs, adapter_events, browser_connectors, defensive_response_plans, endpoint_collectors, endpoint_telemetry_events, service_accounts, service_account_keys, service_account_events, threat_register, threat_register_history, isolation_config, isolation_executions, isolation_operations_config, isolated_workspaces, quarantined_artifacts, simulation_config, secret_references, secret_events, report_schedules, incident_postmortems, export_destinations, export_queue, notification_destinations, notification_templates, notification_deliveries, incident_destinations, external_incident_records, outbound_delivery_evidence, agent_identities, agent_credential_events, audit_events, tool_requests, approval_events, execution_events, security_alerts, alert_notes, security_notifications, notification_retention_policy, notification_retention_events, notification_retention_tombstones, policy_versions, policy_change_events, policy_test_cases, policy_emergency_controls, policy_emergency_events, policy_adapters, policy_rollouts, policy_integration_events, compliance_reports, expiring_approval_links, callback_evidence; 19 tables reclassified as global; `PENDING_TENANT_SCOPING` is empty; all 7 singleton configs resolved - 5 reshaped per org (isolation_config, isolation_operations_config, simulation_config, notification_retention_policy, policy_emergency_controls), 2 install-wide and operator-only (observability_config, audit_retention_config))** | `tenant_guard.PENDING_TENANT_SCOPING` now lists every remaining table explicitly (an honest "not yet decided," distinct from "deliberately global") so the coverage check can never silently miss one. Real finding batch 1: `universal_capability_controls` isn't an ordinary resource table - 5 fixed rows keyed by `capability` alone - so adding org_id required reshaping its primary key to `(capability, org_id)`, not a plain `ADD COLUMN`; the same applies to the 7 singleton configs, flagged in `PENDING_TENANT_SCOPING`'s comments ahead of whoever tackles them. Two real bugs caught by running the full suite, not just new tests: `configure_control()` wasn't seeding a new org's rows before updating them (silent no-op update); the tenant_guard itself false-positived on `ALTER TABLE ... RENAME TO`/`DROP TABLE` (pure schema DDL, no column list to check) - this one crashed the real startup `lifespan()`, caught via `TestClient`-based tests failing, not the new tests for this batch. Real finding batch 2: `abuse_protection.py`'s three tables (rate_limit_policies/_counters, abuse_events) were reclassified as **global, not org-scoped** - they are read/written from a global HTTP middleware before any session or org is resolved (including on `/auth/login` itself), throttling by IP address, not by org; scoping them would have let an attacker bypass the whole-install rate limit by spreading requests across org contexts - a real security regression, not a tenancy gap. `adapter_configs` had the same fixed-row-set shape as `universal_capability_controls` and got the same composite-key reshape; `adapter_events`/`adapter_configs` also exposed an architectural boundary - the agent-facing adapter-request route has no org concept yet (agents aren't tenant-scoped until a later batch), using the same documented default-org fallback already established for the legacy admin PIN. Batch 3 (browser_connectors, defensive_response_plans, endpoint_collectors, endpoint_telemetry_events): all four use UUID-generated primary keys, not fixed named rows, so a plain backfilled `ADD COLUMN` sufficed - no composite-key reshape this batch. Both source modules used positional `INSERT INTO table VALUES(...)` throughout; converted every one to named-column form so tenant_guard's text-based check can verify the `org_id` literal. `endpoint_telemetry_events` has no live call site writing to it anywhere in the codebase today (confirmed by search) - the column was still added so the table could leave the pending bucket with an honest decision recorded rather than sitting undecided indefinitely. All batch-3 call sites are administrator-authenticated routes, so no agent-context fallback was needed. Batch 4 (service_accounts, service_account_keys, service_account_events): a different fixed-shape problem than batches 1-2's - not fixed named rows, but a plain `UNIQUE(name)` constraint (case-insensitive) that would let two orgs collide on the same human-chosen account name; reshaped to `UNIQUE(name, org_id)` via the same rebuild dance used for a composite primary key. The bearer-key verification route (`authenticate_service_key`, `POST /service-accounts/verify`) deliberately takes no org_id parameter - it resolves identity first by a globally-unique random `key_prefix`, then reads org_id back off the row, the same shape as admin_auth's own session-token lookups. Batch 5 (threat_register, threat_register_history): threat_register had the same fixed-row-set shape as batches 1-2 - 30 fixed threat_id rows seeded from a tuple of roadmap-mandated threat categories - so it got the same composite-key reshape; threat_register_history needed only a plain ADD COLUMN. `initialize_threat_register(org_id=...)` now seeds a brand-new org's full 30-threat catalog on first access, mirroring batch 1's per-org seeding pattern, and the existing "never overwrite a reviewer's edit" upgrade logic is now scoped per org. Batch 6 (isolation_config, isolation_executions): isolation_config is the first of the 7 singleton `CHECK(config_id=1)` tables to actually land - same composite-key reshape, `CHECK` constraint left untouched since it still correctly allows exactly one row per org. Real finding: `emergency_terminate()` originally killed every RUNNING sandbox container on the host regardless of org - a cross-tenant denial-of-service risk, not just a tenancy gap - fixed by scoping it (and its in-memory fallback registry) by org_id, so one org's emergency stop can never touch another org's container. Batch 7 (isolation_operations_config, isolated_workspaces, quarantined_artifacts): isolation_operations_config is the second singleton to land, same reshape. `isolated_workspaces.agent_name` had the same global-UNIQUE problem as service_accounts in batch 4, reshaped to `UNIQUE(agent_name, org_id)` - and this one had a **filesystem** consequence beyond the database: the on-disk workspace path was `workspace_root/<agent_name>`, so two orgs with the same agent name would have shared a directory; fixed by nesting paths under an org_id subdirectory so filesystem isolation now matches database isolation. Batch 8 (simulation_config): the third singleton to land, same reshape - and the table explicitly deferred back in batch 1, when `simulation_runs` was scoped but its enablement switch was deliberately left global pending its own batch; `update_simulation_lab()` in `api.py` was the one remaining call site anywhere in the codebase still calling a simulations function without an org_id, fixed here. Batch 9 (observability_config, observability_spans, observability_correlations): traced before assuming they needed org_id, the same scrutiny abuse_protection got in batch 2, and found the same answer - **reclassified as global, not org-scoped**. `observe_request()` is a global pre-auth HTTP middleware wrapping every request including `/auth/login`, before any session or org is resolved; the overwhelming majority of spans could never be attributed to an org in the first place, and the tracing/metrics/retention config is an install-wide operational switch a platform operator needs visibility across every org for, not a per-org setting. Zero schema change - a pure registry move, same as abuse_protection's. Batch 10 (authentication_events, oidc_login_attempts): resolved both tables flagged since P2.1 for the same scrutiny, and both are also **global, not org-scoped** - `authentication_events` logs agent identity-verification attempts before any session exists, and agents aren't tenant-scoped at all yet; `oidc_login_attempts` is single-use OAuth2 state/nonce/PKCE data that exists specifically because no administrator session (and therefore no org) is resolvable yet during an SSO redirect round-trip. Zero schema change. Batch 11 (secret_references, secret_events): secret_references had the same uniqueness problem as service_accounts (batch 4) and isolated_workspaces (batch 7) - `name` globally UNIQUE, reshaped to `UNIQUE(name, org_id)`; `emergency_revoke_all()` originally revoked every ACTIVE secret for a provider regardless of org, scoped by org_id for the same cross-tenant availability reason as `emergency_terminate()` in batch 6. Caught and fixed a signature-ordering mistake before it shipped (inserting `org_id` before the existing `provider` parameter silently broke a pre-existing positional caller - reordered so `org_id` comes after `provider`). **Real regression found and fixed while running the full suite**: `compliance_reports.py`'s `_privileged_activity()` ran a generic query against `secret_events`/`service_account_events`/`policy_change_events` with no org_id predicate at all - since `service_account_events` has carried org_id since batch 4, this had been silently crashing with `TenantScopingError` in any real deployment that ever created a service account, uncaught by the existing suite because its isolated fixture database never created that table before calling `build_evidence()`. Fixed by checking `tenant_guard.ORG_SCOPED_TABLES` membership per table and filtering only the columns that actually exist, defaulting to `DEFAULT_ORG_ID` since `compliance_reports` itself isn't tenant-scoped yet (its own future batch, given it also pulls from audit_events/security_alerts/policy_versions). Batch 12 (report_schedules, incident_postmortems): `run_due_schedules()` is a background worker with no HTTP/admin context - its claim query is deliberately cross-org (one process services every org's due schedules per pass, documented with an explanatory SQL comment so tenant_guard sees why), but every subsequent read/update of a claimed row is scoped by that row's own org_id and the generated report is built with that org's org_id. Hit tenant_guard's existing, deliberate `ALTER TABLE ADD COLUMN` check along the way: report_schedules added several legacy columns via an unconditional loop that also ran against freshly created tables (unlike every other batch's modules) - fixed by moving them into the `CREATE TABLE` statement itself. **Another real regression found and fixed while running the full suite**, the same shape as batch 11's: `retention_report()`'s generic per-table `COUNT(*)` loop queried `quarantined_artifacts` (org-scoped since batch 7) with no org_id predicate, silently crashing in any deployment that had ever created an isolated workspace - fixed the same way as `compliance_reports`'s bug. Batch 13 was not a table migration: surveying `policy_control.py`/`policy_integrations.py` found that the live enforcement engine never reads `policy_versions` directly - `api.py`'s policy-activation code copies whichever policy was just approved into two global, shared, in-process dicts (`main.permissions`/`main.risk_weights`) that every real enforcement decision actually reads. Adding org_id to the database rows alone would have been actively misleading (each org would appear to have an isolated policy while every org's real enforcement still read one shared in-process copy) - documented as its own dedicated future batch rather than rushed. Batch 14 (`identity_providers`, `identity_role_mappings`, `workload_identities`, `privilege_elevations`, `break_glass_activations`, `enterprise_identity_events`): all six surveyed individually and all six are global infrastructure - enterprise SSO configuration and certificate-based agent authentication are both pre-auth (same shape as batch 10's findings), and privilege-elevation/break-glass are administrator-level governance requests with no org tie-in anywhere in the code (confirmed by reading every call site). Zero schema change for batch 14, same as batches 2/9/10's reclassifications. Batch 15 (`export_destinations`, `export_queue` - `security_exports.py`): `export_destinations.name` had the same global-UNIQUE problem as batches 4/11, reshaped to `UNIQUE(name, org_id)`. **Real finding**: unlike those tables, `export_destinations` is the target of a foreign key (`export_queue.destination_id`), and SQLite (3.26+) rewrites inbound foreign keys on `ALTER TABLE ... RENAME` - the rename-aside-then-drop dance used for `service_accounts` would have left `export_queue` referencing a dropped `export_destinations_pre_org` table (reproduced directly). Batch 15 instead builds the new table under a temporary name, copies, drops the old one and renames the new one into place, leaving the FK text untouched; a legacy-upgrade test asserts the FK still names `export_destinations` and passes `PRAGMA foreign_key_check`. The same latent issue already exists in batch 4's `service_accounts` rebuild on any SQLite database that predates it (`service_account_keys`' FK now names a dropped table) - harmless today because SQLite FK enforcement is off on every connection except `policy_control`'s, but recorded here rather than silently fixed inside an unrelated batch. `enqueue_export()` now resolves the destination within the caller's org, so one org can no longer queue its events for delivery to another org's SIEM by `destination_id`. `process_queue()` is a cross-org background worker like batch 12's `run_due_schedules()`: the claim stays deliberately unfiltered (documented in SQL), but it now joins a queued export only to a destination of the *same* org, and every later write is scoped by the claimed row's own org_id. Batch 16 (`notification_destinations`, `notification_templates`, `notification_deliveries` - `notification_delivery.py`): both config tables had a globally UNIQUE `name`, reshaped to `UNIQUE(name, org_id)` with batch 15's build-new/drop/rename-into-place rebuild (also tolerating a legacy table that predates `max_attempts`); `notification_deliveries` needed only a plain ADD COLUMN. `queue_notification()` now resolves both the destination *and* the template within the caller's org (otherwise one org could render another org's template), and `process_deliveries()` got the same cross-org-claim/same-org-join treatment as batch 15's worker. **Real pre-existing bug found and fixed**: `outbound_worker.py` passed `notification_delivery.real_sender` - the raw HTTPS transport - as `run_due_schedules()`'s notifier, so every scheduled report-ready notification in production was POSTed to its `notify_destination_id` (`ndst_...`) as if it were a URL, rejected (`Outbound requests require an https:// destination`), and silently recorded as `NOTIFY_FAILED` evidence - scheduled-report notifications had never actually been delivered. The worker now passes `queue_notification` (the governed path: destination lookup, severity filter, quiet hours, dedupe), and `run_due_schedules()` passes the schedule's own `org_id`, so the destination is resolved within that schedule's org - fixed here because scoping required touching this exact call anyway; a wiring regression test pins it. Batch 17 (`incident_destinations`, `external_incident_records` - `incident_integrations.py`): `incident_destinations` had the same globally UNIQUE `name`, reshaped to `UNIQUE(name, org_id)` with the same rebuild (tolerating a pre-`max_attempts` table); `external_incident_records` needed only a plain ADD COLUMN. `queue_incident()` now resolves the destination within the caller's org - otherwise one org could open tickets in another org's Jira/ServiceNow project, using that org's credential, by `destination_id` - and `process_incidents()` got the same cross-org-claim/same-org-join treatment. `expiring_approval_links` and `callback_evidence` live in the same module but stay pending: approval links act on `tool_requests` (still pending), and callbacks are not yet tied to a record's org. Batch 18 (`outbound_delivery_evidence` - `outbound_delivery.py`): the shared evidence log gets the registry's one deliberately **nullable** `org_id` - NULL marks install-level events with no tenant (enterprise SSO login handshakes, SSRF-allowlist changes) instead of misattributing them to `org_default`; legacy rows from every other subsystem are backfilled to `org_default`. `record_evidence()` now takes `org_id` as a required keyword with no default, so no call site can silently skip it; workers pass the claimed row's own org. **Findings recorded, not changed:** (1) `outbound_allowed_private_hosts` stayed pending (since resolved by the install-operator row below, which reclassified it global) - it is an install-wide SSRF control, so per-org scoping is wrong, but it can't honestly be called global either, because its write endpoints are gated by `require_platform_admin()` and PLATFORM_ADMIN now resolves from the caller's *org* membership, so any org's admin can change an SSRF control that applies to every tenant. Fixing that needs an install-level operator role that doesn't exist yet; `observability_config` (global since batch 9) has the same latent write-gate gap. (2) The three `notification_retention_*` tables stay pending: retention cleanup deletes from `security_notifications` (derived from `security_alerts`, both still unscoped), so a per-org policy would decide deletions in a shared inbox - they must move together with those two tables. **Agent batch A** (`agent_identities`, `agent_credential_events` - `database.py`/`main.py`): **real cross-tenant takeover found and closed** - credential rotate/revoke and scope changes looked agents up by name alone, so one org's PLATFORM_ADMIN could rotate another org's agent credential and *receive the new credential*. Every agent now belongs to one org; `agent_name` stays a global namespace (agents authenticate by name before any org exists), so `get_agent_identity()` is the one documented unfiltered lookup and an agent's org is a property of its identity. Two independent layers - `api.require_agent_in_org()` on every admin `/agents` route (another org's agent is a plain 404) and `org_id` as a required keyword on every database mutation/history read; a mutation check confirmed each layer alone blocks the takeover. Names another org owns are refused as "unavailable" without disclosing the owner. The adapter route now attributes agent requests to the agent's own org (replacing the default-org placeholder); global search filters agents and their tool requests by org. **Agent batch B** (`audit_events`, `tool_requests`, `approval_events`, `execution_events`): every piece of agent evidence is stamped with the agent's org at write time, never from caller input. Closed: one org's admin approving/denying another org's pending tool request; every org's compliance report, live stream, audit view, approval queue, governance report, investigations and search including all orgs' agent activity (the unified timeline is now org-scoped, stamps each event's `org_id`, filters the global authentication events by agent ownership, and reserves an `ALL_ORGS` object sentinel for install-level alert derivation); and **any org's PLATFORM_ADMIN being able to apply install-wide audit retention and delete every org's audit history** - the four audit-integrity tables are reclassified global and all six `/audit-integrity` routes now require install_operator. **Real pre-existing bug fixed:** `GET /tool-requests/{id}`, the agent-facing route both SDKs call, read a key the lookup never returned and failed with a 500 for every existing request; it now authenticates the agent first, looks the request up in the agent's own org, then enforces scope. **Agent batch C** (`security_alerts`, `alert_notes`, `security_notifications`, and the three notification-retention tables batch 18 had to leave pending): alerts belong to the org of the evidence they came from, notes and notifications to their alert's org. Closed: every org's admins seeing, dismissing and annotating every org's alerts, and every inbox showing every org's alerts; and the notification-retention singleton letting one org's admin set the retention that deleted every org's notifications (reshaped to a composite `(id, org_id)` key). Design decision: `org_id` is deliberately nullable on these tables - NULL marks install-level alerts from evidence that belongs to no tenant (e.g. repeated authentication failures against an agent name that exists in no org); install operators see them alongside their org's, so a single-tenant install keeps exactly the visibility it had. **Policy batch** (all eight policy tables - the change batch 13 deferred): enforcement used to read two process-wide dicts that policy approval overwrote, so one org's approved policy became every org's enforcement; `main.evaluate_action()` now reads the agent's own org's published policy, emergency controls and active rollout from the database on every decision, with each org seeded on first use from the install defaults. Also closed: one org's emergency "global deny" stopping every org's agents (emergency controls are per org), one org's active rollout applying to every org's agents, cross-org access to policy versions/history/tests/adapters/rollouts/bundles, and the unauthenticated `GET /permissions`, which would have exposed every org's rules (it now requires an administrator and returns exactly what is enforced for their org). **Real pre-existing bug fixed:** nothing ever loaded the published policy at startup, so every restart silently reverted enforcement to the built-in rules while `/permissions` still reported the approved version - fixed by construction, with a regression test. Reshapes: `policy_versions` UNIQUE(version_number) -> UNIQUE(version_number, org_id) (SQLite rebuild without FK enforcement, references intact); `policy_emergency_controls` and `policy_adapters` to composite keys. **Final batch** (`compliance_reports`, `expiring_approval_links`, `callback_evidence`): `PENDING_TENANT_SCOPING` is now empty - every table is org-scoped or deliberately global, and the CI coverage check enforces it for every future table. **Real pre-existing bug fixed:** the compliance-report generate route never passed the administrator's org, so every API-generated report was built from the default org's evidence whichever org asked, and any org could read or export any org's report. Approval links can now only be issued for, and consumed by, the org of the request they decide. Follow-up resolved: `backend/tests/conftest.py` now isolates the whole test session from `backend/data`, which surfaced and fixed two tests that had been touching the real database. PostgreSQL migrations verified against a real rehearsal container in both directions for all nineteen schema-changing batches (batches 9, 10, 13 and 14 needed none), including explicit same-name/same-key-different-org inserts for batches 4 through 12 and 15 through 17 proving each reshape actually works, not just that it applies cleanly. Commits `cc0dadc`, `0ab7ca9`, `7bfd90d`, `a3d809b`, `3f2f150`, `d26e94c`, `8e21bfa`, `5d72c02`, `65289e0`, `dede3ce`, `f6fbd0a`, `1e9e2fb`, `650028c`, `706eabd`, `5a1fc57`, `8e1ab32`, `879fab8`, `513aab7`, `bb7b26b`, `61b848c`, `bcc61a1`, `eace97b`, `619515d`. |
| P2.2a — Install-operator role (closes a cross-tenant account-takeover chain) | **Verified** | **Real privilege-escalation chain found and closed.** Install-wide controls were gated on PLATFORM_ADMIN, which P2.1 made per-org, while `POST /organizations` let *any* authenticated administrator - even an AUDITOR - create an org and become its PLATFORM_ADMIN. From there the `/administrators` routes allowed listing every account, changing anyone's role or status, and resetting any administrator's password, including other orgs' owners. New global account flag `administrators.install_operator` (like `break_glass`, grantable by no org-level action) and `api.require_install_operator()` on all 21 install-wide routes: org creation, all five `/administrators` routes, observability, the SSRF allowlist, abuse protection, and enterprise-identity configuration. No lockout on upgrade: existing PLATFORM_ADMINs are backfilled as operators once (re-initialization never re-grants a demoted one); the first-run setup admin, bootstrap admin and dev-only legacy PIN are operators; every other new account defaults to non-operator; the last active operator cannot be demoted or disabled. With a real gate in place, `outbound_allowed_private_hosts` moved from pending to GLOBAL. Frontend: `/team`, `/observability`, `/enterprise-identity` and `/abuse-protection` are shown and reachable only for operators; tenant-scoped admin pages stay on the per-org role. The Team page grants and shows operator status (follow-up commit). **Follow-up:** org self-signup, if wanted, belongs to P2.5 onboarding rather than reopening `POST /organizations`. Commit `752a054`. |
| P2.3 — Entitlements, plans, trials, usage meters | **Engine verified — commercial values pending** | Backend-enforced engine (`backend/app/entitlements.py`, specified in `docs/metering-and-entitlements.md`): Foundation/Enterprise/Dedicated plans as data, plus Unassigned - every existing and new org starts Unassigned, which enforces nothing (no behaviour change) until an install operator assigns a plan. Mandatory protections can never be gated (disjoint from gateable features by construction and test; overrides cannot target them). Meters: agents, monthly controlled requests, monthly deliveries, integrations - members are never metered. Hard limits refuse only new growth; soft limits are reported; no plan hard-limits controlled requests or deliveries. Trial expiry or suspension pauses growth while existing agents, evidence, exports, emergency controls, credential revocation and offboarding keep working. Overrides are operator-only, reasoned, expiring, revocable and audited. Enforced at agent registration, SIEM/incident/notification destination creation and report schedules; refusals are 403 `ENTITLEMENT`. Settings shows a read-only Plan & usage panel. **Still open (business decisions, listed in the spec):** the real limit values, whether new orgs start on an automatic trial, storage metering, and the link to billing (P2.4). Verification: backend 602 passed (11 new entitlement tests; mutation check fails 7), PostgreSQL migration rehearsed in both directions with the engine exercised end to end, frontend check clean (115 unit tests), Playwright 45 passed / 1 skipped. Commit `0317feb`. |
| P2.4 — Billing (provider-neutral interface, mock provider, billing-event evidence, license leases) | **Verified — commercial values pending** | Specified in `docs/billing-and-licensing.md`. `backend/app/billing.py`: a `BillingProvider` contract with one implementation, `MockBillingProvider` (a sandbox, refused when `GREYGUARD_ENV=production`), and no live processor. GreyGuard stores no card data: only opaque provider references and an allowlist of normalized event fields, so anything else in a payload, card numbers included, is dropped on parse. Webhooks are HMAC-SHA256 signed with a 5-minute replay window, idempotent per provider event ID, serialized per org, and acknowledge unknown subscriptions without disclosure. Billing-event evidence is a per-org hash chain (`verify_billing_evidence()`), with `(org_id, previous_hash)` unique so a fork cannot be stored. A payment failure starts a 14-day grace period that retries cannot extend. When it lapses, or a subscription is cancelled, the org enters P2.3's restricted mode: growth pauses, while existing agents, evidence, export, emergency controls and offboarding stay available. A successful payment recovers the org at once. Billing state is an *input* to restricted mode, never a write to the operator-set plan status (new `restriction_reasons`), so a payment can never lift an operator's suspension. Plans stay install-operator decisions: `POST /billing/{org_id}/link` opens the subscription and assigns the plan through the audited entitlements engine. Billing access follows the governance role (OWNER/BILLING_ADMIN), whatever the operational role. `backend/app/licensing.py`: Ed25519-signed self-hosted leases (vendor tool `scripts/issue_license_lease.py`) bound to a random per-install ID, VALID → GRACE → LAPSED, with LAPSED or missing restricting every org on the install; recovery is installing a newer lease. Older-lease replay is refused, the stored token is re-verified on every read, and a clock high-water mark stops a wound-back clock reviving a lease. Off unless `GREYGUARD_LICENSE_REQUIRED`. Both features are off by default, so there is no behaviour change. Settings shows billing state and the restriction cause. Open decisions (live provider, grace length, self-serve checkout, lease terms) are listed in the spec. |
| P2.5 — Organization lifecycle (export, deletion, onboarding, offboarding) | **Verified — policy values pending** | Specified in `docs/organization-lifecycle.md`; `backend/app/org_lifecycle.py`. The lifecycle is ACTIVE → OFFBOARDING → DELETED. **Onboarding:** an install operator creates the customer org without joining it, invites its first owner and optionally assigns a plan or trial. A 9-item readiness checklist is computed from real data (owner, separation of duties, auditor, MFA for everyone, plan, policy baseline, first agent, integration, export tested). **Export:** owners or operators can export at any point short of deletion. The bundle holds every row of every org-scoped table with credential material redacted, plus per-table digests; a test forces every secret-looking schema column to have a redact-or-evidence decision. **Offboarding:** owner or operator, with a reason and a retention period. It marks the org first, then revokes agent credentials and service accounts, disables integrations and report schedules, revokes invitations and cancels billing, recording each result. The org becomes read-only in the RBAC middleware apart from export, evidence and every emergency or revocation control, and growth is refused (`ORG_OFFBOARDING`). An operator can cancel it. **Deletion:** install operator only, after retention, with the slug typed, never under a legal hold. One transaction clears every org-scoped table (foreign-key children first, checked against the live schema), memberships and invitations, then the org's files and runtime state go. The org's audit events are recorded as erasures so the install-wide integrity chain still verifies, and a self-hashed deletion certificate is kept in install-level tables that outlive the org. **Two real defects found and fixed along the way:** (1) a cross-tenant disclosure: every compliance report's `administrator_roster` listed every administrator on the install (emails, names, roles, last sign-in), not the org's members, a P2.2 miss found by the export isolation test; (2) audit retention deletion made every later integrity verification report tampering. Authorized deletions are now recorded erasures, and verification reports `records_erased`. |
| P2.6 — Capstone: cross-tenant isolation + billing-failure safety acceptance suite | **Verified** | `backend/tests/test_tenant_acceptance.py`, described in `docs/testing-and-assurance.md`. It is generated from the app's own route table and OpenAPI schema, so new routes are covered automatically. **Read sweep:** an attacker org calls every GET route with the victims' identifiers (a populated tenant *and* the default org) and with its own; no victim identifier may come back. **Write sweep:** every POST/PUT/DELETE/PATCH route with schema-generated bodies; every victim row must be byte-for-byte unchanged, with no 5xx and a minimum number of calls reaching handlers. **Failure matrix:** for all 7 restriction reasons, each of the 8 mandatory protections is checked over HTTP and growth is refused; a test keeps the checks equal to `MANDATORY_PROTECTIONS`. **Three real defects found and fixed:** (1) secret redaction over JSON responses ran on through closing quotes, so any evidence containing text like `password=…` made its response invalid JSON, which broke evidence views and exports (a mandatory protection) whenever an agent request held such text; (2) every non-default org's adapters were seeded with no allowed actions, so they could never be configured and testing one crashed with a 500 (fixed seed, a startup repair for existing orgs, and a guarded test route); (3) agent reset (basic recovery) was blocked while offboarding and is now allowed. |

**Verification run for P2.1:** full existing backend suite (435 passed, 4 skipped, 0 failed) confirms zero regressions; 29 new backend tests (organizations, membership governance, invitations, active-org switching, the tenant-guard mechanism) all pass; frontend tsc/lint/113 unit tests/build all clean; full Playwright suite 43/44 passed (1 skipped, no agents registered in this environment) including a new `org-switcher.spec.ts` that creates a real second organization via the API and confirms switching in a real browser; the PostgreSQL migration verified against a real rehearsal container in both directions (upgrade with existing administrators present, full downgrade, re-upgrade).

**Verification run for P2.2 batch 1:** full backend suite 468 passed, 4 skipped, 0 failed (zero regressions, confirmed only after fixing the lifespan-crashing tenant_guard false positive described above - the first run of this suite genuinely failed for real reasons); frontend tsc/build clean (no frontend changes this batch); full Playwright suite 44/45 passed, 1 skipped, run in smaller per-file batches due to this machine's memory constraints - including the three pages whose backend modules this batch rewrote; PostgreSQL migration verified against a real rehearsal container in both directions (the composite-key reshape included).

**Verification run for P2.2 batch 2:** full backend suite 469 passed, 4 skipped, 0 failed; frontend tsc/build clean (no frontend changes this batch); PostgreSQL migration verified against a real rehearsal container in both directions. Playwright: security-smoke, org-switcher, pwa and permission-gating specs all confirmed passing (each flaky-then-passed once under this machine's sustained memory pressure, never an assertion failure - always a page-load timeout before the app reached a testable state); `every-page.spec.ts` could not complete after five attempts (including a narrowed two-page run) due to sustained memory exhaustion on this machine - disclosed rather than silently skipped. This batch makes zero frontend code changes and the two pages its backend changes reach were confirmed working end-to-end in batch 1's full e2e run with no frontend changes since.

**Verification run for P2.2 batch 3:** full backend suite 489 passed, 4 skipped, 0 failed; frontend tsc/build clean (no frontend changes this batch); PostgreSQL migration verified against a real rehearsal container in both directions (seeded pre-existing rows in all four tables, confirmed backfill to `org_default` and `NOT NULL`, full downgrade restored the exact original schema, re-upgrade clean). Full Playwright suite this time ran clean on the first attempt with zero flakes: security-smoke + permission-gating (4 passed, 1 skipped - no agents registered in this environment) and the full `every-page.spec.ts` (36/36 passed), including both pages this batch's backend changes reach (`/endpoint-telemetry`, `/defensive-integrations`) - closing the disclosed e2e gap from batch 2's report.

**Verification run for P2.2 batch 4:** full backend suite 490 passed, 4 skipped, 0 failed; frontend tsc/build clean (no frontend changes this batch); PostgreSQL migration verified against a real rehearsal container in both directions - seeded pre-existing rows, confirmed backfill to `org_default`, inserted a second row with an identical `name` under a different `org_id` to prove the reshaped constraint actually permits what it's meant to (not just that the migration applies without erroring), removed it before downgrading, confirmed downgrade restores the exact original global-unique constraint, clean re-upgrade. Full Playwright suite clean with zero flakes: security-smoke + permission-gating (4 passed, 1 skipped) and every-page.spec.ts (36/36 passed), including the service-accounts-exercising permission-gating test.

**Verification run for P2.2 batch 5:** full backend suite 491 passed, 4 skipped, 0 failed; frontend tsc/build clean (no frontend changes this batch); PostgreSQL migration verified against a real rehearsal container in both directions - seeded a pre-existing row, confirmed backfill to `org_default`, inserted a second row with the identical fixed `threat_id` under a different `org_id` to prove the reshaped composite key actually permits what it's meant to, removed it before downgrading, confirmed downgrade restores the exact original single-column primary key, clean re-upgrade. Full Playwright suite clean with zero flakes: security-smoke + permission-gating (4 passed, 1 skipped) and every-page.spec.ts (36/36 passed), including `/threat-register`.

**Verification run for P2.2 batch 6:** full backend suite 493 passed, 4 skipped, 0 failed; frontend `tsc` and `build` both clean (no frontend changes this batch). PostgreSQL migration verified against a real rehearsal container in both directions - seeded a pre-existing row, confirmed backfill to `org_default`, inserted a second org's own `config_id=1` row to prove the reshaped key permits what it's meant to without disturbing the pre-existing `CHECK(config_id=1)` constraint, downgrade restored the exact original schema, re-upgrade clean. Playwright: security-smoke + permission-gating passed clean (4 passed, 1 skipped). The full `every-page.spec.ts` run could not complete after four attempts (three full runs plus one sharded half) due to sustained memory exhaustion on this machine, never an assertion failure - disclosed rather than silently skipped. The one page this batch's backend changes reach, `/execution-isolation`, was verified individually via a narrowed run and passed.

**Verification run for P2.2 batch 7:** full backend suite 495 passed, 4 skipped, 0 failed; frontend `tsc` and `build` both clean (no frontend changes this batch, one retry needed for each under this machine's sustained memory pressure). PostgreSQL migration verified against a real rehearsal container in both directions - seeded pre-existing rows in all three tables, confirmed backfill to `org_default`, inserted a second org's row reusing the identical `agent_name` and `config_id=1` to prove both reshapes permit what they're meant to, downgrade restored the exact original schema for both, re-upgrade clean. Playwright: security-smoke + permission-gating passed clean (4 passed, 1 skipped) after one retry. The full `every-page.spec.ts` run could not complete after three attempts due to sustained memory exhaustion on this machine, never an assertion failure - disclosed rather than silently skipped. The one page this batch's backend changes reach, `/isolation-operations`, was verified individually via a narrowed run and passed.

**Verification run for P2.2 batch 8:** full backend suite 496 passed, 4 skipped, 0 failed; frontend `tsc` and `build` both clean (no frontend changes this batch). PostgreSQL migration verified against a real rehearsal container in both directions - seeded a pre-existing row, confirmed backfill to `org_default`, inserted a second org's own `config_id=1` row to prove the reshape permits what it's meant to, downgrade restored the exact original schema, re-upgrade clean. Playwright: security-smoke + permission-gating passed clean on the first attempt (4 passed, 1 skipped). `every-page.spec.ts`: 35/36 passed; the one failure (Compliance Reports, "Something went wrong") does not implicate this batch - confirmed directly by bootstrapping the e2e backend by hand and calling `GET /compliance-reports` with a real session token, which returned 200 with correct data on a fresh database; `compliance_reports.py` has no code path connecting to `adversarial_simulations.py`. This machine's memory was under severe, escalating pressure during this run - a same-run full retry and a narrowed single-page retry were both killed outright by the OOM-prevention mechanism before completing, and no orphaned Playwright/dev-server processes were found to reclaim. Recorded as unreproduced-by-direct-verification environmental flakiness rather than silently re-run into a false pass or silently ignored.

**Verification run for P2.2 batch 9:** full backend suite 496 passed, 4 skipped, 0 failed - no new tests needed (the existing tenant_guard coverage test already verifies every table is classified somewhere, and this batch is a pure set-membership move). No schema, frontend, or API contract change, so no PostgreSQL migration, build, or e2e run applies.

**Verification run for P2.2 batch 10:** full backend suite 496 passed, 4 skipped, 0 failed, run in two halves (257 + 239 test files) to keep peak memory down under this machine's sustained memory pressure, which had escalated enough by this batch to kill even a single-process full-suite pytest run outright. No new tests needed, same reasoning as batch 9. No schema, frontend, or API contract change, so no PostgreSQL migration, build, or e2e run applies.

**Verification run for P2.2 batch 11:** full backend suite 499 passed, 4 skipped, 0 failed, run in two halves - the first half surfaced a real failure (the `emergency_revoke_all` signature-ordering bug above), fixed, and the full split suite reconfirmed green on rerun. PostgreSQL migration verified against a real rehearsal container in both directions - seeded a pre-existing row, confirmed backfill to `org_default`, inserted a second org's row reusing the identical secret `name` to prove the reshape permits what it's meant to, downgrade restored the exact original schema, re-upgrade clean. Frontend build clean (no frontend changes this batch); no e2e run applies.

**Verification run for P2.2 batch 12:** full backend suite 501 passed, 4 skipped, 0 failed, run in two halves (258 + 243) to keep peak memory down. PostgreSQL migration verified against a real rehearsal container in both directions - seeded pre-existing rows in both tables, confirmed backfill to `org_default`, downgrade restored the exact original schema for both, re-upgrade clean. Frontend build clean (no frontend changes this batch); no e2e run applies.

**Batch 13:** documentation/registry-comment only, no code or schema change - the policy-versioning/enforcement-engine finding described above. The existing tenant_guard coverage test (`test_every_schema_table_has_an_explicit_tenant_scoping_status`) still passes, confirming no table was dropped or duplicated across registries while writing up the finding.

**Verification run for P2.2 batch 14:** full backend suite 501 passed, 4 skipped, 0 failed, run in two halves (258 + 243) to keep peak memory down - no new tests needed, same reasoning as batches 9/10. No schema, frontend, or API contract change, so no migration, build, or e2e run applies.

**Verification run for P2.2 batch 15:** full backend suite 509 passed, 0 skipped, 0 failed, run in two halves (258 + 251) - 4 new tests (cross-org name reuse, cross-org enqueue rejection, worker delivering each org's exports to its own destination, legacy SQLite upgrade preserving the `export_queue` foreign key). One unrelated `test_admin_auth` failure appeared on the very first run against a freshly created `backend/data` directory (this Codespace had been rebuilt) and did not reproduce in either of two further runs of the same half, with or without this batch's changes - disclosed rather than ignored. PostgreSQL migration verified against a real `postgres:17-alpine` rehearsal container in both directions - seeded pre-existing rows in both tables at the batch-12 head, confirmed backfill to `org_default` and `NOT NULL`, inserted a same-named destination under a different `org_id` (accepted) and a case-variant duplicate within `org_default` (rejected by the citext composite constraint), downgrade restored the exact original `UNIQUE(name)` constraint with the FK and seeded rows intact, re-upgrade clean; the module's own SQL (including the cross-org claim and the new same-org join) was then exercised end-to-end against that PostgreSQL database through `db_compat`. Frontend `npm run check` clean (lint, 113 unit tests, build; no frontend changes this batch). Full Playwright suite 43 passed, 1 skipped (no agents registered in this environment), including `/security-exports` - after installing Chromium's system libraries, which the rebuilt Codespace was missing.

**Verification run for P2.2 batch 16:** full backend suite 515 passed, 0 failed, run in two halves (258 + 257) - 6 new tests (cross-org name reuse for destinations and templates, cross-org destination/template use rejected, worker delivering each org's notifications to its own destination, a scheduled report notification queued within the schedule's own org end-to-end, legacy SQLite rebuild including a pre-`max_attempts` table, and the outbound-worker notifier wiring regression), plus the existing report-governance notifier test updated to assert the schedule's org_id is passed through. PostgreSQL migration verified against a real `postgres:17-alpine` rehearsal container in both directions - seeded a row in all three tables at the batch-15 head, confirmed backfill to `org_default` and `NOT NULL`, same-name destination and template accepted under a different `org_id`, case-variant destination duplicate and exact template duplicate rejected within `org_default`, downgrade restored both original `UNIQUE(name)` constraints with seeded rows intact, re-upgrade clean; the module's SQL and the fixed worker notifier path were then exercised end-to-end against that database (a scheduled report's notification reached its own org's endpoint). Frontend `npm run check` clean (lint, 113 unit tests, build; no frontend changes). Full Playwright suite 43 passed, 1 skipped (no agents registered), including the Communication Integrations page that calls `/notification-delivery`.

**Verification run for P2.2 batch 17:** full backend suite 519 passed, 0 failed, run in two halves (262 + 257) - 4 new tests (cross-org name reuse, cross-org queue rejection, worker delivering each org's incidents to its own destination, legacy SQLite rebuild of a pre-`max_attempts` table with the `available_at` backfill preserved). That legacy test caught a behaviour change during development - the `available_at` backfill had been gated on the column being newly added, where the original ran it on every init - and it was restored before commit. PostgreSQL migration verified against a real `postgres:17-alpine` rehearsal container in both directions - seeded a row in both tables at the batch-16 head, confirmed backfill to `org_default` and `NOT NULL`, same-name destination accepted under a different `org_id` and a case-variant duplicate rejected within `org_default`; the module's SQL (cross-org queue rejection, worker claim and same-org join) was exercised end-to-end against that database; downgrade refused while two orgs shared a name (the documented composite-key caveat), then restored the original `UNIQUE(name)` with seeded rows intact once only one org's rows remained; re-upgrade clean. Frontend `npm run check` clean (lint, 113 unit tests, build; no frontend changes). Full Playwright suite 43 passed, 1 skipped (no agents registered).

**Verification run for P2.2 batch 18:** full backend suite 521 passed, 0 failed, run in two halves (262 + 259) - new tests for the required `org_id` keyword (a call without it raises `TypeError`), the legacy SQLite backfill (export evidence -> `org_default`, SSO evidence stays NULL), the incident worker attributing each record's evidence to that record's own org, and SSO login evidence staying install-level. PostgreSQL migration verified against a real `postgres:17-alpine` rehearsal container in both directions - seeded legacy export, SSO and SSRF-allowlist evidence at the batch-17 head, confirmed the backfill (export -> `org_default`, SSO/SSRF -> NULL) and that the column is nullable; the module's SQL was exercised through `db_compat` (an `org_other` write and an install-level allowlist write); downgrade dropped the column with all rows intact; re-upgrade clean. Frontend `npm run check` clean (lint, 113 unit tests, build; no frontend changes). Full Playwright suite 43 passed, 1 skipped (no agents registered).

**Verification run for P2.2a (install-operator role):** full backend suite 548 passed, 0 failed, run in two halves (285 + 263) - 27 new tests: every one of the 21 gated routes refuses a non-operator org PLATFORM_ADMIN, the full org-creation takeover chain, operator access, the last-operator guard, first-run setup, the legacy PIN, and the SQLite backfill including no re-grant. Mutation check: temporarily reverting the gate to the old PLATFORM_ADMIN check fails 22 of them (all 21 routes plus the takeover chain). PostgreSQL migration verified against a real `postgres:17-alpine` rehearsal container in both directions - backfill (PLATFORM_ADMIN -> operator, analyst not; a disabled PLATFORM_ADMIN is backfilled too, matching SQLite, so re-enabling restores exactly what they had before orgs), `NOT NULL DEFAULT 0`, last-operator guard, grant and hand-over, new accounts default to non-operator; downgrade kept all rows; re-upgrade clean. Frontend `npm run check` clean (lint, 113 unit tests, build). Full Playwright suite 44 passed, 1 skipped (no agents registered), including a new end-to-end test that signs in as a real non-operator PLATFORM_ADMIN and confirms the four install-wide pages are hidden from navigation, redirect or deny on direct navigation, and that the server itself returns 403.

**Verification run for P2.2 agent batch A:** full backend suite 563 passed, 0 failed, run in two halves (300 + 263) - 15 new tests: a two-org takeover attempt (the original credential still authenticates afterwards), each of seven admin agent routes treating another org's agent as missing with its identity untouched, the owning org still managing its agent, the global name namespace without owner disclosure, pre-org runtime states belonging to `org_default`, credential-history attribution, the legacy SQLite backfill, and org-filtered global search. Mutation checks: disabling both ownership layers fails 5 route tests outright; the takeover test only fails once the database-layer filter is also removed, confirming the two layers are independent. PostgreSQL migration verified against a real `postgres:17-alpine` rehearsal container in both directions - seeded an identity and a credential event, backfill to `org_default` and `NOT NULL`, then the module's SQL (cross-org rotate refused, own-org rotate and history, org-filtered listing, install-wide count); downgrade kept all rows; re-upgrade clean. The name-reuse rule was not reached in that rehearsal (the probe was rejected first by scope validation) - it is covered by the SQLite tests, and its only database step, the identity lookup, did run on PostgreSQL. Frontend `npm run check` clean (lint, 113 unit tests, build; no frontend changes). Full Playwright suite 45 passed, 1 skipped.

**Verification run for P2.2 agent batch B:** full backend suite 575 passed, 0 failed, run in two halves (312 + 263) - 6 new agent-evidence tenancy tests (stamping, cross-org approval refused with the request left pending, scoped timeline plus `ALL_ORGS`, org-scoped compliance evidence, the fixed agent detail route over real HTTP including a cross-org probe returning 404 and a bad credential returning 401, legacy backfill) and the six audit-integrity routes added to the install-operator gate tests; existing test doubles updated for the new required keyword. The detail-route 500 was reproduced on the unmodified code before fixing. PostgreSQL migration verified against a real `postgres:17-alpine` rehearsal container in both directions - seeded rows in all four tables, backfill to `org_default` and `NOT NULL`, then the module's SQL end to end (agent-org stamping, cross-org approval refused, own-org decision with same-org approval evidence, per-org timelines, `ALL_ORGS`, org-scoped compliance evidence); downgrade kept all rows; re-upgrade clean. A second rehearsal exercised the audit-integrity statements on PostgreSQL (seal and verify across both orgs' rows; install-wide retention deleting old rows from both orgs while keeping current ones). Frontend `npm run check` clean (lint, 112 unit tests - one nav test folded into the install-operator loop - build). Full Playwright suite 45 passed, 1 skipped; the non-operator e2e test now also covers `/audit-integrity`.

**Verification run for P2.2 agent batch C:** full backend suite 580 passed, 0 failed, run in two halves (317 + 263) - 5 new tenancy tests (alerts follow their evidence's org; another org's alert cannot be read, updated or annotated; install-level alerts and notifications visible only to operators; per-org notifications and retention, where one org's 7-day cleanup leaves the other org's notifications intact; legacy singleton and alert backfill). Mutation checks: ignoring the org in alert visibility fails 4 tests; letting retention cleanup span orgs fails the per-org retention test. The guard also caught a raw unscoped `security_alerts` query in an existing test. PostgreSQL migration verified against a real `postgres:17-alpine` rehearsal container in both directions - a seeded row in all six tables, backfill to `org_default`, composite policy key; then the modules' SQL end to end (per-org alerts, the operator's added install-level alert, cross-org note refused, own-org note and update, pre-org note still attached, per-org inboxes, policies and history); downgrade refused while two orgs held policies (the documented caveat), then restored `PRIMARY KEY (id)` with the original policy and all rows; re-upgrade clean. Frontend `npm run check` clean (lint, 112 unit tests, build). Full Playwright suite 45 passed, 1 skipped.

**Verification run for P2.2 policy batch:** full backend suite 587 passed, 0 failed, run in two halves (324 + 263) - 7 new tenancy tests (per-org enforcement through the real four-eyes workflow, the restart regression, per-org global deny, per-org rollouts, cross-org policy versions invisible, `/permissions` requiring an administrator, legacy upgrade with `PRAGMA foreign_key_check` clean). Mutation check: forcing `evaluate_action()` to ignore the agent's org fails all 4 enforcement tests. PostgreSQL migration verified against a real `postgres:17-alpine` rehearsal container in both directions - a seeded row in all eight tables, backfill to `org_default`, composite keys and the per-org version constraint; then enforcement end to end (the default org keeps its pre-org BLOCK policy while a new org is seeded with the defaults; one org's approval and its global deny change only its own agents; per-org version numbering; stored policy tests still run; cross-org version lookup refused); downgrade refused while two orgs had rows (the documented caveat), then restored every original constraint with the pre-org policy intact; re-upgrade clean. Frontend `npm run check` clean (lint, 112 unit tests, build). Full Playwright suite 45 passed, 1 skipped, including `/policies` and `/risk` loading through the authenticated `/permissions` route.

**Verification run for P2.2 final batch:** full backend suite 591 passed, 0 failed, run in two halves (328 + 263) - 4 new tenancy tests (reports built from and confined to the requesting org; approval links issued and consumed only within the request's org; callback evidence attribution; `PENDING_TENANT_SCOPING` asserted empty). PostgreSQL migration verified against a real `postgres:17-alpine` rehearsal container in both directions - a seeded row in each table, backfill to `org_default` and `NOT NULL`; then the modules' SQL end to end (org-confined report evidence, cross-org report read refused, PDF export, per-org history; cross-org link consumption refused, own-org consumption deciding the request, per-org link listing); downgrade kept all rows; re-upgrade clean. Frontend `npm run check` clean (lint, 112 unit tests, build). Full Playwright suite 45 passed, 1 skipped.

**Verification run for P2.4:** full backend suite 620 passed, 0 failed, run in two halves (341 + 279), including 18 new tests driving the real routes and the real webhook endpoint over HTTP. They cover:

**Verification run for P2.5:** full backend suite 633 passed, 0 failed, run in two halves (357 + 276), including 13 new lifecycle tests through the real routes and middleware, plus a roster assertion added to the existing report-tenancy test. They cover:

**Verification run for P2.6:** full backend suite 646 passed, 0 failed, run in two halves (359 + 287), including:

- 10 acceptance tests: the read sweep, the write sweep, the protection-coverage check, and the 7-state failure matrix;
- 1 redaction regression test;
- 2 adapter-seeding regression tests.

The read sweep made over 100 calls and the write sweep over 150 calls that reached handlers.

Mutation checks:

- Restoring the P2.5 compliance-roster leak fails the read sweep. The first version of the sweep missed it, because it only probed with victim identifiers; it now also walks the attacker's own records.
- Making one list route fall back to the default org fails the read sweep. This is why the default org is a second victim.
- Removing the agent-ownership check fails the write sweep.
- Taking emergency stop off the offboarding allowlist fails the matrix.
- A no-op change passes.

The whole suite also passed against real `postgres:17-alpine`, each test on a freshly migrated schema, including the startup adapter repair. There is no schema change in P2.6.

The full Playwright suite gave 46 passed and 1 skipped after the redaction change, which touches every API response.

- onboarding without operator membership, and owner acceptance;
- the computed checklist;
- an export confined to the org, with credentials redacted, and verified digests;
- the schema-wide redaction decision;
- export permissions;
- offboarding closing every door, with credentials failing, growth refused, HTTP read-only with evidence, export and emergency controls still allowed, and invitations refused;
- offboarding permissions and cancellation;
- deletion of two populated orgs: one deleted, every org-scoped table empty for it, the neighbour's and the default org's counts unchanged, files and runtime state removed, the certificate verifying, the slug freed;
- the integrity chain valid after deletion and after retention, while an unrecorded deletion is still detected;
- a legal hold blocking deletion;
- foreign-key order against the live schema;
- the default org being undeletable.

Mutation checks: turning off export redaction, skipping one table in deletion, deletion erasures, the legal-hold check, the retention wait, credential revocation, the offboarding read-only rule, the lifecycle restriction, retention erasures or the invitation org-status check each fails tests. Restoring the old install-wide roster fails the tenancy test.

PostgreSQL migration `20261015_26` was verified against a real `postgres:17-alpine` container in both directions:

- a legacy audit event was seeded at the P2.4 head;
- the real foreign keys were listed, and every org-scoped child is in `CHILD_TABLES_FIRST`;
- the lifecycle ran end to end on PostgreSQL: two populated orgs, an export with redaction, offboarding, and deletion leaving 0 rows for the deleted org and the neighbour unchanged. The integrity chain verified after deletion and again after a retention run removed the seeded legacy event, and the certificate verified;
- downgrade removed the three tables while leaving P2.4's intact, and re-upgrade was clean.

Frontend `npm run check` is clean: lint, 120 unit tests including 2 new lifecycle-panel tests, and build. The full Playwright suite gave 46 passed and 1 skipped, including a new check that Settings renders the Plan & usage and Readiness & data panels, the computed checklist and the export button against the real backend.

- billing off by default, and the mock provider refused in production;
- linking assigns the plan with audit;
- grace, then restriction, with existing agents, export, emergency controls and revocation intact;
- a retry storm not extending grace, and immediate recovery on payment;
- a payment not lifting an operator suspension, and a payment not reopening a cancellation;
- webhook signature, tampering, stale-timestamp and missing-secret refusals;
- idempotent redelivery, and card fields in a payload never stored;
- unknown subscriptions not disclosed, and the hash chain detecting an edited event;
- governance-role access, including a BILLING_ADMIN who is an AUDITOR managing the contact over real HTTP through the RBAC middleware, plus cross-org isolation;
- 24 concurrent deliveries of 8 events giving one unbroken chain;
- leases: not enforced unless required, missing → restricted → valid, grace → lapsed → renewal recovery, bad signature, forged dates, wrong install, older-lease replay, already-lapsed and over-long leases refused, table edits ignored, a tampered token treated as invalid, and the clock-rollback guard.

Mutation checks:

- Disabling the billing restriction fails 3 tests; the signature check, 2; the field allowlist, 1; the grace-deadline guard, 1; the clock high-water mark, 2; the older-lease check, 1; the licence restriction, 2.
- Removing the per-org lock fails the concurrency test in 2 of 3 runs. The test passed 5 of 5 with the lock.

Development also caught a real portability bug: the first version retried a chain-fork `IntegrityError` inside the same transaction, which PostgreSQL aborts. It was replaced by a per-org row lock before commit.

PostgreSQL migration `20261015_25` was verified against a real `postgres:17-alpine` container in both directions: upgrade from the P2.3 head; then the modules end to end (linking, a failed payment, a redelivery reported as a duplicate, `PAYMENT_OVERDUE` after grace, recovery on payment, a valid three-event chain, and a licence going from `LICENSE_MISSING` to `VALID`); a 30-delivery concurrency run three times with a valid chain each time; downgrade removing all five tables while leaving P2.3's intact; and a clean re-upgrade.

Frontend `npm run check` is clean: lint, 118 unit tests including 3 new restriction and billing summary tests, and build. The full Playwright suite gave 45 passed and 1 skipped against the real backend, including Settings, which now also loads `/billing`.

---

## P3 — Deployment packages and service reliability

**Status: Verified, with stated limits.** The deployment models, gateway distribution, the status page, the reliability documentation, measured load and the compatibility policy all exist. HA itself does not exist yet; its blocker was found and is documented below. Customer-managed keys and private connectivity are deliberately not offered.

| Sub-item | Status | Evidence |
|---|---|---|
| Deployment models (hosted, hybrid, dedicated, self-hosted) with data boundaries, responsibilities, secrets, backups, telemetry, upgrades, rollback, deletion and support | **Verified (documented)** | `docs/deployment-models.md`, stating what is built and what is not. |
| Node/gateway enrollment and workload identity | **Verified** | `backend/app/gateways.py`, `docs/gateway-distribution.md`: a one-time enrollment token exchanged for a hashed node credential; nodes are org-scoped and Enterprise-gated; the fleet view shows IN_SYNC/OUT_OF_DATE/SILENT; revocation takes effect at once; offboarding revokes every node. Commit `d3ec0d6`. |
| Signed versioned policy/configuration distribution | **Verified** | Bundles hold the org's published policy, emergency controls and revoked agents, signed with **Ed25519**. Gateways hold only the public key; the existing HMAC export could not serve this, because its verifier can also forge. The SDK's `greyguard_sdk.gateway` rejects bad signatures, other nodes' bundles, replays and expired bundles. |
| Bounded offline policy use and revocation freshness | **Verified** | `valid_until` is the node's offline allowance (5 minutes to 7 days). After it, `decide()` fails closed, so the allowance is also the revocation-freshness bound. Tested, including revocation and emergency stop reaching the next bundle. |
| HA and failure-mode matrix | **Verified for multi-process; multi-host documented** | `docs/reliability.md`. **Real defect found and fixed:** the shipped image ran `--workers 2`, but agent runtime state was per-process, so an agent suspended by one worker was still **allowed** by the other, whose save then reverted the suspension. That state now lives in the database (`agent_runtime_states`, Alembic `20261015_29`) and every decision updates it atomically. Verified across processes, under concurrency (no lost increments), and on a live `uvicorn --workers 2` server where all 40 requests after a suspension were refused. The image runs two workers again. Multi-host HA needs replicas, a shared data volume and failover PostgreSQL. |
| Load, connection and queue benchmarks | **Verified (measured)** | `scripts/benchmark_load.py` against a real uvicorn server on SQLite and PostgreSQL. The results are in `docs/reliability.md` and `artifacts/benchmarks/`, as observations rather than commitments. **Finding:** PostgreSQL, the production database, measured 4–11× slower than SQLite (`/health` 14 req/s, agent tool requests 5 req/s, 39 of 100 live streams connected), most likely because `db_compat` opens a new PostgreSQL connection for every database call, with no pool. **Fixed:** a connection pool took PostgreSQL to 3–10× its unpooled throughput, at or above SQLite on every path, with 100 of 100 streams connected (commit `3d9fdff`). |
| Regional data-placement matrix | **Verified (documented)** | `docs/reliability.md`: single-region per install; multi-region tenancy is not built; Dedicated gives a region choice through a separate install. |
| Customer-managed keys, private connectivity | **Not offered** | Not implemented or verified, so not offered, per the addendum. |
| Public status page; severity, escalation, maintenance notices and measured response | **Verified** | `backend/app/service_status.py` and a public `/status` page: live component checks, operator-declared SEV1–SEV4 incidents with escalation routes, maintenance windows, and measured median time to acknowledge and resolve, with no SLA. Commit `bb65bc4`. |
| API/SDK compatibility matrix and deprecation policy | **Verified (documented)** | `docs/api-compatibility.md`: what v1 promises, the security-fix exception, a minimum 12-month deprecation with `Deprecation`/`Sunset`/`Link` headers (already emitted on legacy paths), and the SDK matrix. |

---

## P4 — Buyer validation, packaging and pricing

**Status: provisional decisions recorded.** Every decision is evidence-driven: it stands until interviews, the cost model or operating data contradict it. The full record is in `docs/roadmap/p4-decision-package.md`.

- **Approved (provisional):** D1 (buyer), D2 (90-day paid pilot, Enterprise TRIAL, hosted), D4 (SSO in every edition), D5 (working edition labels), D7 (annual subscription banded by governed agents, no figures), D8 (no self-serve trial), D11 (proceed to P5).
- **D9:** hosted-first as the working direction, subject to verified cost, capacity, backup, recovery and support readiness. Customer-hosted gateways stay pilot-only until packaged.
- **D10:** the objective of 2–4 design partners is approved; candidates are to be chosen.
- **D3 undecided:** no pilot fee in code or documents.
- **D6 partly decided:** request and delivery volumes are now **enforced in code as monitor-only**. They cannot be hard-limited by plans or overrides, and a test proves an org past its soft limit keeps receiving security decisions. The capacity *rules* for agents and integrations are now built (commits `e11acd5` and the follow-up UI commit): only active agents and enabled integrations count; archiving (platform-admin, tenant-scoped, reasoned, audited) frees capacity and deletes nothing; plans are explicit (`UNASSIGNED` grants no capacity, and orgs that existed before D6 get a one-time, audited `TRANSITIONAL` assignment); Dedicated takes its limits from the contract; install operators assign plans from Settings, administrators archive agents from the Agents page, and integration destinations from the Security Exports, Incident Integrations and Communication Integrations pages (commit `b0b1760`). The Foundation/Enterprise limit *values* are retained provisionally and still await review.


**Verification run for D6 capacity rules:** full backend suite 693 passed, 0 failed, run in two halves (387 + 306), including the 11 D6 tests (one extended to prove the agent list reports `archived_at`). Mutation checks: the 6 from `e11acd5` plus one new (dropping `archived_at` from the public identity fails the archive test). PostgreSQL migration `20261015_32` verified against a real `postgres:17-alpine` rehearsal container in both directions: seeded at the `20261015_31` head with an org without a plan, an org already on Foundation, a deleted org and an agent. The upgrade gave `org_default` and the plan-less org an audited `TRANSITIONAL` assignment (actor `migration:d6`), left Foundation untouched, skipped the deleted org, added the archive columns to all four tables and `contract_limits_json`, and wrote the `d6_explicit_plans` mark. The downgrade removed the transitional assignments, mark table and columns while keeping the agent, the Foundation assignment and the audit events as history; the re-upgrade was clean. A fresh database migrated to head starts `UNASSIGNED` with the mark set, so the application's SQLite backfill never runs on PostgreSQL. 10 of the 11 D6 tests also passed against PostgreSQL, each on its own freshly migrated database. The eleventh builds a legacy SQLite file by design, and its PostgreSQL equivalent is the rehearsal above. Frontend `npm run check` clean (lint, 135 unit tests including the new plan-assignment payload checks, build). Full Playwright suite 50 passed, 1 skipped (no agents registered, so the archive button has unit and API coverage but no browser run), including a new end-to-end test in which an install operator assigns a plan from Settings, with `TRANSITIONAL` not offered and Dedicated blocked until contract limits are entered.

**Verification run for D6 destination archiving in the console (`b0b1760`):** full backend suite 694 passed, 0 failed, run in two halves (388 + 306) from the repository root, including a new test proving all three destination lists report `archived_at`. Mutation check: hiding `archived_at` from the notification destination list fails that test. No schema change, so no migration rehearsal was needed. Frontend `npm run check` clean (lint, 137 unit tests including ARCHIVED taking precedence over delivery health, build). Full Playwright suite 51 passed, 1 skipped, including a new end-to-end test in which a platform admin archives a notification destination: the confirm button stays disabled until a reason is given, the API returns 200, and the card stays listed as ARCHIVED without an Archive button.

No prices, payment credentials or live billing exist anywhere. Interviews, design-partner recruitment and the cost model are business work outside this repository.

---

## P5 — Customer onboarding and success

**Status: Verified and approved (2026-10-15); business values pending.** Built to the provisional P4 decisions (D2 pilot model, D8 sales-assisted, no prices) and approved by the project owner as implemented in commit `f15bfbe`. That includes keeping counts-only adoption analytics, with its per-org opt-out that deletes collected counts. Still pending: D3 (pilot fee: no fee or price field until cost modelling and buyer interviews), D10 (design partners: until suitable candidates are identified) and D6 (agent and integration limit values: under review; the capacity rules themselves are built and verified).

| Sub-item | Status | Evidence |
|---|---|---|
| Repeatable customer lifecycle (discovery → offboarding) with exit criteria | **Verified (documented)** | `docs/customer-lifecycle.md`: 12 stages, each tied to product evidence. Stages 3–10 map onto the readiness checklist that `GET /organizations/{org_id}/lifecycle` computes (P2.5). |
| Implementation checklist, responsibility matrix, training material, support and version policy | **Verified (documented); business values pending** | `docs/customer-lifecycle.md`: a RACI matrix, role training with hands-on practice, and a support policy. Contacts, hours, cadence and supported versions are left marked **[commercial team]** rather than invented. Response targets are measured by the status page, not promised. |
| Product onboarding experience | **Verified** | A Getting Started page (`/getting-started`) turns the computed readiness checklist into guided steps (why, who, a link to the page that does it), with tests ensuring every link is a real page and every backend step has guidance. Pilot tracking (`backend/app/pilots.py`) follows P4 D2: Enterprise TRIAL, 90 days, decision at day 75, six success criteria (four measured from product data, two operator-confirmed with a note), and outcomes convert / extend once / offboard. No fee or price is stored (D3 open). |
| Product analytics excluding prompts, secrets and payloads, and disableable | **Verified** | `backend/app/product_analytics.py`, `docs/product-analytics.md`. Adoption is counts only, computed from existing data. The only new collection is daily page-view counts per fixed navigation path (no user, session, IP or URL parameters; the browser honours Do Not Track). It can be turned off install-wide (`GREYGUARD_PRODUCT_ANALYTICS=off`) or per org by its owners, which also deletes what was collected. Tests prove no request content reaches the adoption output. |
| Export, credential revocation, data deletion, offboarding | **Verified** | P2.5 (`docs/organization-lifecycle.md`). |

---

## P6 — Vendor trust and procurement readiness

**Status: In progress (approved 2026-10-15).** The project owner approved decisions T1–T8 as recommended in [`p6-decision-package.md`](p6-decision-package.md): engineering-scoped work only, source content kept in this repository until the P7 public site, and T3 (security contact), T6 (hosted-offering vendors) and T8 (evidence-request process) still to be supplied by the owner. P6.0 restored the failing security workflow; P6.1 wrote the Trust Center source content and its source register (`docs/trust/`). P6.2 added the questionnaire answer bank and the legal-document register. The hosted data-flow diagram is in `docs/trust/security-overview.md`. P6.3 serves `security.txt` and applies the owner's decisions on T3, T6, T8 and the licence (recorded in the decision package). **P6's engineering scope is complete.** What remains belongs to the project owner:
- turning on private vulnerability reporting for the repository;
- adding a security mailbox before launch;
- contracting vendors;
- legal documents through counsel;
- the penetration test before the first paid pilot;
- publication with P7.

**Verification run for P6.0 and P6.1 (`778dac3`, `9bdaf04`):** the scheduled *Security checks* run of 2026-10-12 had failed in three jobs, which a Trust Center could not describe as passing. *Bandit:* 40 B608 findings, each traced to a code-constant or allowlisted identifier with bound values, and each marked with its reason. A mutation check confirms that a new, unmarked SQL f-string is still reported. *Gitleaks:* the full history was rescanned locally; the 2 findings are a fake token in a scanner test and an example-file placeholder, listed by fingerprint in `.gitleaksignore`; no real secret was found. *Trivy:* the `0.28.0` action tag no longer existed upstream, so the action is pinned to the v0.36.0 commit SHA. A local `trivy fs` run with the action's scanners (vuln, secret) at HIGH/CRITICAL is clean; with misconfiguration scanning added, it reports only that the test-only PostgreSQL parity image runs as root. `pip-audit`, `npm audit --audit-level=high` and SBOM generation all pass locally. **All of this still has to be confirmed by the workflow running on GitHub after a push.** Trust Center: 10 pages and 61 registered statements. `backend/tests/test_trust_center.py` (5 tests) checks register and page IDs in both directions, the evidence, owner and date of every row, every cited path, and that `backend/app` holds no external URL. Three mutations were each caught: a dropped register row, a cited path renamed, and a hard-coded vendor URL. Full backend suite 699 passed, 0 failed (388 + 311), run from the repository root. Each statement was checked against its cited source before commit. That check corrected two claims in the decision package: production PostgreSQL backups are **not** encrypted by GreyGuard (AES-256-GCM applies only to SQLite installs), and the scripted DR drill covers only SQLite.

**Verification run for P6.2:** `docs/trust/questionnaire-answer-bank.md` has 47 answers in ten domains. 42 cite registered statements. 5 are *Owner to answer*: security policies and owner (G4), personnel (P1), incident-notification time (L3), DPA (R5) and subprocessors (T1, which also cites what is known). Nothing is copied into a buyer form without re-checking (T4). `docs/trust/legal-documents.md` lists the 10 T7 documents by name, owner, reviewer and status, all *Not started*, and records that the repository has no licence file. One statement was added, TC-IR-1: the runbook exists, but there is no formal security-incident response plan. The Trust Center tests now number 6. The new one requires every answer to use a defined answer value and to cite a statement unless it is left to the owner; the mutation of stripping a citation from a *Yes* answer is caught. Full backend suite 700 passed, 0 failed (388 + 312).

**Verification run for the GitHub security checks and P6.3 (`a6ff916` and the P6.3 commit):**
- *GitHub security checks.* The first GitHub run of the repaired workflow (run 38755382085, on Dependabot PR #2) failed in `secret-scan`: *"GITHUB_TOKEN is now required to scan pull requests"*. It also warned `Unexpected input(s) 'CRITICAL'`: inside the one-line `with: {...}` mapping, `severity: HIGH,CRITICAL` was split at the comma, so Trivy had only ever gated on HIGH. Both were fixed in PR #16 (`a6ff916`). On that PR every check passed on GitHub: the five Security checks jobs, CI, CodeQL and the security assurance matrix. The Trivy warning was gone, and Gitleaks reported *"no leaks found"*.
- *`security.txt`.* Served from `frontend/public/.well-known/` through the shipped `deployment/nginx.conf`. A real `nginx:1.31.6-alpine3.24-slim` container returned `200`, `text/plain; charset=utf-8`, with every server-level security header kept.
- *Tests.* `backend/tests/test_security_txt.py` has 5 tests covering the contact, expiry under a year, known fields only, both nginx configs, and the service-worker denylist. Two mutations were each caught: an expired date, and an app-shell fallback. A new Playwright test fetches the file from the built app.
- *Repository setting.* Private vulnerability reporting was found **off** on the repository (`GET /repos/.../private-vulnerability-reporting` returned `enabled: false`). The contact therefore does not accept reports until the owner enables it; Trust Center statement TC-VD-4 records this.
- *Suites.* Full backend suite 705 passed, 0 failed (396 + 309). Frontend `npm run check` clean (137 unit tests). Full Playwright suite 52 passed, 1 skipped.

| Sub-item | Status | Evidence |
|---|---|---|
| Security overview/architecture content | **Verified (source content, unpublished)** | `docs/trust/` (P6.1): ten pages, each statement registered in `docs/trust/source-register.md` with evidence, owner and review date. Publication waits for P7 (T2). |
| Subprocessor register, responsible-disclosure policy, `security.txt` | **In progress** | `docs/trust/subprocessors.md` lists what the software contacts and leaves hosted-offering vendors as "not yet chosen" (T6). `docs/trust/vulnerability-disclosure.md` restates `SECURITY.md`. `security.txt` is blocked on T3. |
| SOC 2/ISO 27001/insurance/certifications | **Not applicable** (per the addendum itself) | Addendum explicitly calls these "later gated programmes, not launch claims" — correctly not attempted. |
| Legal documents (Terms, DPA, AUP, etc.) | **Not applicable to engineering** | Requires qualified legal counsel per the addendum's own text; not something I should draft or imply completion of. |

---

## P7 — Separate public commercial website

**Status: In progress (approved 2026-10-15; P7.0 verified).** Built to the approved decision package [`p7-decision-package.md`](p7-decision-package.md). The owner will choose hosting, domain and demo route (W4, W5) after reviewing [`p7-owner-brief.md`](p7-owner-brief.md); engineering continues without them, and only publishing (W11) waits.

**P7.0: claim register (commit `f1ef90a`).**
- **The register.** `website/content/claims.json` holds 29 claims, all **proposed**: none is approved, and the site will publish only approved ones. They cover Gate, Watch, Respond and Evidence capabilities, connection methods, platform isolation and four limitations (coverage, single host and no SLA, no live-database encryption, no penetration test or certification). Monitor-only connection is labelled **planned** because it is not built.
- **The check.** `scripts/check_claims.py` validates the register, and `backend/tests/test_claim_register.py` runs it in CI. It requires:
  - every cited file and `file::test` to exist;
  - a test behind every verified capability;
  - no wording implying a partnership, certification or guarantee;
  - a named approver and date on every approval, with no approved claim past its review date.
- **New evidence for the core control loop.** Writing the register showed it had no direct tests. `backend/tests/test_control_loop.py` now proves:
  - an ASK request waits and does not run until approved, and a denied request never runs;
  - blocked actions add risk and suspend the agent at its threshold, after which everything is refused;
  - an ungranted scope is denied;
  - a reset restores a suspended agent.
- **The validator caught its own author.** It rejected a mistyped test name in the first draft, and its own tests found a pattern bug: `100%` never matched.

**Verification run for P7.0:**
- Full backend suite in two halves: 407 + 317 = 724 passed.
- Mutation checks:
  - Caught: removing the claim rules (the verified-needs-a-test rule, review-date expiry and the forbidden-word check), and auto-approving ASK requests.
  - Survived, with nothing observable changed: removing the early refusal of a suspended agent. The atomic risk update refuses a suspended agent independently, so that refusal is enforced twice.
- Frontend unaffected (no frontend change).

**P7.1: site skeleton (commit `3b1dbe1`).**
- **Structure:** `website/` is a static Astro 7.3.5 site with its own package, lockfile and build. It imports nothing from the console.
  - Pages: the eight required navigation items, the seven required footer links, four legal page shells (noindex, marked as awaiting counsel per W8), an accessibility statement shell, a responsible-disclosure page using the T3 contact, and a 404.
  - Content pages are labelled placeholders until P7.2–P7.4.
- **Claims:** page copy states claims only through the `Claim` component, which reads the register.
  - A publish build fails without the domain (W4), and fails on the first unapproved claim. Both are confirmed by running a publish build.
  - Preview builds mark unapproved claims and keep every page noindex.
- **Security headers:** `public/_headers` sets a strict Content-Security-Policy (no scripts, nothing inline, same-origin images, styles and fonts), HSTS, nosniff, Referrer-Policy, Permissions-Policy, COOP/CORP and frame denial. `robots.txt` blocks indexing until publication.
- **CI:** the CI workflow gains a `website` job (build, site check, claim check). The security workflow audits the site's npm dependencies, and Dependabot watches them. Gitleaks already scans the whole repository.

**Verification run for P7.1:**
- Preview build: 17 pages.
- `npm run check` passes. Six deliberate corruptions of the built output were each caught: an inline style, a broken internal link, a missing navigation item, an injected script, a removed CSP and an indexable preview page.
- Publish build: refused without `GREYGUARD_SITE_URL`, and refused on unapproved claim GG-GATE-1.
- `npm audit`: 0 vulnerabilities.
- Screenshots at 1440 px and 390 px: no horizontal scroll.
- Open for P7.2: the logo file carries its own navy background box, which shows slightly against the header.

**P7.2–P7.4: the site redesigned against reference sites (commits `da5a0eb`…`7fa390b`).** At the owner's request ("use other website references… do the best and even more"), 12 leading sites were studied from live screenshots:
- AI-agent security: Zenity, Noma, Lakera, Prompt Security;
- security: Wiz, CrowdStrike, Snyk, 1Password, Cloudflare;
- product craft: Linear, Vercel, Stripe.

Their common structure was adopted in GreyGuard's own brand and wording: announcement bar, a sticky header with mega-menus, a hero with a product visual, a connection strip, a problem section, platform sections, a request-path diagram, proof, a closing call to action and a full footer. Nothing was copied.

What the reference sites show and GreyGuard does not have or may not invent was replaced with the claim register: customer logos, testimonials, analyst badges and user counts. Every claim shows its availability and control, and the Trust page publishes the whole register with test counts.

Pages built:
- **Homepage.**
- **Platform:** the addendum's nine product-page elements for each of Gate, Watch, Respond and Evidence, with synthetic illustrations.
- **Proof & Trust:** assurance status, the full claim register, and the T8 evidence-request process.
- **Agent environments:** connection methods, SDK examples taken from the READMEs, and a coverage table with its planned and not-covered rows.
- **Company:** principles, and the contact section the demo buttons link to.

The mega-menus work without scripts (hover and keyboard focus), and the mobile menu is a native `<details>` element, so the strict CSP still holds. Decision V3 is implemented: claims carry a `control` field that the validator requires.

**Findings:**
- **Logo:** every brand-pack logo is a 3D render on a dark rectangle, which the reference sites never show. The artwork is unchanged and only resized: 2.3 MB → 10 KB WebP. Transparent vector masters are an owner commission (`docs/brand/logo-design-brief.md`).
- **Accuracy fixes made during review:**
  - "Self-hosted or hosted" became "Runs in your own environment", because no hosted service exists yet.
  - The illustration's "Risk if approved" became "Risk added", because risk is added at decision time.
  - The verified count was corrected so it excludes limitations.
  - Monitor-only's evidence was changed to "Planned".

**Verification for P7.2–P7.4:**
- `npm run check` passes on every build.
- Screenshots reviewed at 1440 px and 390 px for the homepage, the open mega-menu, Platform, Trust and Agent environments, with no horizontal scroll.
- Claim tests pass: 14.

**Completed in the next round (commits `139d3d1`, and the use cases and resources commit):**
- **Integrations:** a directory of six families with maturity labels. Six new claims, GG-INTG-1..6, sit in an `integrate` group. Cloud secret managers and external policy engines are labelled **preview**, because live resolution and live engine decisions are untested.
- **Use cases:** six cases by buyer and workflow, plus an "Is GreyGuard right for you?" check.
- **Resources:** only material that exists today.

Every navigation page now has content. The site check passes on all 17 pages, the claim tests pass (14) and the register holds 35 claims, all proposed. A designer-ready logo brief is published as a shareable document; its source is `docs/brand/logo-design-brief.md`.

Remaining before publication: the owner's claim approvals, W4 (domain and host), W5 (demo route), W8 (counsel's legal pages), the logo masters and the trademark search. Final product screenshots and the tour wait for P7.5, per v3. Next: P7.5's console gap matrix.

**Deferred-decision architecture (owner instruction, 2026-10-15; commits `5ac82ec`, `581ead0`, `79a4bfe`).** Development continues without forcing founder, brand, legal, hosting or commercial decisions. Every such value now lives in one place, renders through a slot, and has a safe state until it is decided.

- **Decision registry.** `config/decisions.json` holds 43 typed decisions across brand, commercial, company, legal/trust and operations, each with an owner, a tier and a remediation step. The tiers are BLOCKING_FOR_PRODUCTION, REQUIRED_BEFORE_PUBLIC_LAUNCH, OPTIONAL_POST_LAUNCH and COMPLETED.
  - 4 are decided: the product name, the tagline, the security contact (T3) and the disclosure contact, which references it.
  - `scripts/decisions.py` validates the registry, scans it for secrets and renders [`FOUNDER_DECISIONS_REQUIRED.md`](FOUNDER_DECISIONS_REQUIRED.md).
  - `readiness --target development|preview|production|public-launch` reports each missing item and its fix. Development and preview always pass; production and public launch fail while their items are open.
  - Newly discovered decisions were added rather than guessed, among them the penetration test (LEG-12).
- **Brand slots.** `config/brand-assets.json` names 16 slots:
  - dark and light lockups, horizontal lockup, symbol, mono symbol;
  - favicons at 16, 32 and 48 px plus ICO, Apple touch at 180 px;
  - PWA icons at 192 and 512 px plus maskable;
  - a 1200 × 630 social preview, a document logo and a splash.
  
  12 slots are provisional, using the existing logo unchanged and resized only. 4 are missing and render their fallback. `scripts/brand_assets.py sync` generates the console's typed map and CSS variables and [`docs/brand/ASSET_MANIFEST.md`](../brand/ASSET_MANIFEST.md). `npm run brand` in `website/` derives the site's copies. Components ask for a slot, never a file, so a final master replaces a provisional one by dropping the file at the slot's path and updating its status. The provisional state is internal and never shown to visitors.
- **Website slots:** BrandMark, BrandLockup, PublicContact, DemoRequestDestination, PlanDisplay, SupportInformation, LegalDocument, LegalDocumentLink and TrustClaim, all reading the registry. Safe states:
  - plans show "Contact sales";
  - every demo button leads to `/request-demo/`, which explains that requests open soon and collects nothing, so nothing is silently discarded;
  - unapproved legal pages show "Draft: awaiting qualified legal review", are noindex, and are tagged "(draft)" in the footer;
  - certifications always read "Not currently claimed", and the penetration test reads "Not independently verified".
  - A publish build runs the production readiness gate and fails with the report.

**Verification run:**
- Registry, brand and claim tests: 43 passed. That is 19 for the registry, 10 for brand assets and 14 for claims.
- Mutations caught:
  - a hard-coded `/brand/` path in a component;
  - a secret in the console's brand map;
  - an extra `VITE_` variable;
  - a security.txt contact that differs from CO-03;
  - a manifest edit without sync;
  - an unlabelled legal draft (site check);
  - plus the registry mutations recorded with `5ac82ec`.
- Full backend suite in two halves: 432 + 322 = 754 passed.
- Playwright: 64 passed, 1 skipped (the existing light-theme skip).
- Frontend `npm run check` passes. Website preview build: 18 pages, and the site check passes. A publish build fails at the readiness gate, as intended.
- Screenshots of `/request-demo/`, Company, Privacy and Terms at 1440 px and 390 px: no horizontal scroll.

Nothing was pushed, published or deployed.

### P7.5 progress against Master Roadmap v3 (Section 5, "P7.5 — product experience hardening")

The owner follows P7.5 here. The table is updated with every batch; the detailed entries follow below it, newest last.

| v3 item | Status | Where |
|---|---|---|
| 1. Navigation architecture | ✅ Done | batch 1 `385c32a` |
| 2. Command Center with role presets | ✅ Done | batch 3 `edb8d36` |
| 3. Universal page anatomy | ✅ Done, except contextual docs links, which wait for hosted docs | batches 2, 4, 4d; `p7.5-gap-matrix.md`, `p7.5-time-range-saved-views-design.md` |
| 4. Control Graph | ✅ Done, including the 15-second cache (DEV-001 closed) | `p7.5-control-graph-design.md`; `eabf0e1`, `6e381db`, `d3104e5` |
| 5. Investigation workspace | 🔨 **In progress**: design approved 2026-10-16; step 2 (workspace page) next | `p7.5-investigation-workspace-design.md` |
| 6. Decision explainability | ✅ Explanation card done (`d6cbc2f`); it is also reused in the workspace | same design |
| 7. Safe change management | Not started | |
| 8. Unified action inbox | Not started | |
| 9. Help and explanation | Not started | |
| 10. Design quality | Partly done: console design v2 `52c0d93`. **Next after 5 and 6:** visual-regression tests and performance budgets (owner's order) | |
| 11. Synthetic demonstration org, Trust Center, UX gate | Not started | |

Deviations from approved designs are tracked in [`deviations.md`](deviations.md).

**P7.5 batch 1: seven-domain navigation (V1), 2026-10-16, commit `385c32a`.** The console now uses v3's seven task domains everywhere: the sidebar, the collapsed mega-menu, the breadcrumb trail, page eyebrows and Ctrl+K. The domains are Command Center (pinned), Agents & Access, Policies & Approvals, Operations & Incidents, Evidence & Reports, Integrations, and Organization & Administration. Gate, Watch, Respond and Evidence remain the website's buyer-facing names.

- **Regrouping.** There are now 16 workspaces. New ones: Operators & Access, Agent Connections, Alerting & Ticketing and Platform Health. Authentication moved to Agents & Identity. Telemetry & Sensors moved to Integrations. Every route and page title is unchanged.
- **Derived eyebrows.** `PageHeader` takes its eyebrow from the page's workspace, so a future regrouping cannot leave a stale label. Detail pages add "Investigation".
- **Favourites and recent pages** (v3: "recent pages, favourites"). A star beside the top-bar title adds or removes the open page. It is not shown on detail pages or the Command Center.
  - Favourites appear above the sidebar's domains. Ctrl+K lists Favourites and Recent pages before any query. A favourite is listed once, and the open page is left out of recent pages.
  - Both lists are per-device conveniences in localStorage. Only known console page paths are stored; detail URLs are recorded as their list page, so no agent or request identifier is kept. Each list is permission-filtered when shown.
- **Fix found by the new layout.** The collapsed mega-menu assumed a panel at most 420 px tall. Operations & Incidents is taller, so its last items fell below the window. The panel now measures itself after opening and moves up to fit; a panel taller than the window scrolls.

**Verification run:**
- Frontend `npm run check` passes: lint, 169 unit tests, and the build.
- Mutations caught: the permission filter removed from `visiblePages`; the known-path filter removed from stored reads; a detail URL stored verbatim; a favourite accepting any path.
- Playwright: 65 passed with no retries. The navigation spec also passed 3 times in a row.
- Screenshots reviewed: the sidebar with favourites, Ctrl+K with favourites and recent pages, and the collapsed Operations & Incidents mega-menu.
- No backend change, so the backend suite and migration rehearsal do not apply.

**Observed, not changed:** when resuming a session fails for any reason, including a 429 from the rate limit, `AuthContext` tries a refresh and then signs the operator out. A rate-limited operator is therefore signed out rather than asked to retry. This showed up as a sign-out in an e2e test that made several full page loads. The test now navigates within the app. The underlying behaviour needs its own security-reviewed change.

The P7.5 gap matrix (v3 ordering, step 2) had not been written yet. This batch went first because V1 was already decided.

Nothing was pushed, published or deployed.

**P7.5 gap matrix (v3 ordering, step 2), 2026-10-16.** [`p7.5-gap-matrix.md`](p7.5-gap-matrix.md) audits all 35 navigation pages and both detail pages against v3's universal page anatomy and the shell items. It used a code scan of every page, screenshots of 16 pages, and hand checks.
- **Four findings come first:**
  - Agents cannot be registered from the console. `POST /agents` exists but no page calls it, so Getting Started's "Register your first agent" step dead-ends.
  - The bell's unread dot and the sidebar's "control plane online" text are static.
  - Three pages show "no matching…" when nothing exists.
  - There is no shared permission-denied state.
- **Systemic gaps** for the page kit: freshness, time range, saved views, related records, docs links and page-level primary actions. Sorting and paging are missing on the ten mature list pages.
- **Proposed order:**
  - batch 2: these corrections, with the registration flow under security review because it issues a credential;
  - batch 3: the role-preset Command Center;
  - batch 4: the page-anatomy kit;
  - then the Control Graph, the investigation workspace and explainability.

No code changed.

**P7.5 batch 2: corrections from the gap matrix, 2026-10-16, commit `4f4e8f7`.** All four first findings are fixed.
- **Agent registration.** A "Register agent" button on Agents opens a dialog: the agent name, at least one scope, and the credential shown once. Getting Started's step opens it directly (`/agents?register=1`). No server capability was added: it calls the existing `POST /agents`, which already checks `identity:manage`, plan capacity and that the name is unused in every organization, and which records an `ISSUED` credential event. The server's refusal reason is shown in the dialog.
- **Shell signals.**
  - The bell's dot appears only when `/notifications/summary` reports unread items.
  - The sidebar's status line reports `/status`: operational, degraded, maintenance or major outage. When there is no answer it reads "Status unavailable", never "online".
  - Both load 3 seconds after the page's own data.
- **Empty versus no match.** Incident Center, Tool Requests and Audit Trail say "No … yet" when nothing exists, and "No matching …" with a Clear filters button only when a filter hides results. Sandbox's executions list gained an empty state.
- **One access-denied state.** A single check around the shell's outlet replaces ten silent redirects to the Command Center and Team's own denied heading. It names only the role required: "Install operator access required" or "Platform Administrator access required". It loads none of the page's data, and the pages keep their own checks as a second layer. Secrets and Service Accounts are marked `readOnlyForOtherRoles` and still open read-only.
- **Session resume (the issue observed in batch 1).** Only a 401 or 403 from the server ends a session. A rate limit, a 5xx or a network failure keeps it and retries after 2, 4, 8 and 16 seconds, then every 30 seconds. The splash screen explains the wait, and the refresh token is not spent on a transient failure. The server still checks the token on every request, so keeping it grants nothing. The unused `GET /agents` on every page load was removed; sign-in still makes it once to confirm the new token works.
- **Mega-menu.** It now renders on `<body>`, because the sidebar's stacking context let the offline banner cover it.

**Verification run:**
- Frontend `npm run check` passes: lint, 177 unit tests, and the build.
- Mutations caught:
  - a 429 treated as a rejected session;
  - read-only pages refused;
  - a failed `/status` shown as operational;
  - an unanswered `/status` shown as operational.
- Playwright: 69 passed, 1 skipped (the existing light-theme skip), no retries.
- New e2e tests:
  - registration, including the one-time credential and a duplicate-name refusal;
  - a stubbed 429 keeping the session without a refresh, and a 401 still ending it;
  - the bell and status line matching the API;
  - the shared denied state for an auditor, which loads none of the page's data.
- No backend change.

Nothing was pushed, published or deployed.

**P7.5 design quality: console design v2, 2026-10-16, commit `52c0d93`.** The owner compared the console with the public website and found it unprofessional. They delegated the direction to the references.

- **References.** The public product views of Linear, Grafana's playground, GitLab, Datadog Cloud Security and Vercel's Geist system were screenshotted and studied. All of them keep a compact left sidebar; top mega-menus appear only on their marketing sites. So the console keeps the sidebar (decision V1 stands) and adopts their calm, flat, dense style in the website's navy and cyan identity.
- **Changes.**
  - New tokens.
  - The shell rewritten: compact sidebar, slim top bar, underline tabs.
  - The page kit restyled: Inter headings, flat KPI cards, quiet labels and table headers, small radii.
  - The page header no longer repeats the breadcrumb.
  - Eleven older pages moved their KPI rows onto `StatCard`, and 145 dead rules were removed.
  - Every older stylesheet now ends with a "Design v2" block that hides decorative layers and flattens surfaces.
  - Dropdowns, inputs, the offline notice and the incident drawer were normalised.
  - Settings shows configuration as facts rather than KPIs.
  - The rules are recorded in [`docs/design-system.md`](../design-system.md), which replaces the "Sentinel Vault" direction.
- **Gap matrix.** This covers the visual-consistency finding and part of v3 item 10. Visual-regression tests, performance budgets and the light theme remain.

**Verification run:**
- Frontend `npm run check` passes: lint, 177 unit tests, and the build.
- Playwright: 69 passed, 1 skipped, no retries. This includes every page at 390 px with no horizontal scroll.
- Screenshots were reviewed at 1440 px before and after for the Command Center, a page-kit page (Service Accounts) and all eleven older pages.
- No backend change.

Nothing was pushed, published or deployed.

**P7.5 batch 3: role-preset Command Center (v3 item 2), 2026-10-16, commit `edb8d36`.** It is one composable home rather than six dashboards. The registry, presets and rules are in `frontend/src/config/commandCenter.ts`.

- **Six views:** Platform Administrator, Security Analyst, Approver, Auditor, Organization Owner and Billing Administrator.
  - A person starts on their operational role's view: Platform Administrator, Security Analyst, or Auditor for everyone else.
  - They are offered only the views their roles allow. Approver needs `approval:manage`, because there is no separate approver role and Security Analysts already hold it. Owner needs governance role `OWNER`. Billing needs `OWNER` or `BILLING_ADMIN`.
  - A stored view that a role no longer allows falls back to the default.
- **Only what the person may see.** Each view sets two to five KPIs and an ordered list of panels. Every KPI and panel reads data that every role may read (GET routes), so no panel appears only to be disabled. Acting still happens on the linked page, under that page's own checks.
- **Pinning.** Customize pins extra panels or hides the view's own, with a reset. It is saved per account on this device under `greyguard_command_center:<admin_id>`, and anything that is not a known view or panel is dropped on read.
- **Known limitation:** the server has no preference store yet, so pins do not follow a person to another device.
- **New panels:** Plan & usage (`GET /entitlements`) and Compliance reports (`GET /compliance-reports`).
- **Fewer requests.** Only the queries that the visible KPIs and panels need are fetched.

**Verification run:**
- Frontend `npm run check` passes: lint, 184 unit tests, and the build. The 7 new tests cover the preset rules, pinning and stored-value validation.
- Mutations caught:
  - every view offered to every role;
  - a stored view used without re-checking the role;
  - stored pins not validated;
  - the billing view offered to everyone.
- Playwright: 70 passed, 1 skipped, no retries.
- New e2e tests:
  - an administrator is offered all six views, switches to Billing, pins Compliance reports, hides Readiness, keeps both across a reload, and resets;
  - a real AUDITOR session lands on the Auditor view, with no view switcher and no approval queue.
- A mistake was caught during this batch: the new test file first replaced the existing P1.4 Command Center spec. The original test was restored beside the new one, and every other test file changed today was checked for the same problem.
- Screenshots of the administrator view, the Auditor view and the Customize dialog were reviewed.
- No backend change.

Nothing was pushed, published or deployed. Next in v3's order: the rest of the universal page anatomy. The page-anatomy kit (gap matrix batch 4) adds freshness, time range, saved views, related records, docs links, and sorting and paging for the ten older list pages.

**P7.5 batch 4: page-anatomy kit, first part, 2026-10-16.** It has three pieces, each committed and verified on its own.

- **4a, sortable and paged tables (`15c24f5`).**
  - `DataTable` gains `selectedKey`, shown with `aria-current`, and `onRowClick`, a mouse convenience that leaves buttons and links in the row alone.
  - Agents, Tool Requests and Risk Center move their custom tables onto it: sortable columns, 15 rows a page, and the shared empty states.
  - The agent name and request action are now real buttons that open the details panel. Before, only a mouse click on the row could open it, so keyboard users could not.
  - Risk Center shows Reset only for a suspended agent and only to someone allowed to reset (v3: never show a widget only to disable it).
  - 32 dead rules were removed.
  - A permission test that used to skip itself, because it counted rows before the table loaded, now waits and runs.
- **4b, "Show more" paging (`767b91f`).** Approvals, Audit Trail, Authentication, Incident Center and Notifications show 25 items and grow on request. A new search or filter starts again from the first page. The hook is `components/page/ShowMore.tsx`.
- **4c, evidence freshness (`efbe05a`).** The design changed from a per-page line to one top-bar indicator ("Updated 2 min ago") with one Refresh for the page, as in Grafana and Datadog.
  - It reports the oldest successful load among the page's active queries, so a page never looks fresher than its stalest panel.
  - It ignores the shell's own requests, and stays hidden on pages that load nothing through the query cache rather than guessing.

**Deferred, with reasons:**
- **Time range and saved views** need their own design: which pages, server-side time filters, and where views are stored.
- **Contextual docs links** wait until documentation is hosted somewhere (W-decisions). Linking the private repository would mislead.
- **Related records** need the Control Graph's relationship data.

**Verification run:** for each piece, `npm run check` and the full Playwright suite passed with no retries. At the end: 190 unit tests, and 72 Playwright tests with none skipped. Mutations caught:
- 4b: the filter reset removed;
- 4c: the newest data reported instead of the oldest;
- 4c: the shell's own requests counted.

No backend change. Nothing was pushed, published or deployed.

**P7.5 batch 4d: time range and saved views, 2026-10-16.** Built to the design approved that day (`docs/roadmap/p7.5-time-range-saved-views-design.md`, decisions recorded in `7be46c5`).

- **4d-1, server-side ranges (`3896adc`).**
  - `since`/`until` on `/tool-requests`, `/audit-events` and `/alerts`; `since` on `/live-events`, for its initial history only.
  - A range is ANDed after the org filter, never instead of it.
  - Pending approvals and unresolved alerts are returned whatever the range, and sort first so the row limit cannot crowd them out.
  - The lookback is the smaller of 400 days and configured audit retention (`time_range.permitted_lookback_days`), so nobody queries past what is retained. Retention is install-wide today; the function takes `org_id` so it can become per-org.
  - Responses report the range and whether the list was truncated.
  - Migration `20261016_33` adds per-org time indexes to `audit_events` and `security_alerts`.
- **4d-2, the range bar and URL filters (`d6a1643`).**
  - One range bar under the toolbar on Tool Requests, Approvals, Audit Trail, Incident Center and Authentication, and a history range on Live Operations. Defaults: 24 hours on Tool Requests and Live Operations, 7 days elsewhere.
  - Each list says what it holds, whether the server capped it, and that open items are always shown. Empty states name the range and offer a wider one.
  - Filters live in the URL: Back works, and a link reopens the same view. Invalid values fall back to the defaults.
  - Approvals now asks the server for ASK decisions only (new `policy_decision` filter), so its "newest N" notice is exact.
- **4d-3, personal saved views (`f294942`).** A Views menu in the range bar. Views are stored in the browser under the person's account id and page, and hold only the page's own filter keys (re-filtered on read), at most 20 per page. The record shape (`page`, `query`, `scope`) is ready for a permission-controlled shared-views table later.
- **Fix found while building the Control Graph (`9338e77`).** Evidence timestamps are stored in local time with an offset, so comparing them as text is wrong on a server that does not run in UTC. Ranges now compare instants (`julianday` on SQLite, `timestamptz` on PostgreSQL) behind an index-friendly text pre-filter widened by 14 hours.

**Verification run:**
- **Backend:** full suite 437 + 346 = 783 passed, run in two halves, before the fix; after it, the 33 time-range tests again. The tests cover validation, tenant isolation with a range, open items, truncation, the retention-bound lookback, UTC offsets, 401 before 422, and an AUDITOR's scoped read.
- **Mutation checks:** 12 caught. The 10 below, plus two on the fix (text-only comparison; the pre-filter not widened):
  - the open-rule parentheses removed (would leak another org's pending requests);
  - the lookback, retention cap, `until` and timezone checks removed;
  - range validation run before authentication;
  - the open rule removed for alerts and for requests;
  - pending not sorted first;
  - audit truncation ignored.
- **PostgreSQL** (`postgres:17-alpine`): migration up, down and up again, with a seeded row intact. All 33 time-range tests passed, each alone on a freshly migrated database.
- **Frontend:** `npm run check` passed (220 unit tests, build). Two mutations caught on saved views: stored keys not re-filtered, and malformed entries accepted.
- **Playwright:** the final full run had 73 passed and none flaky.
- **Rate-limit finding (pre-existing, for the owner):** the full e2e suite runs at the API's GENERAL limit of 300 requests a minute per client. The e2e backend recorded a limit breach even in a passing run, and 1 of 4 full runs failed its last test on it. Running in shards is worse: each shard signs in again and trips the ADMIN_AUTH limit. The new spec was cut to one page load and one reload. The limits were not changed; a fix is the owner's call (for example a test-only policy, or fewer shell requests per page load under v3 item 10's performance budgets).
- **Screenshots** of five pages, the custom range and the Views menu were reviewed at desktop and phone widths.

Nothing was pushed, published or deployed.

**Test-only rate-limit override for the browser suite (`1e542fc`), owner decision 2026-10-16.** Production keeps GENERAL at 300 requests a minute. The throwaway e2e backend raises only GENERAL (3000) and AGENT_ACTION (1200), and only with `GREYGUARD_ENV=test` plus an exact sentinel. Anything else refuses to start. Override-seeded rows are marked, and production refuses a database holding one. Sign-in limits are never raised. A Playwright auto-fixture clears the e2e database's rate-limit counters before each test. Details: `docs/testing/e2e-rate-limits.md`.

**Control Graph backend (`eabf0e1`, `7dddeb5`).** Exact, append-only decision records for every new tool request, plus the read-only graph and impact-preview endpoints, built to the owner's three decisions. The frontend is next. One design point is not built yet: the 15-second response cache, tracked as **DEV-001** with follow-up FU-CG-01 in `docs/roadmap/deviations.md`.

**Verification run:**
- **Backend:** full suite, run in two halves: 463 + 364 = 827 passed.
- **New tests:**
  - `test_rate_limit_override.py`, 14 tests, including "production keeps 300 requests a minute";
  - `test_control_graph.py`, 26 tests, covering provenance, append-only storage, historical evidence (exact versus inferred, a changed policy record, a tampered record), tenant isolation, withheld install-level alerts, limits, the retention-bound window, no raw payloads, and an AUDITOR's read-only use, proven by a before/after snapshot of every table plus refused mutations.
- **Mutation checks:** 21 caught.
  - Override (5): the test-environment check, the exact sentinel, the production refusal of a seeded database, sign-in never raised, and the production-config hook.
  - Control Graph (16): org scope on approvals and on alerts, the install-level rule, the ownership check on both routes, inferred labelled as recorded, the node limit, the preview counting only allowed requests, provenance recorded, the append-only trigger, both fingerprint checks, target shortening, and the one-second inference precision.
- **PostgreSQL** (`postgres:17-alpine`):
  - migration `20261016_34` went up, down and up again; an UPDATE was refused by the trigger, a DELETE was allowed, and the downgrade removed both the table and its function;
  - `test_control_graph.py` (26) and `test_rate_limit_override.py` (14) passed, each test alone on a freshly migrated database.
- **Frontend:** `npm run check` passed (220 unit tests, build).
- **Playwright:** three consecutive full runs of 73 passed, 0 flaky, 0 skipped. The e2e backend recorded no rate-limit events at all.

Nothing was pushed, published or deployed.

**Control Graph interface (`6e381db`).** A "Relationships" tab on the agent page (`/agents/:name?tab=relationships`), built to the approved design.
- **Layout:** five columns read left to right: identity, scopes, tools and policy, requests grouped by decision (riskiest first), outcomes. Every node is a real button.
- **Selection:** selecting a node highlights its path, never expanding through the agent, and opens a details panel. The panel renders in a portal so the shell's top bar cannot cover it; a screenshot review caught that.
- **Exact versus inferred:** every request node shows a badge for which it is. The panel shows the exact record (rule, policy version, the record's fingerprint check, and whether the stored version still matches), or says plainly that the decision is inferred and why it can be wrong.
- **Impact preview:** offered for scopes, the credential and tools, labelled read-only, and sending GET requests only.
- **List view:** the same relationships as sentences.
- **Window:** 30 days by default, with the retention horizon stated ("older history is not retained"). Capped and withheld items are stated, not hidden.
- **Loading:** the tab lives in the URL, and the graph loads only when the tab is open.

**Verification run:** `npm run check` passed (230 unit tests, 10 of them new; build). The full Playwright suite had 74 passed, 0 flaky; the new e2e covers an exact decision, the panel's close button, a read-only preview with no non-GET request, and arrow-key tabs. Three frontend mutations were caught: the agent expanded in path highlighting, inferred badged as exact, and the list view dropping "inferred". Screenshots were reviewed at desktop and phone widths. The backend is unchanged since its verified run (827 passed).

The Control Graph is complete apart from DEV-001, the 15-second cache (FU-CG-01). Nothing was pushed, published or deployed.

**FU-CG-01, the Control Graph's 15-second cache (`d3104e5`).** DEV-001 is closed, with the evidence in `docs/roadmap/deviations.md`: full backend suite 850 passed; 23 cache tests and 26 graph tests passed on SQLite and PostgreSQL; 10 of 11 mutations caught (the survivor is a redundant stamp); frontend check passed; Playwright 74 passed, 0 flaky. One real stale-data gap was found and fixed while building it: a retention change was not in the key. Nothing was pushed, published or deployed.

**P7.5 items 5 and 6, step 1: decision explainability (`d6cbc2f`), 2026-10-16.** The design (`p7.5-investigation-workspace-design.md`) was approved with all five recommendations.
- **Explanation endpoint and card:** `/request-investigations/{id}/explanation`, shown on the request page. Fixed reasons per rule type and outcome, built from the exact decision record; inferred where no record exists; no confidence score.
- **"Why is this unavailable?":** built from the viewer's role only.
- **A wrong sentence removed:** the old generic text called emergency refusals policy decisions.
- **Authentication assurance:** decision records version 2 record the agent key or verified certificate (migration `20261016_35`). Version-1 records still verify.
- **Secret-looking values** (JWTs, API keys, GitHub, Slack, AWS and Google keys, GreyGuard credentials, bearer tokens, private keys) are redacted for every role, and the count is shown.
- **A flaky test fixed (`d61ec25`):** the pilots test matched "fee" inside random hex ids, about 1 run in 100. It now matches whole words.

**Verification run:**
- **Backend:** 507 + 369 = 876 passed (the pilots flake appeared once, was diagnosed and fixed, and the half was rerun clean).
- **New tests:** `test_decision_explanation.py`, 26 tests covering:
  - every rule type's reason; inferred labelling; a changed policy as a limitation;
  - key and certificate authentication recorded; version-1 records still verifying;
  - role-only "unavailable" reasons; tenant 404s;
  - redaction of eight secret formats, with ordinary text kept.
- **Mutation checks:** 10 of 10 caught, including:
  - certificate detection, the method allowlist and the version-1 fingerprint fields;
  - the approve step's permission and the unavailable reason;
  - value redaction and a single pattern;
  - the emergency reason, and both limitations.
- **PostgreSQL:** migration `20261016_35` went up, down and up again, keeping a version-1 row, and updates were still refused by the trigger. 26 explanation tests and 26 Control Graph tests passed, each alone on a fresh database.
- **Frontend:** 235 unit tests and the build passed. **Playwright:** 75 passed, 0 flaky, including the new explanation spec (a real agent request with a secret in its payload).

Nothing was pushed, published or deployed.

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
| Tenant-isolation design and test evidence | **Verified** | Design: `tenant_guard.py` (every query against an org-scoped table must carry an `org_id` predicate) plus the per-table registry. Evidence: the per-batch P2.2 tenancy tests and the P2.6 route-generated acceptance suite (`docs/testing-and-assurance.md`), passing on SQLite and PostgreSQL. |
| Trust Center source register, claim register | **In progress** | Trust Center source register built (`docs/trust/source-register.md`, P6.1). The P8 claim register has not been started. |
| Complete source-code/security PDF | **Planned** | Not started — this is the original task's Phase D deliverable. |
| Independent security review | **Planned** | Same gap flagged under P0 above; applies here too as a final-acceptance gate. |
| Application information architecture (P1.4) | **Verified** | Owner requirement 2026-10-15: domain-grouped, expandable navigation; page-level tabs and contextual actions; a rich operational dashboard; every page professionally structured; role-based visibility and all security boundaries preserved. Criteria are listed under P1.4 above. Final acceptance fails until they are verified. |
| Backup/restore/upgrade/rollback/tenant-deletion rehearsals | **In progress (partial)** | `scripts/rehearse_production.py`, `scripts/run_disaster_recovery_drill.py`, `scripts/verify_postgresql_parity.py` exist and have run successfully before (per `artifacts/production-rehearsal.json`, dated before this session's changes). The real PostgreSQL backup/restore gap this item depended on is now closed (`postgres_backup_ops.py`, above); tenant deletion is now rehearsed against a real PostgreSQL container (P2.5 verification run): two populated orgs, one deleted, the other's row counts unchanged and the integrity chain still verifying. |

---

## Summary

**Done this session, confirmed with evidence:** all five Stage 3 security milestones; all eight "operations and structural corrections" items including dependency pinning and the full baseline Alembic migration (captured from a real rehearsal PostgreSQL run, not hand-transcribed, verified three independent ways); a genuinely independent security review of the two highest-impact authentication modules, which found and got fixed one Critical (complete cert-auth bypass via the actually-shipped `nginx.conf`), one High (percent-escaping break that made legitimate cert auth non-functional), and one Medium (SSO admin-takeover via fail-open domain restriction) finding; a fresh full E2E run (38/38) and a fresh final-security-review run (all checks passed, one correctly-tracked pre-existing base-image CVE with no code impact); a real multi-worker SQLite startup race that crash-looped a production container, found by actually running the pinned image rather than just the test suite, fixed at the root and verified against a real container's first boot and restart. Full backend suite confirmed clean across multiple full passes in memory-safe batches, the last one covering every file changed this session: **448 passed, 4 skipped, 0 failed**, across all 60 backend test files.

**P0 is now fully closed.** No open items remain from the original task or the addendum's P0 list.

**A note on what running real things, not just tests, changed:** two of this session's most serious findings - the certificate-auth bypass and the startup race - were both things a passing test suite had missed, because the tests never exercised the actual deployment artifact (which nginx config ships) or the actual multi-process runtime behavior (two uvicorn workers racing against one SQLite file). Independent review caught the first; building and running the real Docker image caught the second. Both are now covered by tests that exercise the real thing, not just the function in isolation.

**Everything from P1 onward is correctly untouched**, per your standing instruction and the addendum's own sequencing. I have not begun branded-interface, tenancy/billing, or public-website work, and will not without your explicit go-ahead at each checkpoint.

**Nothing has been pushed.** All work is in local commits on `main`, per your instruction.
