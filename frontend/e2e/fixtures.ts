import { test as base } from "@playwright/test"
import { existsSync } from "node:fs"
import { join } from "node:path"
import { DatabaseSync } from "node:sqlite"

// Every spec imports `test` from here. Before each test, the isolated e2e backend's rate-limit
// counters are cleared, so no test inherits another's request budget or a block it caused.
//
// This touches only the throwaway database scripts/e2e_backend.py creates in .e2e-data for this
// run; it is not an API and nothing in the application can call it. The limits themselves come
// from the test-only override (docs/testing/e2e-rate-limits.md); ADMIN_AUTH keeps its real limit.
const E2E_DATABASE = join(import.meta.dirname, "..", "..", ".e2e-data", "greyguard.db")

export function resetRateLimitCounters() {
  if (!existsSync(E2E_DATABASE)) return
  const database = new DatabaseSync(E2E_DATABASE)
  try {
    database.exec("PRAGMA busy_timeout = 5000")
    database.exec("DELETE FROM rate_limit_counters")
  } finally {
    database.close()
  }
}

export const test = base.extend<{ isolatedRateLimits: void }>({
  // Playwright requires the object pattern even when a fixture uses no other fixtures.
  // eslint-disable-next-line no-empty-pattern
  isolatedRateLimits: [async ({}, use) => {
    resetRateLimitCounters()
    await use()
  }, { auto: true }],
})

// Everything else (expect, types) as Playwright exports it; the local `test` above takes precedence.
export * from "@playwright/test"
