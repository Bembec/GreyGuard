import { expect, test } from "@playwright/test"

import { adminSession } from "./session"

// A rate limit or outage while a page loads says nothing about the session, so the console waits
// and resumes instead of signing the operator out. Only a 401 or 403 ends the session.

let session: Record<string, string> = {}
test.beforeAll(() => { session = adminSession() })

test("a rate-limited session check keeps the session and resumes on its own", async ({ page }) => {
  let refused = 0
  await page.route("**/api/auth/me", async (route) => {
    if (refused < 2) {
      refused += 1
      await route.fulfill({ status: 429, contentType: "application/json", body: JSON.stringify({ detail: "Too many requests." }) })
    } else {
      await route.continue()
    }
  })
  const refreshes: string[] = []
  page.on("request", (request) => { if (request.url().includes("/api/auth/refresh")) refreshes.push(request.url()) })

  // The real backend may also be rate limiting by this point in the suite, so allow for its
  // 60-second block on top of the two stubbed refusals.
  test.setTimeout(120_000)
  await page.addInitScript((values) => { for (const [key, value] of Object.entries(values)) sessionStorage.setItem(key, value) }, session)
  await page.goto("/getting-started")
  await expect(page.getByText(/Waiting for the control plane to respond/)).toBeVisible()
  await expect(page.locator(".topbar__title")).toHaveText("Getting Started", { timeout: 100_000 })
  expect(refused).toBe(2)
  // A transient failure is not a reason to spend the refresh token.
  expect(refreshes).toEqual([])
})

test("a rejected session still ends at the sign-in page", async ({ page }) => {
  await page.route("**/api/auth/me", (route) => route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Session expired." }) }))
  await page.route("**/api/auth/refresh", (route) => route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Refresh token expired." }) }))
  await page.addInitScript((values) => { for (const [key, value] of Object.entries(values)) sessionStorage.setItem(key, value) }, session)
  await page.goto("/getting-started")
  await expect(page.getByRole("heading", { name: "Operator sign in" })).toBeVisible({ timeout: 15_000 })
})
