import { expect, test } from "@playwright/test"

import { openWithSession, signInOnce } from "./session"

// The P1.4 information architecture: the sidebar lists product domains and their workspaces,
// and a workspace's pages are tabs that keep their own URLs.

let session: Record<string, string> = {}

test.beforeAll(async ({ browser }) => {
  test.setTimeout(120_000)
  session = await signInOnce(browser)
})

test.beforeEach(async ({ page }) => {
  await openWithSession(page, session, "/dashboard")
})

test("the sidebar groups workspaces into expandable product domains", async ({ page }) => {
  const sidebar = page.getByRole("navigation", { name: "Primary navigation" })
  for (const domain of ["Gate", "Watch", "Respond", "Evidence", "Administration"]) {
    await expect(sidebar.getByRole("button", { name: domain })).toHaveAttribute("aria-expanded", "true")
  }
  // One entry per workspace, not one per page.
  await expect(sidebar.getByRole("link")).toHaveCount(13)
  await sidebar.getByRole("button", { name: "Evidence" }).click()
  await expect(sidebar.getByRole("button", { name: "Evidence" })).toHaveAttribute("aria-expanded", "false")
  await expect(sidebar.getByRole("link", { name: /Audit & Integrity/ })).toHaveCount(0)
  // The choice is remembered on this device.
  await page.reload()
  await expect(page.getByRole("navigation", { name: "Primary navigation" }).getByRole("button", { name: "Evidence" })).toHaveAttribute("aria-expanded", "false")
  await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("button", { name: "Evidence" }).click()
})

test("workspace tabs move between pages and keep each page's URL", async ({ page }) => {
  await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: /Requests & Approvals/ }).click()
  await expect(page).toHaveURL(/\/approvals$/)
  const tabs = page.getByRole("navigation", { name: "Requests & Approvals sections" })
  await expect(tabs.getByRole("link", { name: "Approvals" })).toHaveAttribute("aria-current", "page")
  await tabs.getByRole("link", { name: "Tool Requests" }).click()
  await expect(page).toHaveURL(/\/requests$/)
  await expect(tabs.getByRole("link", { name: "Tool Requests" })).toHaveAttribute("aria-current", "page")
  await expect(page.locator(".topbar__trail")).toContainText("Gate")
  await expect(page.locator(".topbar__trail")).toContainText("Requests & Approvals")
  // A direct visit opens the same workspace with the right tab selected.
  await page.goto("/sandbox")
  await expect(page.getByRole("navigation", { name: "Requests & Approvals sections" }).getByRole("link", { name: "Sandbox" })).toHaveAttribute("aria-current", "page", { timeout: 15_000 })
})

test("search jumps to a page by name", async ({ page }) => {
  await page.keyboard.press("Control+k")
  await page.getByRole("textbox", { name: /Search control plane/ }).fill("threat")
  await page.getByRole("listbox", { name: "Pages" }).getByRole("option", { name: /Threat Register/ }).click()
  await expect(page).toHaveURL(/\/threat-register$/)
})

test("the collapsed sidebar opens a mega-menu with every workspace and page in a domain", async ({ page }) => {
  await page.getByRole("button", { name: "Collapse sidebar" }).click()
  await page.getByTitle("Respond").click()
  const menu = page.getByRole("menu", { name: "Respond navigation" })
  await expect(menu.getByRole("group", { name: "Incident Response" })).toBeVisible()
  await expect(menu.getByRole("group", { name: "Containment" })).toBeVisible()
  await menu.getByRole("menuitem", { name: /Isolation Operations/ }).click()
  await expect(page).toHaveURL(/\/isolation-operations$/)
})
