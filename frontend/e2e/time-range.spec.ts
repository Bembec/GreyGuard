import { expect, test } from "@playwright/test"

import { adminSession, openWithSession } from "./session"

// P7.5 batch 4d: the evidence lists take a server-side time range, kept in the URL with the other
// filters, so Back works and a link reopens the same view; a saved view brings filters back after
// a reload. One page load and one reload in all: the full suite runs close to the API's
// per-client rate limit. Validation details are unit-tested (timeRange/savedViews.test.tsx).

let session: Record<string, string> = {}
test.beforeAll(() => { session = adminSession() })

test("range and filters live in the URL, Back restores them, and a saved view survives a reload", async ({ page }) => {
  const sent: string[] = []
  page.on("request", (request) => { if (request.url().includes("/api/tool-requests?")) sent.push(request.url()) })
  // Junk values in a link fall back to the page's defaults.
  await openWithSession(page, session, "/requests?range=99y&decision=EVIL")

  const notice = page.getByTestId("range-notice")
  const decisions = page.getByRole("combobox").filter({ hasText: "All decisions" })
  await expect(notice).toContainText("in the last 24 hours", { timeout: 15_000 })
  await expect(notice).toContainText("Pending requests are always shown")
  await expect(decisions).toHaveValue("ALL")
  expect(sent.some((url) => url.includes("since="))).toBe(true)

  // Each choice is a history entry.
  await page.getByTestId("time-range").selectOption("7d")
  await expect(page).toHaveURL(/range=7d/)
  await expect(notice).toContainText("in the last 7 days", { timeout: 15_000 })
  await decisions.selectOption("BLOCK")
  await expect(page).toHaveURL(/decision=BLOCK/)
  await page.goBack()
  await expect(page).not.toHaveURL(/decision=BLOCK/)
  await expect(page).toHaveURL(/range=7d/)
  await page.goForward()
  await expect(page).toHaveURL(/decision=BLOCK/)

  // Save the view, change the filters, reload, and apply it.
  await page.getByRole("button", { name: /^Views/ }).click()
  await page.getByLabel("Save the current filters as").fill("Blocked, last 7 days")
  await page.getByRole("button", { name: "Save", exact: true }).click()
  await expect(page.getByText("Saved in this browser, for your account only.")).toBeVisible()
  await page.keyboard.press("Escape")
  await page.getByTestId("time-range").selectOption("24h")
  await decisions.selectOption("ALL")
  await expect(page).not.toHaveURL(/range=7d|decision=BLOCK/)

  await page.reload()
  await page.getByRole("button", { name: /^Views/ }).click()
  await page.getByRole("button", { name: "Blocked, last 7 days", exact: true }).click()
  await expect(page).toHaveURL(/decision=BLOCK/)
  await expect(page).toHaveURL(/range=7d/)
  await expect(notice).toContainText("in the last 7 days", { timeout: 15_000 })
})
