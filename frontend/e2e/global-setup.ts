import { chromium, expect, type FullConfig } from "@playwright/test"
import { writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

// Signs the bootstrap administrator in once for the whole run. Admin sign-in is rate limited by
// abuse protection (ADMIN_AUTH: 20 requests per 5 minutes per client, and each sign-in costs two:
// the login page's SSO lookup and the login itself), so specs that only need an administrator
// reuse this session instead of signing in again.
export const SESSION_FILE = join(tmpdir(), "greyguard-e2e-admin-session.json")

export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL!
  const browser = await chromium.launch()
  const page = await browser.newPage({ baseURL })
  await page.goto("/")
  await page.locator("#admin-email").fill(process.env.GREYGUARD_E2E_EMAIL!)
  await page.locator("#admin-password").fill(process.env.GREYGUARD_E2E_PASSWORD!)
  const [login] = await Promise.all([
    // The first login on a fresh database also runs one-time initialization.
    page.waitForResponse((response) => response.url().endsWith("/auth/login") && response.request().method() === "POST", { timeout: 90_000 }),
    page.getByRole("button", { name: /Enter command center/i }).click(),
  ])
  expect(login.status(), `login failed: ${await login.text()}`).toBe(200)
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(/Every action passes/i, { timeout: 30_000 })
  const session = await page.evaluate(() => Object.fromEntries(Object.entries(sessionStorage)))
  writeFileSync(SESSION_FILE, JSON.stringify(session))
  await browser.close()
}
