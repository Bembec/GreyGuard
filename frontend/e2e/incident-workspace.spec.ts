import { expect, test } from "./fixtures"

import { adminSession, openWithSession } from "./session"

// P7.5 item 5: an incident opens on its own investigation page, explains what happened exactly,
// and every change lands in its action record. One page load plus in-app navigation.

let session: Record<string, string> = {}
test.beforeAll(() => { session = adminSession() })

test("an incident is investigated on its own page and every change is recorded", async ({ page }) => {
  await openWithSession(page, session, "/getting-started")
  const agentName = `incident_agent_${Date.now()}`
  const email = await page.evaluate(async (name) => {
    const headers = { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" }
    const me = await (await fetch("/api/auth/me", { headers })).json()
    await fetch(`/api/entitlements/${me.active_org_id}`, { method: "PUT", headers, body: JSON.stringify({ plan: "FOUNDATION", status: "ACTIVE" }) })
    const registered = await (await fetch("/api/agents", { method: "POST", headers, body: JSON.stringify({ agent_name: name, scopes: ["send_email"] }) })).json()
    // send_email is BLOCK by default policy: high-severity evidence, so an incident.
    await fetch("/api/tool-requests", { method: "POST", headers: { "Content-Type": "application/json", "X-Agent-Name": name, "X-Agent-Key": registered.credential },
      body: JSON.stringify({ action: "send_email", target: "ops@example.com", payload: {} }) })
    return me.email as string
  }, agentName)

  // Open it from Incident Center: the row leads to the incident's own page.
  await page.getByRole("link", { name: /Incident Response/ }).first().click()
  await page.getByRole("button", { name: new RegExp(agentName) }).first().click()
  await expect(page).toHaveURL(/\/incidents\/[^/]+$/)
  await expect(page.getByRole("heading", { level: 1 })).toContainText(agentName, { timeout: 15_000 })

  // What happened is the exact explanation.
  const card = page.getByRole("region", { name: "Why GreyGuard decided this" })
  await expect(card).toContainText("Blocked because policy v1 does not allow send_email.")
  await expect(card).toContainText("Exact decision record")
  await expect(page.getByTestId("incident-meta")).toContainText("No SLA set")

  // Acknowledge, assign, note: each lands in the action record with the person who did it.
  await page.getByRole("button", { name: "Acknowledge" }).first().click()
  await page.getByRole("button", { name: "Action record" }).click()
  await expect(page.getByText("Status changed from open to acknowledged.")).toBeVisible({ timeout: 15_000 })
  await page.getByLabel("Choose an owner").selectOption(email)
  await page.getByRole("button", { name: "Assign" }).click()
  await expect(page.getByText(`Owner set to ${email}.`)).toBeVisible({ timeout: 15_000 })
  await page.getByRole("button", { name: "Add a note" }).click()
  await page.getByLabel("Note", { exact: true }).fill("Checked with the team: expected test traffic.")
  await page.getByRole("button", { name: "Add note" }).click()
  await expect(page.getByText("Note: Checked with the team: expected test traffic.")).toBeVisible({ timeout: 15_000 })
  await expect(page.locator(".incident-workspace__entries li.is-record small").first()).toContainText(email)

  // Phone width: one column, with the primary action in a bar at the bottom.
  await page.setViewportSize({ width: 390, height: 844 })
  const bar = page.locator(".incident-workspace__mobile-bar")
  await expect(bar).toBeVisible()
  await expect(bar.getByRole("button", { name: "Start investigating" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
})

test("containment from an incident needs the typed target and a reason, and export downloads a verifiable package", async ({ page }) => {
  await openWithSession(page, session, "/getting-started")
  const agentName = `contain_agent_${Date.now()}`
  const alertId = await page.evaluate(async (name) => {
    const headers = { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" }
    const me = await (await fetch("/api/auth/me", { headers })).json()
    await fetch(`/api/entitlements/${me.active_org_id}`, { method: "PUT", headers, body: JSON.stringify({ plan: "FOUNDATION", status: "ACTIVE" }) })
    const registered = await (await fetch("/api/agents", { method: "POST", headers, body: JSON.stringify({ agent_name: name, scopes: ["send_email"] }) })).json()
    await fetch("/api/tool-requests", { method: "POST", headers: { "Content-Type": "application/json", "X-Agent-Name": name, "X-Agent-Key": registered.credential },
      body: JSON.stringify({ action: "send_email", target: "ops@example.com", payload: {} }) })
    const alerts = await (await fetch("/api/alerts", { headers })).json()
    const list = (Array.isArray(alerts) ? alerts : alerts.alerts ?? alerts.items ?? []) as { alert_id: string; agent_name: string }[]
    return list.find((alert) => alert.agent_name === name)?.alert_id ?? ""
  }, agentName)
  expect(alertId).not.toBe("")

  await page.evaluate((path) => { window.history.pushState({}, "", path); window.dispatchEvent(new PopStateEvent("popstate")) }, `/incidents/${alertId}`)
  await expect(page.getByRole("heading", { level: 1 })).toContainText(agentName, { timeout: 15_000 })

  // Revoke: the confirm button stays disabled until the exact agent name and a reason are given.
  await page.getByRole("button", { name: "Revoke the agent's credential" }).click()
  const dialog = page.getByRole("alertdialog")
  const confirm = dialog.getByRole("button", { name: "Revoke the agent's credential" })
  await dialog.getByLabel(/to confirm/).fill("wrong_name")
  await dialog.getByLabel("Reason (recorded)").fill("Suspicious send_email attempts.")
  await expect(confirm).toBeDisabled()
  await dialog.getByLabel(/to confirm/).fill(agentName)
  await confirm.click()
  await page.getByRole("button", { name: "Action record" }).click()
  await expect(page.getByText(`Containment: revoked the credential of ${agentName}.`)).toBeVisible({ timeout: 15_000 })

  // Export: a JSON download whose manifest covers every part, and the export is recorded.
  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("button", { name: "Export package" }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe(`greyguard-incident-${alertId.replace(/[^a-zA-Z0-9_-]/g, "-")}.json`)
  const { readFile } = await import("node:fs/promises")
  const pkg = JSON.parse(await readFile((await download.path())!, "utf8"))
  expect(pkg.format).toBe("greyguard.incident-package/1")
  expect(Object.keys(pkg.manifest.parts).sort()).toEqual(Object.keys(pkg.parts).sort())
  expect(JSON.stringify(pkg.parts.action_record)).toContain("revoke_credential")
  await expect(page.getByText("Incident package exported.")).toBeVisible({ timeout: 15_000 })
})

test("an admin sets response targets from the suggestions, and incidents are measured against them", async ({ page }) => {
  await openWithSession(page, session, "/getting-started")
  const agentName = `sla_agent_${Date.now()}`
  const orgId = await page.evaluate(async (name) => {
    const headers = { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" }
    const me = await (await fetch("/api/auth/me", { headers })).json()
    await fetch(`/api/entitlements/${me.active_org_id}`, { method: "PUT", headers, body: JSON.stringify({ plan: "FOUNDATION", status: "ACTIVE" }) })
    const registered = await (await fetch("/api/agents", { method: "POST", headers, body: JSON.stringify({ agent_name: name, scopes: ["send_email"] }) })).json()
    await fetch("/api/tool-requests", { method: "POST", headers: { "Content-Type": "application/json", "X-Agent-Name": name, "X-Agent-Key": registered.credential },
      body: JSON.stringify({ action: "send_email", target: "ops@example.com", payload: {} }) })
    return me.active_org_id as string
  }, agentName)

  try {
    await page.getByRole("link", { name: /Incident Response/ }).first().click()
    await page.getByRole("button", { name: "Response targets" }).click()
    const panel = page.getByRole("region", { name: "Response targets" })
    await expect(panel).toContainText("No SLA set")
    await panel.getByRole("button", { name: "Fill in the suggestions" }).click()
    await panel.getByRole("button", { name: "Save targets" }).click()
    await expect(panel).toContainText("Set by", { timeout: 15_000 })

    await page.getByRole("button", { name: new RegExp(agentName) }).first().click()
    await expect(page.getByRole("heading", { level: 1 })).toContainText(agentName, { timeout: 15_000 })
    await expect(page.getByTestId("incident-meta")).toContainText(/Acknowledge within target \((15 minutes|1 hour)\) · due/)

    // Phone width: the targets form stays usable without sideways scrolling.
    await page.setViewportSize({ width: 390, height: 844 })
    await page.getByRole("link", { name: "All incidents" }).or(page.getByRole("button", { name: "All incidents" })).first().click()
    await page.getByRole("button", { name: "Response targets" }).click()
    await expect(page.getByRole("region", { name: "Response targets" })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true)
  } finally {
    // Other specs expect "No SLA set": always leave the organization without targets.
    await page.evaluate(async (org) => {
      const headers = { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" }
      await fetch(`/api/organizations/${org}/incident-sla`, { method: "PUT", headers, body: JSON.stringify({ targets: {} }) })
    }, orgId)
  }
})
