import { expect, test } from "@playwright/test"

import { adminSession, openWithSession } from "./session"

// The P1.4 Command Center shows live data from the backend, each figure drilling through to the
// page that holds its records, and no posture claim that isn't backed by data. One page load
// covers every check, to keep this suite well inside the API's per-client rate limit.

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
