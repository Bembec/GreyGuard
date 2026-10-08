# Addendum Reconciliation — Status Matrix

Reconciles `GreyGuard_Final_Product_Commercial_and_Launch_Roadmap_Addendum.md` against the current repository, the original engineering task list, and `stage-2-reconciliation.md`. Organized in the addendum's own P0–P10 order. Status values: **Verified** (done, tested, evidence below), **In progress** (started, not complete), **Planned** (scoped, not started), **Deferred** (explicitly held pending a checkpoint/approval per the addendum or Michael's instructions), **Not applicable**.

Nothing below duplicates already-completed work — where a requirement is already satisfied, the entry says so and points at the commit/file, rather than re-describing or re-implementing it.

---

## P0 — Finish current security milestones

| Requirement | Status | Evidence |
|---|---|---|
| Secure outbound delivery | **Verified** | `outbound_delivery.py`, `outbound_worker.py` + wiring into notification/incident/export/report queues. Commits `32722f1`…`39d053e`. 114 tests across the affected files; full backend suite green at the time. |
| Enterprise OIDC sign-in | **Verified** | `enterprise_sso.py` (Authorization Code + PKCE, RS256/ES256 only, nonce/state/PKCE single-use, fixed redirect URI). Commits `c95ec2c`…`d550e38`. 36 dedicated tests + full suite green. |
| Certificate-based agent authentication | **Verified** | `agent_certificate_auth.py`, `workload_identities.agent_name` binding, nginx header contract. Commits `ce79ddd`…`05ada59`. 26 tests. |
| Credential history | **Verified** | `agent_credential_events` table, `GET /agents/{name}/credential-history`, UI pager on the agent detail page. Commits `12368d2`…`8b84353`. 9 tests, two of which independently confirm no credential/hash ever appears in the evidence. |
| Artifact scanning | **Verified** | `malware_scanner.py` (clamd INSTREAM adapter, disabled by default), quarantine/scan routes. Commits `e68e32e`…`662cfff`. 22 tests against a fake local clamd server, no live ClamAV required. |
| Full tests pass | **Verified** | Full backend suite re-run after each milestone; latest run **423 passed, 4 skipped** (skips are the Windows-only symlink tests that run for real on CI's `ubuntu-latest`), 0 failed. Frontend: lint clean, 87/87 unit tests, production build succeeds, each re-verified after every milestone in this session. |
| E2E covers every page | **Verified** (pre-existing to this work) | `frontend/e2e/every-page.spec.ts` — 38/38 passing, fixed in the earlier Stage 2 work (commits `b29c7dd`, `a3da772`) and unaffected by Stage 3 (Stage 3 touched no frontend routes it covers). Not re-run this session since no route/page behavior changed — **recommend one fresh run before calling P0 fully closed**, see Remaining risks below. |
| Production rehearsal and final security review pass | **In progress** | Full `scripts/run_final_security_review.py` run after the PyJWT addition (Milestone 2): pip-audit, bandit, npm audit, secret-scan, SBOM generate/verify, both container scans all passed. **Not re-run since** (Milestones 3–5 added no new dependency, so SBOM is unaffected, but the container-scan/production-rehearsal artifacts are now several commits stale). Recommend one more full run before this item is marked Verified. |
| No security exception disguised as a pass | **Verified** | No `#nosec`, no suppressed bandit/pip-audit findings, no skipped security-relevant test introduced this session. Confirmed via `bandit -lll` (0 findings) after every milestone. |
| Independent review recorded for OIDC/JWT and other high-impact authentication logic | **Not applicable to self-review; Planned for a real independent reviewer** | Everything in this session was written and reviewed by the same model (me). I self-reviewed carefully (e.g. caught and fixed the HS256-test-construction issue in Milestone 2, the `_clamd_instream` try-block bug and the fake-server TCP-framing bug in Milestone 5), but that is not independent review in the sense this line means. **This is a real, explicit gap**: OIDC/JWT verification (`enterprise_sso.py`) and certificate authentication (`agent_certificate_auth.py`) are exactly the kind of high-impact authentication logic that should get a second set of human (or at least separately-prompted/different-tool) eyes before this platform is called commercially ready. Flagging for Michael rather than claiming it's done. |

### Operations/structural corrections named in the original task but not in the addendum's P0 list

These were part of the original engineering task's "Operations and structural corrections" section. The addendum doesn't explicitly re-list them, but they're prerequisites the addendum assumes (e.g. P2 says "after a complete baseline Alembic migration"). None are started yet.

| Requirement | Status | Evidence |
|---|---|---|
| Full `.env.production.example` audit | **In progress** | Every variable *this session's features* introduced is documented (`GREYGUARD_SSO_REDIRECT_URI`, `GREYGUARD_TRUST_CLIENT_CERT_HEADERS`, `GREYGUARD_MALWARE_SCANNING_ENABLED`, `GREYGUARD_CLAMD_HOST`/`PORT`). The earlier-identified gap (signing/backup/Vault keys from before this session: `GREYGUARD_REPORT_SIGNING_KEY`, `GREYGUARD_POLICY_SIGNING_KEY`, `GREYGUARD_RELEASE_SIGNING_KEY`, `GREYGUARD_BACKUP_KEY`, `VAULT_ADDR`/`VAULT_TOKEN`) is still open — a full audit pass hasn't been done. |
| PostgreSQL-native backup/restore scripts | **Planned** | Not started. `database_ops.py` remains SQLite-only; no `pg_dump`/`pg_basebackup` procedure exists. Recorded as a gap in `stage-2-reconciliation.md` §1 (superseded) — the delivery-related part of that gap is now closed by Milestone 1; the backup/restore part is unrelated and still open. |
| Docs correction: Alembic doesn't manage the full schema | **Planned** | Not started. Still true: one migration (`20261005_01_migration_control.py`) manages only an evidence table; the ~76 application tables are created imperatively at import time across ~28 modules (now including this session's `agent_credential_events`, `oidc_login_attempts`, `outbound_delivery_evidence`/`outbound_allowed_private_hosts`). |
| Full baseline Alembic migration before Phase C | **Planned, and explicitly gates P2** | Not started. The addendum's P2 depends on this exact step ("after a complete baseline Alembic migration"), so it must happen before any tenant-model work, not just before this document calls it done. |
| Reconcile the two Python SDKs | **Planned** | Not started. `backend/sdk/greyguard_client.py` and `sdk/python/greyguard_sdk/` remain two independently-referenced clients. |
| Pin FastAPI/Uvicorn | **Deferred — needs your explicit approval** | Not started; this is a dependency-version change, which the working instructions for this whole engagement require stopping for before doing. |
| Remove empty scaffolding (`routers/services/core/schemas/utils`) | **Planned** | Not started. Still present, still empty, still unused. |
| PostgreSQL parity tests for `db_compat.py` | **Planned** | Not started. The hand-rolled SQLite→Postgres translator is unchanged; this session added new raw SQL (credential/SSO/outbound-delivery/workload tables) that has **not** been parity-tested against Postgres, only exercised against SQLite in the test suite. This is a slightly elevated version of the pre-existing risk noted in the original review (`db_compat.py`'s table-name-specific special-casing) — new tables added this session don't need special-casing (none use `INSERT OR REPLACE`/`INSERT OR IGNORE`), but they are still unverified against a live Postgres instance. |

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
| Backup/restore/upgrade/rollback/tenant-deletion rehearsals | **In progress (partial)** | `scripts/rehearse_production.py`, `scripts/run_disaster_recovery_drill.py`, `scripts/verify_postgresql_parity.py` exist and have run successfully before (per `artifacts/production-rehearsal.json`, dated before this session's changes). SQLite-only backup/restore (see P0 operations-corrections table above) and tenant-deletion rehearsal (no tenancy yet) remain open. |

---

## Summary

**Done this session, confirmed with evidence:** all five Stage 3 security milestones (P0's core engineering content). Full backend and frontend test suites pass as of the last commit (`662cfff`).

**Real open items before P0 can be called fully closed** (in priority order):
1. Independent review of `enterprise_sso.py` and `agent_certificate_auth.py` by someone/something other than me.
2. One fresh full E2E run and one fresh `run_final_security_review.py` run, since several commits have landed since each was last executed.
3. The eight "operations and structural corrections" items — none started, all still accurate as originally scoped.

**Everything from P1 onward is correctly untouched**, per your standing instruction and the addendum's own sequencing. I have not begun branded-interface, tenancy/billing, or public-website work, and will not without your explicit go-ahead at each checkpoint.

**Nothing has been pushed.** All work is in local commits on `main`, per your instruction.
