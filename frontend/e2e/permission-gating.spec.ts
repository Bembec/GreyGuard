import { expect, test } from "@playwright/test"

// Confirms Phase 2's permission-gating actually changes what renders for a non-PLATFORM_ADMIN
// role, not just that pages don't crash (every-page.spec.ts already covers that, always as
// PLATFORM_ADMIN). Creates a real AUDITOR administrator via the bootstrap PLATFORM_ADMIN
// session, signs in as that AUDITOR, and checks mutation controls on the pages found to have
// been completely unguarded before this phase (see docs/roadmap/addendum-reconciliation.md).

const AUDITOR_EMAIL = "e2e-auditor@example.com"
const AUDITOR_PASSWORD = "AuditorOnlyReadAccess!2026"

test.beforeAll(async ({ browser }) => {
  test.setTimeout(120_000)
  const page = await browser.newPage()
  await page.goto("/")
  await page.locator("#admin-email").fill(process.env.GREYGUARD_E2E_EMAIL!)
  await page.locator("#admin-password").fill(process.env.GREYGUARD_E2E_PASSWORD!)
  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith("/auth/login") && response.request().method() === "POST", { timeout: 90_000 }),
    page.getByRole("button", { name: /Enter command center/i }).click(),
  ])
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(/Every action passes/i, { timeout: 30_000 })

  // Create the AUDITOR account as the bootstrap PLATFORM_ADMIN, via a real API call using the
  // session already established in the browser (not a separate unauthenticated fetch).
  const created = await page.evaluate(
    async ({ email, password }) => {
      const token = sessionStorage.getItem("greyguard_admin_pin")
      const response = await fetch("/api/administrators", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Pin": token ?? "" },
        body: JSON.stringify({ email, display_name: "E2E Auditor", role: "AUDITOR", password }),
      })
      return { status: response.status, body: await response.text() }
    },
    { email: AUDITOR_EMAIL, password: AUDITOR_PASSWORD },
  )
  expect([201, 409]).toContain(created.status) // 409 if a prior run already created it
  await page.close()
})

async function signInAsAuditor(page: import("@playwright/test").Page) {
  await page.goto("/")
  await page.locator("#admin-email").fill(AUDITOR_EMAIL)
  await page.locator("#admin-password").fill(AUDITOR_PASSWORD)
  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith("/auth/login") && response.request().method() === "POST", { timeout: 30_000 }),
    page.getByRole("button", { name: /Enter command center/i }).click(),
  ])
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(/Every action passes/i, { timeout: 15_000 })
}

test("AUDITOR does not see service account mutation controls", async ({ page }) => {
  await signInAsAuditor(page)
  await page.goto("/service-accounts")
  await expect(page.getByText(/read-only access to service accounts/i)).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole("button", { name: /New service account/i })).toHaveCount(0)
})

test("AUDITOR is redirected away from abuse protection (PLATFORM_ADMIN-only resource)", async ({ page }) => {
  // GET /abuse-protection itself calls require_platform_admin() server-side - this is not a
  // mutation-only restriction, so the frontend redirects instead of rendering a read-only view.
  await signInAsAuditor(page)
  await page.goto("/abuse-protection")
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 })
})

test("AUDITOR sees agent scope/credential controls as read-only", async ({ page }) => {
  await signInAsAuditor(page)
  await page.goto("/agents")
  const rows = page.locator(".agent-table tbody tr")
  const rowCount = await rows.count()
  test.skip(rowCount === 0, "no agents registered in this environment")
  await rows.first().click()
  await expect(page.getByText(/read-only access to scope boundaries/i)).toBeVisible({ timeout: 10_000 })
  await expect(page.getByRole("button", { name: /Rotate credential/i })).toHaveCount(0)
  await expect(page.getByRole("button", { name: /^Revoke$/i })).toHaveCount(0)
})
