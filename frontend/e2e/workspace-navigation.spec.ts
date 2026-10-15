import { expect, test } from "@playwright/test"

import { adminSession, openWithSession } from "./session"

// The P1.4 information architecture: the sidebar lists product domains and their workspaces,
// and a workspace's pages are tabs that keep their own URLs.

let session: Record<string, string> = {}
test.beforeAll(() => { session = adminSession() })


test("the sidebar groups workspaces into expandable product domains", async ({ page }) => {
  await openWithSession(page, session, "/getting-started")
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
  await openWithSession(page, session, "/getting-started")
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
  await openWithSession(page, session, "/getting-started")
  await page.keyboard.press("Control+k")
  await page.getByRole("textbox", { name: /Search control plane/ }).fill("threat")
  await page.getByRole("listbox", { name: "Pages" }).getByRole("option", { name: /Threat Register/ }).click()
  await expect(page).toHaveURL(/\/threat-register$/)
})

test("the collapsed sidebar opens a mega-menu with every workspace and page in a domain", async ({ page }) => {
  await openWithSession(page, session, "/getting-started")
  await page.getByRole("button", { name: "Collapse sidebar" }).click()
  await page.getByTitle("Respond").click()
  const menu = page.getByRole("menu", { name: "Respond navigation" })
  await expect(menu.getByRole("group", { name: "Incident Response" })).toBeVisible()
  await expect(menu.getByRole("group", { name: "Containment" })).toBeVisible()
  // The panel must actually be painted, not clipped by the sidebar: the item is the topmost
  // element at its own centre point.
  const item = menu.getByRole("menuitem", { name: /Isolation Operations/ })
  const box = (await item.boundingBox())!
  const hit = await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.closest("[role=menuitem]")?.textContent ?? "", { x: box.x + box.width / 2, y: box.y + box.height / 2 })
  expect(hit).toContain("Isolation Operations")
  await item.click()
  await expect(page).toHaveURL(/\/isolation-operations$/)
})

test("the tab bar stays above a page's own background layers", async ({ page }) => {
  // Live Operations paints a fixed, full-viewport atmosphere inside its own stacking context; it
  // once covered the tab bar. A hit test cannot see that layer (it ignores pointer events), so this
  // checks the stacking rule that keeps the shell's bands on top.
  await openWithSession(page, session, "/live")
  const tabs = page.getByRole("navigation", { name: "Live Monitoring sections" })
  await expect(tabs).toBeVisible()
  expect(await tabs.evaluate((element) => { const style = getComputedStyle(element); return [style.position, Number(style.zIndex) >= 1] })).toEqual(["relative", true])
})

test("sections and tabs work from the keyboard alone", async ({ page }) => {
  await openWithSession(page, session, "/approvals")
  const sidebar = page.getByRole("navigation", { name: "Primary navigation" })
  const evidence = sidebar.getByRole("button", { name: "Evidence" })
  await evidence.focus()
  await page.keyboard.press("Enter")
  await expect(evidence).toHaveAttribute("aria-expanded", "false")
  await page.keyboard.press("Enter")
  await expect(evidence).toHaveAttribute("aria-expanded", "true")
  // Tabs are ordinary links: focus one and follow it with Enter.
  const tabs = page.getByRole("navigation", { name: "Requests & Approvals sections" })
  await tabs.getByRole("link", { name: "Tool Requests" }).focus()
  await page.keyboard.press("Enter")
  await expect(page).toHaveURL(/\/requests$/)
  await expect(tabs.getByRole("link", { name: "Tool Requests" })).toHaveAttribute("aria-current", "page")
})

test("a platform administrator gets each threat's Review action (the control for the AUDITOR check)", async ({ page }) => {
  await openWithSession(page, session, "/threat-register")
  await expect(page.getByRole("table", { name: "Threats" })).toBeVisible({ timeout: 15_000 })
  expect(await page.getByRole("button", { name: /^Review (?!by$)/ }).count()).toBeGreaterThan(0)
})

test("the console is dark-only until the light theme is production quality", async ({ page }) => {
  await openWithSession(page, session, "/dashboard")
  await expect(page.getByRole("button", { name: "Change appearance" })).toHaveCount(0)
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark")
})
