import { expect, type Page } from "@playwright/test"
import { readFileSync } from "node:fs"

import { SESSION_FILE } from "./global-setup"

/** The bootstrap administrator's session, signed in once by global-setup.ts for the whole run. */
export function adminSession(): Record<string, string> {
  return JSON.parse(readFileSync(SESSION_FILE, "utf8")) as Record<string, string>
}

export async function openWithSession(page: Page, session: Record<string, string>, path: string) {
  await page.addInitScript((values) => { for (const [key, value] of Object.entries(values)) sessionStorage.setItem(key, value) }, session)
  await page.goto(path)
  await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(/^\s*$|Every action passes/i, { timeout: 30_000 })
}
