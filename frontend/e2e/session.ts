import { expect, type Browser, type Page } from "@playwright/test"

// Admin sign-in is rate limited (abuse protection's ADMIN_AUTH category), so a spec signs in once
// and reuses that session in every test rather than signing in per test.

export async function signInOnce(browser: Browser): Promise<Record<string, string>> {
  const page = await browser.newPage()
  await page.goto("/")
  await page.locator("#admin-email").fill(process.env.GREYGUARD_E2E_EMAIL!)
  await page.locator("#admin-password").fill(process.env.GREYGUARD_E2E_PASSWORD!)
  const [login] = await Promise.all([
    page.waitForResponse((response) => response.url().endsWith("/auth/login") && response.request().method() === "POST", { timeout: 90_000 }),
    page.getByRole("button", { name: /Enter command center/i }).click(),
  ])
  expect(login.status(), `login failed: ${await login.text()}`).toBe(200)
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(/Every action passes/i, { timeout: 30_000 })
  const session = await page.evaluate(() => Object.fromEntries(Object.entries(sessionStorage)))
  await page.close()
  return session
}

export async function openWithSession(page: Page, session: Record<string, string>, path: string) {
  await page.addInitScript((values) => { for (const [key, value] of Object.entries(values)) sessionStorage.setItem(key, value) }, session)
  await page.goto(path)
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(/^\s*$|Every action passes/i, { timeout: 30_000 })
}
