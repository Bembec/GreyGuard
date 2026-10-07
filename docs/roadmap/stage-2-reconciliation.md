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

**Corrected status: NOT complete.** Verified in code:

- `backend/app/notification_delivery.py` — `queue_notification()` inserts a row into the delivery queue. `process_deliveries(sender)` exists and would actually dispatch a queued notification, but **nothing in the codebase calls it** — no worker, no scheduled task, no startup hook. Confirmed by searching for callers of `process_deliveries` outside its own test file: none found in `api.py`, `main.py`, or any other runtime module.
- `backend/app/report_governance.py` — `create_schedule()` / `list_schedules()` store schedule rows; there is no runner that ever executes a due schedule.
- `backend/app/incident_integrations.py` and `backend/app/security_exports.py` have the equivalent "queue exists, nothing drains it" shape (`process_incidents`, `process_queue`).

**What this means concretely:** an administrator can configure a Slack/PagerDuty/Jira/ServiceNow/SIEM destination and the UI will accept it and show it as "configured," but no notification, incident ticket, SIEM export, or scheduled compliance report will ever actually be delivered until a real worker is wired up. This is Stage 3 Milestone 1 (secure outbound delivery) — tracked, not started.

**Why this matters for the roadmap:** "complete" should mean the feature does what an administrator would reasonably expect end-to-end. Configuration-and-queue-only is the groundwork for the feature, not the feature.

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
