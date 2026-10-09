import { expect, test } from "@playwright/test"

// Confirms P2.1's multi-org membership end to end in a real browser: the bootstrap
// PLATFORM_ADMIN creates a second organization (via the real API, same pattern as
// permission-gating.spec.ts's AUDITOR creation), the UserMenu's org switcher lists both, and
// switching actually changes which org the session acts as.

test("the bootstrap administrator can create a second org and switch between them", async ({ page }) => {
  await page.goto("/")
  await page.locator("#admin-email").fill(process.env.GREYGUARD_E2E_EMAIL!)
  await page.locator("#admin-password").fill(process.env.GREYGUARD_E2E_PASSWORD!)
  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith("/auth/login") && response.request().method() === "POST", { timeout: 90_000 }),
    page.getByRole("button", { name: /Enter command center/i }).click(),
  ])
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(/Every action passes/i, { timeout: 30_000 })

  const created = await page.evaluate(async () => {
    const token = sessionStorage.getItem("greyguard_admin_pin")
    const response = await fetch("/api/organizations", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Admin-Pin": token ?? "" },
      body: JSON.stringify({ name: "E2E Second Org", slug: "e2e-second-org" }),
    })
    return { status: response.status, body: await response.json() }
  })
  expect([201, 409]).toContain(created.status) // 409 if a prior run already created it

  await page.reload()
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(/Every action passes/i, { timeout: 30_000 })

  await page.getByRole("button", { name: /Platform Administrator/i }).click()
  await expect(page.getByRole("menuitemradio", { name: "Default Organization" })).toHaveAttribute("aria-checked", "true")
  const secondOrgOption = page.getByRole("menuitemradio", { name: "E2E Second Org" })
  await expect(secondOrgOption).toBeVisible()

  await Promise.all([
    page.waitForResponse((response) => response.url().endsWith("/auth/active-org") && response.request().method() === "POST"),
    secondOrgOption.click(),
  ])

  // selectOrg() does not close the panel after switching (unlike the other menu actions), so
  // the same open menu reflects the updated active org once the switch call resolves.
  await expect(page.getByRole("menuitemradio", { name: "E2E Second Org" })).toHaveAttribute("aria-checked", "true")
  await expect(page.getByRole("menuitemradio", { name: "Default Organization" })).toHaveAttribute("aria-checked", "false")
})
