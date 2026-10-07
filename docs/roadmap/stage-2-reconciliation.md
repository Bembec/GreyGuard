# Stage 2 Reconciliation — GreyGuard Master Roadmap

**Status:** interim reconciliation. **The master roadmap/handover DOCX was not found anywhere in this repository** (searched for `*.docx`, `*roadmap*`, `*handover*`, `*master*` across the full tree). This document exists because Stage 2 of the current work plan requires reconciling implementation reality against that roadmap's Section 8/9/19/20 status, and there is nothing in the repo to reconcile against directly.

**Action needed from Michael:** copy the master roadmap DOCX into this repository at:

```
docs/roadmap/greyguard-master-roadmap.docx
```

Once it's in place, this Markdown file should be re-reconciled against its actual section numbering and wording — the section references below (8, 9, 19, 20) are taken from the task instructions that produced this document, not read from the DOCX itself, since it isn't accessible here.

---

## 1. Corrected status: Section 8 / Section 9 (outbound delivery & integrations)

**Prior status (per task instruction):** "configuration and queues" marked complete.

**Status as of Stage 3 Milestone 1: now actually complete.** `backend/app/outbound_delivery.py` (new) provides a shared SSRF-safe sender and `backend/app/outbound_worker.py` (new) runs a background delivery loop inside the API process, wired into `api.py`'s lifespan. `notification_delivery.process_deliveries`, `incident_integrations.process_incidents`, `security_exports.process_queue`, and `report_governance.run_due_schedules` are now actually invoked on an interval and each claims its rows atomically before acting, so the two-worker production deployment can run both loops without double-sending.

Covered: HTTPS-only destinations; fresh DNS resolution and address validation on every attempt (blocking loopback/link-local/multicast/unspecified/reserved/cloud-metadata unconditionally, private ranges unless a Platform Administrator allows that exact hostname); the TCP connection is pinned to the validated address so a later DNS change can't redirect it (DNS-rebinding resistant); redirects are never followed; bounded connect/read/total timeouts; capped exponential backoff with jitter; a dead-letter state after each destination's configured attempt limit; an `Idempotency-Key` on every request; HMAC request signing for security-export destinations that configure a signing key; append-only evidence (`outbound_delivery_evidence`) for enqueue/attempt/success/failure/retry/dead-letter/blocked; and `safe_error()` redaction on every stored error message as a backstop against a dependency ever echoing something sensitive.

**Known, deliberately out-of-scope gaps from this milestone** (fail closed with a clear dead-letter error, never silently dropped or mis-sent): EMAIL notification delivery (needs an SMTP transport) and Syslog-over-TLS export delivery (needs a raw TLS socket transport, not HTTP). Both are flagged in `docs/communication-integrations.md` / `docs/security-export-integrations.md`.

**Still open:** no frontend UI yet for the new private-destination SSRF allowlist (`GET/POST /outbound-delivery/private-allowlist`, `DELETE /outbound-delivery/private-allowlist/{host}`) — an administrator can call the API directly today; a console page is a reasonable fast-follow, not part of this milestone.

## 2. CSRF — confirmed already covered

Verified in code, not merely asserted:

- `backend/app/api.py:333` — the only session-identifying value accepted on requests is the custom header `X-Admin-Pin` (plus `X-Agent-Name`/`X-Agent-Key` for agent calls). Searched the entire backend for `set_cookie` / session cookies: **none exist**. The frontend stores the token in `sessionStorage` (`frontend/src/context/AuthContext.tsx`) and attaches it as an explicit header on each request — never as an ambient, browser-auto-attached credential.
- Because there is no cookie-based (or otherwise ambient) credential, a third-party site cannot force an authenticated request through a victim's browser the way classic CSRF requires — it cannot read `sessionStorage` cross-origin and cannot make the browser auto-attach `X-Admin-Pin`.
- `backend/app/production_config.py` independently fails closed on wildcard CORS origins in production (verified via `backend/tests/test_production_readiness.py`), closing the one realistic variant of this class of attack (a permissive CORS policy that would let a malicious origin read responses).

**Conclusion:** CSRF is structurally covered by the header-based auth design, not by an explicit CSRF-token mechanism, and does not need one. No code change required. Record this as closed for Section 8/9 purposes.

## 3. Threat register — assessment fields present and populated

`backend/app/threat_register.py:38-57`. The `threat_register` table carries real assessment fields, not placeholders: `severity`, `asset`, `threat_actor`, `attack_path`, `existing_controls` (JSON), `residual_risk`, `test_evidence` (JSON), `incident_response`, `owner`, `review_date`, plus `updated_at`/`updated_by`. Every change is versioned into `threat_register_history` with a full snapshot. Seed logic explicitly protects reviewer edits from being overwritten by placeholder upgrades ("Upgrade only untouched placeholder rows; never overwrite a reviewer's edits" — `threat_register.py:58`).

**Status: complete as implemented.** Record this against whichever roadmap item tracks threat-register depth.

## 4. Symlink protection — implemented and tested

`backend/app/tool_gateway.py` (`normalize_target`) refuses any sandboxed path that resolves through a symlink to a location outside the sandbox root. Covered by `backend/tests/test_symlink_escape.py`, parametrized over symlinked file, symlinked directory, and nested symlinked-directory escape attempts, plus a positive control (ordinary in-sandbox files still work).

**Caveat recorded here, not previously visible:** on this Windows development machine, these tests self-skip (`pytest.skip(...)`) unless symlink creation is permitted (Developer Mode or admin rights) — confirmed by running the full backend suite (280 passed, 4 skipped on this run; the symlink tests account for the skips). This is **not** a gap in the control itself: `.github/workflows/ci.yml` and `security.yml` run on `ubuntu-latest`, where symlink creation needs no special privilege, so CI exercises these tests for real on every push. Local Windows runs will always show them as skipped — that's expected, not a regression.

## 5. Corrected simulation results

`backend/app/adversarial_simulations.py:56` — the `simulation_runs` table has a hard SQL constraint: `simulated INTEGER NOT NULL CHECK(simulated=1)`. Every scenario in the catalog carries `fictional_target: "reserved-target.example"` and `operational: False` (`adversarial_simulations.py:57`). There is no code path that can mark a simulation run as operational or point it at a real target — it's enforced at the schema level, not just by convention in application code.

**Status: confirmed non-operational by construction.** Safe to record Simulation Lab results as "adversarial simulation evidence, no live/operational risk" without further caveats.

## 6. Stage 2 browser coverage — now actually green

Separate from the roadmap items above: the Stage 2 "finish browser coverage" task (fixing AppShell's duplicate `<h1>`) is complete and verified with a fresh run, not the stale committed `frontend/test-results/e2e-results.json`:

- Root cause and fix: see commits `fix(frontend): stop AppShell rendering a duplicate page-level <h1>` and `fix(frontend): give every page its own real <h1> and correct e2e assertions`.
- Fixing the shell's duplicate heading exposed three pages that had never had a real heading of their own (`DashboardPage`, `AgentDetailPage`, `RequestDetailPage` in their loading/error branches) — all three now have one.
- Verified this run: `npm run lint` (clean, pre-existing warnings only), `npm run test` (87/87), `npm run build` (clean), full Playwright suite **38/38 passed, 0 failed, 0 skipped**.

---

## Open question for Michael

Everything above is grounded in the current code, not in roadmap text, because the roadmap text isn't available here. Once `docs/roadmap/greyguard-master-roadmap.docx` is copied into the repo, this file should be regenerated against its actual section structure so "Section 8"/"Section 9" above map to whatever they're really called in the source document.
