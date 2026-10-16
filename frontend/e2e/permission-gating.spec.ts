import { expect, test } from "@playwright/test"

// Confirms Phase 2's permission-gating actually changes what renders for a non-PLATFORM_ADMIN
// role, not just that pages don't crash (every-page.spec.ts already covers that, always as
// PLATFORM_ADMIN). Creates a real AUDITOR administrator via the bootstrap PLATFORM_ADMIN
// session, signs in as that AUDITOR, and checks mutation controls on the pages found to have
// been completely unguarded before this phase (see docs/roadmap/addendum-reconciliation.md).

const AUDITOR_EMAIL = "e2e-auditor@example.com"
const AUDITOR_PASSWORD = "AuditorOnlyReadAccess!2026"
// A PLATFORM_ADMIN account that is not an install operator - the shape every org owner has.
const ORG_ADMIN_EMAIL = "e2e-org-admin@example.com"
const ORG_ADMIN_PASSWORD = "OrgAdminNotOperator!2026"

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
  const create = (email: string, password: string, role: string) => page.evaluate(
    async ({ email, password, role }) => {
      const token = sessionStorage.getItem("greyguard_admin_pin")
      const response = await fetch("/api/administrators", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Pin": token ?? "" },
        body: JSON.stringify({ email, display_name: `E2E ${role}`, role, password }),
      })
      return { status: response.status, body: await response.text() }
    },
    { email, password, role },
  )
  // 409 if a prior run already created the account.
  expect([201, 409]).toContain((await create(AUDITOR_EMAIL, AUDITOR_PASSWORD, "AUDITOR")).status)
  expect([201, 409]).toContain((await create(ORG_ADMIN_EMAIL, ORG_ADMIN_PASSWORD, "PLATFORM_ADMIN")).status)
  await page.close()
})

async function signInAsAuditor(page: import("@playwright/test").Page) {
  await signIn(page, AUDITOR_EMAIL, AUDITOR_PASSWORD)
}

async function signIn(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/")
  await page.locator("#admin-email").fill(email)
  await page.locator("#admin-password").fill(password)
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

test("AUDITOR gets the shared access-denied state on abuse protection (install-operator-only resource)", async ({ page }) => {
  // GET /abuse-protection itself calls require_install_operator() server-side - this is not a
  // mutation-only restriction, so the console explains the requirement instead of rendering the page.
  await signInAsAuditor(page)
  const pageRequests: string[] = []
  page.on("request", (request) => { if (request.url().includes("/api/abuse-protection")) pageRequests.push(request.url()) })
  await page.goto("/abuse-protection")
  await expect(page.getByRole("heading", { name: "Install operator access required" })).toBeVisible({ timeout: 15_000 })
  await expect(page).toHaveURL(/\/abuse-protection$/)
  await page.getByRole("link", { name: "Go to the Command Center" }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
  expect(pageRequests, "the denied page must not request its data").toEqual([])
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

test("an org PLATFORM_ADMIN who is not an install operator cannot reach install-wide controls", async ({ page }) => {
  await signIn(page, ORG_ADMIN_EMAIL, ORG_ADMIN_PASSWORD)
  // Tenant-scoped admin pages stay available to the org's PLATFORM_ADMIN as workspace tabs...
  await page.goto("/compliance")
  const reportTabs = page.getByRole("navigation", { name: "Reports & Exports sections" })
  await expect(reportTabs.getByRole("link", { name: "Security Exports" })).toBeVisible({ timeout: 15_000 })
  // ...but install-wide ones are neither listed in any workspace that holds them nor reachable directly.
  for (const [workspacePath, hiddenPath] of [["/agents", "/enterprise-identity"], ["/endpoint-telemetry", "/observability"], ["/audit", "/audit-integrity"], ["/account-security", "/team"], ["/account-security", "/abuse-protection"]]) {
    await page.goto(workspacePath)
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 })
    await expect(page.locator(`a[href="${hiddenPath}"]`)).toHaveCount(0)
  }
  await page.goto("/observability")
  await expect(page.getByRole("heading", { name: "Install operator access required" })).toBeVisible({ timeout: 15_000 })
  await page.goto("/team")
  await expect(page.getByRole("heading", { name: /Install operator access required/i })).toBeVisible({ timeout: 15_000 })
  // The server enforces it too, not just the UI.
  const status = await page.evaluate(async () => {
    const response = await fetch("/api/administrators", { headers: { "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" } })
    return response.status
  })
  expect(status).toBe(403)
})

test("the Team page marks install operators and exposes the operator toggle", async ({ page }) => {
  await signIn(page, process.env.GREYGUARD_E2E_EMAIL!, process.env.GREYGUARD_E2E_PASSWORD!)
  await page.goto("/team")
  const operatorCard = page.locator(".team-card", { hasText: process.env.GREYGUARD_E2E_EMAIL! })
  await expect(operatorCard.getByText("Install operator")).toBeVisible({ timeout: 15_000 })
  const orgAdminCard = page.locator(".team-card", { hasText: ORG_ADMIN_EMAIL })
  await expect(orgAdminCard.getByText("Install operator")).toHaveCount(0)
  await orgAdminCard.click()
  await expect(page.getByRole("checkbox", { name: /Install operator/i })).not.toBeChecked()
})

test("AUDITOR sees only the workspaces and tabs its role may open", async ({ page }) => {
  await signInAsAuditor(page)
  // The Command Center opens on the Auditor view, the only one this role is offered, so there is
  // no view switcher and no approval queue.
  await expect(page.getByRole("heading", { name: "Latest decisions and events" })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole("heading", { name: "Compliance reports" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Approval queue" })).toHaveCount(0)
  await expect(page.getByLabel("Command Center view")).toHaveCount(0)
  const sidebar = page.getByRole("navigation", { name: "Primary navigation" })
  await expect(sidebar.getByRole("link", { name: /Requests & Approvals/ })).toBeVisible({ timeout: 15_000 })
  // Every Containment page needs PLATFORM_ADMIN, so the workspace itself is not offered.
  await expect(sidebar.getByRole("link", { name: /Containment/ })).toHaveCount(0)
  // Open workspaces show only the permitted tabs.
  await page.goto("/approvals")
  const tabs = page.getByRole("navigation", { name: "Requests & Approvals sections" })
  await expect(tabs.getByRole("link")).toHaveCount(3, { timeout: 15_000 })
  await page.goto("/policies")
  const controls = page.getByRole("navigation", { name: "Policies & Controls sections" })
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 })
  await expect(controls).toHaveCount(0)
  await expect(page.locator('a[href="/secrets"]')).toHaveCount(0)
})

test("AUDITOR sees records but not the contextual actions its role may not take", async ({ page }) => {
  await signInAsAuditor(page)
  // Threat register: readable by every role, reviewable only by a platform administrator.
  await page.goto("/threat-register")
  await expect(page.getByRole("table", { name: "Threats" })).toBeVisible({ timeout: 15_000 })
  // Each row's action is labelled "Review <threat title>"; the "Review by" column header is a sort control.
  await expect(page.getByRole("button", { name: /^Review (?!by$)/ })).toHaveCount(0)
  // Policy change control: an auditor can read versions but cannot draft, approve or reject.
  await page.goto("/policies")
  await expect(page.getByRole("region", { name: "Policy versions and approvals" })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole("button", { name: "Create draft" })).toHaveCount(0)
  await expect(page.getByRole("button", { name: /^(Approve|Reject)$/ })).toHaveCount(0)
})
