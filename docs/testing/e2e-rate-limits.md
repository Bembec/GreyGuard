# Browser end-to-end tests and rate limits

**Decided by the owner on 2026-10-16.** Production keeps its rate limits. The full Playwright suite runs against a throwaway backend with higher read limits, switched on explicitly and only there.

## Why

The suite drives one browser from one client address for about two minutes. At the production `GENERAL` limit (300 requests a minute per client) it ran right at the edge. The backend recorded limit breaches even in passing runs, and about one full run in four failed a late test with "Waiting for the control plane to respond". Running the suite in shards was worse: each shard signs in again and trips the sign-in limit.

## What the override changes

| Category | Production | Under the e2e override |
|---|---|---|
| `GENERAL` (most console reads) | 300 a minute | 3000 a minute |
| `AGENT_ACTION` (includes the console's `GET /tool-requests`) | 120 a minute | 1200 a minute |
| `ADMIN_AUTH` (sign-in) | 20 per 5 minutes | **unchanged** |
| `SERVICE_ACCOUNT` | 60 a minute | **unchanged** |

Sign-in protection is never raised, so the suite exercises it as it ships.

## How it is switched on

It needs both of these, set by `scripts/e2e_backend.py` for the backend Playwright starts:

- `GREYGUARD_ENV=test`
- `GREYGUARD_E2E_RATE_LIMIT_OVERRIDE=e2e-test-environment-only` (this exact value)

## Why it cannot reach production by accident

- **Refused at startup** (`production_config.load_production_config` → `abuse_protection.e2e_override_active`):
  - the variable present with any `GREYGUARD_ENV` other than `test`, production included;
  - any value other than the exact sentinel (`1`, `true` and the like are refused, not ignored).
- **Marked when seeded.** Limits seeded under the override are recorded with `updated_by = e2e-test-override`. A production start refuses a database holding such a row (`assert_no_test_override_in_production`), so a test database cannot carry the higher limits into production.
- **Production refuses SQLite** anyway, and the e2e backend uses a fresh SQLite folder (`.e2e-data`) on every run.
- **Tests:** `backend/tests/test_rate_limit_override.py` proves that production and every non-test environment keep 300 a minute, that only the exact sentinel works, that sign-in limits are never raised, and that production refuses an override-seeded database. Each guard was mutation-checked.

## Isolation between tests

Every spec imports `test` from `frontend/e2e/fixtures.ts`. Its automatic fixture clears the e2e backend's `rate_limit_counters` before each test, so no test inherits another's request budget or a block it caused. It touches only the throwaway `.e2e-data` database, through Node's built-in SQLite. It is not an API, and nothing in the application can call it.

One consequence: lockout that builds up across several tests is not exercised by the browser suite. The backend suite covers lockout directly (`test_abuse_protection.py`).

## Running

`npm run build`, then `npx playwright test` from `frontend/`. Run the suite whole: sharding repeats the global sign-in.
