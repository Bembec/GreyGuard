import { expect, test } from "@playwright/test"

import { adminSession, openWithSession } from "./session"

// P7.5 batch 2: an administrator registers an agent from the console, and Getting Started's
// "Register your first agent" step opens that flow directly.

let session: Record<string, string> = {}
test.beforeAll(() => { session = adminSession() })

test("an administrator registers an agent and sees its credential once", async ({ page }) => {
  await openWithSession(page, session, "/agents?register=1")
  // Self-contained: new agents need a plan with capacity, so give the org one first.
  const plan = await page.evaluate(async () => {
    const headers = { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" }
    const me = await (await fetch("/api/auth/me", { headers })).json()
    return (await fetch(`/api/entitlements/${me.active_org_id}`, { method: "PUT", headers, body: JSON.stringify({ plan: "FOUNDATION", status: "ACTIVE" }) })).status
  })
  expect(plan).toBe(200)

  const dialog = page.getByRole("alertdialog", { name: "Register an agent" })
  await expect(dialog).toBeVisible({ timeout: 15_000 })
  const submit = dialog.getByRole("button", { name: "Register and issue credential" })
  const name = `e2e_agent_${Date.now()}`
  await dialog.getByLabel("Agent name").fill(name)
  // At least one scope is required.
  await expect(submit).toBeDisabled()
  await dialog.getByLabel("read_file").check()
  await submit.click()

  const credential = page.getByRole("dialog", { name: "Save this credential now" })
  await expect(credential).toBeVisible()
  await expect(credential.locator("code")).not.toHaveText("")
  await credential.getByRole("button", { name: "I have saved the credential" }).click()
  await expect(credential).toHaveCount(0)
  // The query string is cleared, so a reload does not reopen registration.
  await expect(page).toHaveURL(/\/agents$/)
  await expect(page.getByRole("table", { name: "Agents" }).getByText(name)).toBeVisible()

  // A second registration under the same name is refused, and the server's reason is shown.
  await page.getByRole("button", { name: "Register agent" }).click()
  await dialog.getByLabel("Agent name").fill(name)
  await dialog.getByLabel("read_file").check()
  await submit.click()
  await expect(dialog.getByRole("alert")).toContainText("already exists")
  await expect(page.getByRole("dialog", { name: "Save this credential now" })).toHaveCount(0)
})
