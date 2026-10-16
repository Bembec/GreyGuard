import { expect, test } from "./fixtures"

import { adminSession, openWithSession } from "./session"

// P7.5 Control Graph: an agent's relationships, read-only, opened from its own page. A request
// made now has an exact decision record, and the impact preview reads without changing anything.

let session: Record<string, string> = {}
test.beforeAll(() => { session = adminSession() })

test("the Relationships tab shows an exact decision and a read-only impact preview", async ({ page }) => {
  await openWithSession(page, session, "/agents")
  const name = `graph_agent_${Date.now()}`
  // Self-contained: a plan with capacity, an agent, and one request from it.
  const setup = await page.evaluate(async (agentName) => {
    const headers = { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" }
    const me = await (await fetch("/api/auth/me", { headers })).json()
    await fetch(`/api/entitlements/${me.active_org_id}`, { method: "PUT", headers, body: JSON.stringify({ plan: "FOUNDATION", status: "ACTIVE" }) })
    const registered = await (await fetch("/api/agents", { method: "POST", headers, body: JSON.stringify({ agent_name: agentName, scopes: ["read_file", "list_files"] }) })).json()
    const request = await fetch("/api/tool-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Name": agentName, "X-Agent-Key": registered.credential },
      body: JSON.stringify({ action: "list_files", target: ".", payload: {} }),
    })
    return { credential: Boolean(registered.credential), request: request.status }
  }, name)
  expect(setup).toEqual({ credential: true, request: 201 })

  await page.goto(`/agents/${name}?tab=relationships`)
  await expect(page.getByRole("tab", { name: "Relationships" })).toHaveAttribute("aria-selected", "true", { timeout: 15_000 })
  const summary = page.getByTestId("graph-summary")
  await expect(summary).toContainText("1 with an exact decision record", { timeout: 15_000 })
  await expect(summary).toContainText("older history is not retained")

  // The request is labelled exact, and its evidence names the rule and the policy version.
  const request = page.getByRole("button", { name: /Request: list_files/ })
  await expect(request).toContainText("Exact")
  await request.click()
  const evidence = page.getByRole("region", { name: "Decision evidence" })
  await expect(evidence).toContainText("Exact decision record")
  await expect(evidence).toContainText("permission:list_files")
  await expect(evidence).toContainText("The record matches the fingerprint")
  // The panel sits above the shell's top bar: its close button is reachable, and closes it.
  await page.getByRole("button", { name: "Close details" }).click()
  await expect(evidence).toHaveCount(0)

  // The impact preview reads only.
  const mutations: string[] = []
  page.on("request", (sent) => { if (sent.url().includes("/api/") && sent.method() !== "GET") mutations.push(`${sent.method()} ${sent.url()}`) })
  await page.getByRole("button", { name: /Scope: list_files/ }).click()
  const preview = page.getByRole("region", { name: "Impact preview" })
  await expect(preview.getByText("Read-only")).toBeVisible()
  await preview.getByRole("button", { name: "Preview impact" }).click()
  await expect(page.getByTestId("impact-preview")).toContainText("Tools that would become unreachable: list_files")
  await expect(page.getByTestId("impact-preview")).toContainText("Nothing changes here")
  expect(mutations.filter((entry) => !entry.includes("/analytics/"))).toEqual([])

  // Keyboard: the tabs move with the arrow keys.
  await page.getByRole("tab", { name: "Relationships" }).focus()
  await page.keyboard.press("ArrowLeft")
  await expect(page.getByRole("tab", { name: "Evidence" })).toHaveAttribute("aria-selected", "true")
  await expect(page).not.toHaveURL(/tab=relationships/)
})
