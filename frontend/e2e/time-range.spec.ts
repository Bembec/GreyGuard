import { expect, test } from "@playwright/test"

import { adminSession, openWithSession } from "./session"

// P7.5 batch 4d: the evidence lists take a server-side time range, kept in the URL with the other
// filters, so Back works and a link reopens the same view. One page load per test, to stay well
// inside the API's per-client rate limit.

let session: Record<string, string> = {}
test.beforeAll(() => { session = adminSession() })

test("Tool Requests keeps its range and filters in the URL, and Back restores them", async ({ page }) => {
  const sent: string[] = []
  page.on("request", (request) => { if (request.url().includes("/api/tool-requests?")) sent.push(request.url()) })
  await openWithSession(page, session, "/requests")

  const notice = page.getByTestId("range-notice")
  await expect(notice).toContainText("in the last 24 hours", { timeout: 15_000 })
  await expect(notice).toContainText("Pending requests are always shown")
  expect(sent.some((url) => url.includes("since="))).toBe(true)

  await page.getByTestId("time-range").selectOption("7d")
  await expect(page).toHaveURL(/range=7d/)
  await expect(notice).toContainText("in the last 7 days", { timeout: 15_000 })

  await page.getByRole("combobox").filter({ hasText: "All decisions" }).selectOption("BLOCK")
  await expect(page).toHaveURL(/decision=BLOCK/)

  await page.goBack()
  await expect(page).not.toHaveURL(/decision=BLOCK/)
  await expect(page).toHaveURL(/range=7d/)
  await page.goBack()
  await expect(page).not.toHaveURL(/range=/)
  await expect(notice).toContainText("in the last 24 hours")
})

test("a bad link still opens the page on its defaults, and a custom range is checked before it is sent", async ({ page }) => {
  await openWithSession(page, session, "/audit?range=99y&type=EVIL&since=garbage")
  const notice = page.getByTestId("range-notice")
  await expect(notice).toContainText("in the last 7 days", { timeout: 15_000 })
  await expect(page.getByLabel("Filter event type")).toHaveValue("ALL")

  await page.getByTestId("time-range").selectOption("custom")
  const from = page.getByLabel("From", { exact: true })
  const to = page.getByLabel("To", { exact: true })
  await from.fill("2026-01-02T10:00")
  await to.fill("2026-01-01T10:00")
  await expect(page.getByRole("button", { name: "Apply" })).toBeDisabled()
  await expect(page.getByText("The end must be after the start.")).toBeVisible()
})
