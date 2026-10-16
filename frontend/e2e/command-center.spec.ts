import { expect, test } from "./fixtures"

import { adminSession, openWithSession } from "./session"

// The P1.4 Command Center shows live data from the backend, each figure drilling through to the
// page that holds its records, and no posture claim that isn't backed by data. P7.5 batch 3 adds
// a view per role and panels a person can pin or hide; the auditor's own view is checked in
// permission-gating.spec.ts with a real AUDITOR session. Each test makes one page load (plus one
// reload), to keep this suite well inside the API's per-client rate limit.

let session: Record<string, string> = {}
test.beforeAll(() => { session = adminSession() })

test("the Command Center shows live figures, linked panels and an honest offline state", async ({ page, context }) => {
  await openWithSession(page, session, "/dashboard")

  // Posture figures come from the API.
  const count = await page.evaluate(async () => {
    const response = await fetch("/api/tool-requests?approval_status=PENDING&limit=200", { headers: { "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" } })
    return (await response.json()).count as number
  })
  const stats = page.getByRole("region", { name: "Security posture" })
  const approvals = stats.getByRole("link", { name: /Pending approvals/ })
  await expect(approvals).toContainText(String(count), { timeout: 15_000 })

  // Each panel has a heading and a route to its full page.
  for (const [heading, link] of [["Approval queue", "Open approvals"], ["Open incidents", "Incident Center"], ["Agent risk", "Risk Center"], ["Readiness", "Getting Started"], ["Latest decisions and events", "Open Audit Trail"]]) {
    const panel = page.getByRole("region", { name: heading })
    await expect(panel).toBeVisible({ timeout: 15_000 })
    await expect(panel.getByRole("link", { name: link })).toBeVisible()
  }
  await expect(page.getByRole("region", { name: "Readiness" }).getByText(/\d+ of 9/)).toBeVisible({ timeout: 15_000 })

  // Offline is stated plainly rather than shown as live.
  await context.setOffline(true)
  await expect(page.getByText("You are offline")).toBeVisible()
  await context.setOffline(false)
  await expect(page.getByText("You are offline")).toHaveCount(0)

  // A figure drills through to its source page.
  await approvals.click()
  await expect(page).toHaveURL(/\/approvals$/)
})

test("a platform administrator switches views and customizes panels, and the choice persists", async ({ page }) => {
  await openWithSession(page, session, "/dashboard")
  const view = page.getByLabel("Command Center view")
  await expect(view).toHaveValue("platform-admin", { timeout: 15_000 })
  // A platform administrator who owns the organization is offered all six views.
  await expect(view.locator("option")).toHaveText([
    "Platform Administrator", "Security Analyst", "Approver", "Auditor", "Organization Owner", "Billing Administrator",
  ])
  await expect(page.getByRole("heading", { name: "Approval queue" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Plan & usage" })).toHaveCount(0)

  await view.selectOption("billing")
  await expect(page.getByRole("heading", { name: "Plan & usage" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Approval queue" })).toHaveCount(0)
  await expect(page.getByText("The plan, its limits and what is in use")).toBeVisible()

  // Pin a panel the view does not include, and hide one it does.
  await page.getByRole("button", { name: "Customize" }).click()
  const dialog = page.getByRole("dialog", { name: "Customize the Command Center" })
  await dialog.getByRole("checkbox", { name: /Compliance reports/ }).check()
  await dialog.getByRole("checkbox", { name: /Readiness/ }).uncheck()
  await dialog.getByRole("button", { name: "Close" }).click()
  await expect(page.getByRole("heading", { name: "Compliance reports" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Readiness" })).toHaveCount(0)

  // The view and the panels survive a reload for this account.
  await page.reload()
  await expect(page.getByLabel("Command Center view")).toHaveValue("billing", { timeout: 15_000 })
  await expect(page.getByRole("heading", { name: "Compliance reports" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Readiness" })).toHaveCount(0)

  // Reset brings back the view's own panels; switch back so other specs see the default.
  await page.getByRole("button", { name: "Customize" }).click()
  await dialog.getByRole("button", { name: "Reset to this view's panels" }).click()
  await dialog.getByRole("button", { name: "Close" }).click()
  await expect(page.getByRole("heading", { name: "Readiness" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Compliance reports" })).toHaveCount(0)
  await page.getByLabel("Command Center view").selectOption("platform-admin")
})
