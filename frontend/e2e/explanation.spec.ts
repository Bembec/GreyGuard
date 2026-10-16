import { expect, test } from "./fixtures"

import { adminSession, openWithSession } from "./session"

// P7.5 item 6: a request's page explains exactly why GreyGuard decided as it did, says how the
// agent authenticated, and never shows a value that looks like a secret.

let session: Record<string, string> = {}
test.beforeAll(() => { session = adminSession() })

test("a request explains its decision exactly and redacts secret-looking values", async ({ page }) => {
  await openWithSession(page, session, "/agents")
  const secret = "sk-e2eabcdefghijklmnopqrstuv"
  const requestId = await page.evaluate(async ([agentName, secretValue]) => {
    const headers = { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" }
    const me = await (await fetch("/api/auth/me", { headers })).json()
    await fetch(`/api/entitlements/${me.active_org_id}`, { method: "PUT", headers, body: JSON.stringify({ plan: "FOUNDATION", status: "ACTIVE" }) })
    const registered = await (await fetch("/api/agents", { method: "POST", headers, body: JSON.stringify({ agent_name: agentName, scopes: ["write_note"] }) })).json()
    const response = await fetch("/api/tool-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Agent-Name": agentName, "X-Agent-Key": registered.credential },
      body: JSON.stringify({ action: "write_note", target: "notes/todo.txt", payload: { content: `remember ${secretValue}` } }),
    })
    return (await response.json()).request_id as string
  }, [`explain_agent_${Date.now()}`, secret])

  await page.goto(`/requests/${requestId}`)
  const card = page.getByRole("region", { name: "Why GreyGuard decided this" })
  await expect(card).toBeVisible({ timeout: 15_000 })
  await expect(card).toContainText("Exact decision record")
  await expect(page.getByTestId("explanation-reason")).toHaveText("Held for human approval because policy v1 requires a reviewer for write_note.")
  await expect(card).toContainText("The agent authenticated with its agent key.")
  await expect(card).toContainText("permission:write_note")
  await expect(page.getByTestId("redaction-count")).toContainText("1 redacted")
  await expect(page.locator("body")).not.toContainText(secret)
  await expect(page.locator("body")).toContainText("[REDACTED: looks like a secret]")
})
