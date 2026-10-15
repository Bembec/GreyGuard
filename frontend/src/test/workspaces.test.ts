import { describe, expect, it } from "vitest"

import { navigationItems, navigationPermission } from "../config/navigation"
import { navigationGroups } from "../config/navigationGroups"
import {
  commandCenter,
  matchPages,
  pagePathFor,
  visibleTabs,
  workspaceForPath,
  workspaces,
} from "../config/workspaces"
import type { Administrator } from "../context/AuthContext"
import { matchesPermission } from "../hooks/usePermission"

// Every console page that existed before the P1.4 information architecture redesign. The
// redesign may regroup these pages, but each one must still exist at the same URL.
const PRE_REDESIGN_PATHS = [
  "/dashboard", "/getting-started", "/live", "/agents", "/requests", "/approvals", "/policies",
  "/risk", "/incidents", "/notifications", "/audit", "/compliance", "/authentication",
  "/account-security", "/sandbox", "/team", "/secrets", "/service-accounts", "/adapters",
  "/observability", "/security-exports", "/audit-integrity", "/communication-integrations",
  "/incident-integrations", "/execution-isolation", "/isolation-operations", "/endpoint-telemetry",
  "/defensive-integrations", "/simulations", "/universal-controls", "/capability-removals",
  "/threat-register", "/enterprise-identity", "/abuse-protection", "/settings",
]

const routesSource = Object.values(
  import.meta.glob("../routes/AppRoutes.tsx", { query: "?raw", import: "default", eager: true }),
)[0] as string
const declaredRoutes = new Set([...routesSource.matchAll(/path="([^"]+)"/g)].map((match) => match[1]))

const base: Administrator = {
  admin_id: "a", email: "a@example.com", display_name: "A", role: "PLATFORM_ADMIN", permissions: [],
}
const operator: Administrator = { ...base, install_operator: true }
const orgAdmin: Administrator = { ...base, install_operator: false }
const auditor: Administrator = { ...base, role: "AUDITOR", install_operator: false }

describe("route inventory", () => {
  it("keeps every pre-redesign page at its original URL", () => {
    const paths = new Set(navigationItems.map((item) => item.path))
    for (const path of PRE_REDESIGN_PATHS) {
      expect(paths.has(path), `${path} is missing from navigation`).toBe(true)
      expect(declaredRoutes.has(path), `${path} has no route`).toBe(true)
    }
  })

  it("keeps the investigation detail routes", () => {
    expect(declaredRoutes.has("/agents/:agentName")).toBe(true)
    expect(declaredRoutes.has("/requests/:requestId")).toBe(true)
  })

  it("places every page except the Command Center in exactly one workspace", () => {
    for (const item of navigationItems) {
      const owners = workspaces.filter((workspace) => workspace.tabs.includes(item.path))
      expect(owners.length, item.path).toBe(item === commandCenter ? 0 : 1)
    }
  })

  it("only lists real pages as tabs, each in its own domain", () => {
    for (const workspace of workspaces) {
      for (const path of workspace.tabs) {
        const item = navigationItems.find((entry) => entry.path === path)
        expect(item, `${workspace.id} lists unknown page ${path}`).toBeDefined()
        expect(item!.group, `${path} is filed under a different domain`).toBe(workspace.domain)
      }
    }
  })
})

describe("information architecture", () => {
  it("never shows a domain as a long flat list", () => {
    for (const group of navigationGroups) {
      const count = workspaces.filter((workspace) => workspace.domain === group.id).length
      expect(count, group.id).toBeGreaterThan(0)
      expect(count, group.id).toBeLessThanOrEqual(4)
    }
    for (const workspace of workspaces) expect(workspace.tabs.length, workspace.id).toBeLessThanOrEqual(4)
  })

  it("cuts the sidebar from one entry per page to one entry per workspace", () => {
    expect(workspaces.length + 1).toBeLessThan(navigationItems.length / 2)
  })

  it("has unique workspace ids and labels", () => {
    expect(new Set(workspaces.map((workspace) => workspace.id)).size).toBe(workspaces.length)
    expect(new Set(workspaces.map((workspace) => workspace.label)).size).toBe(workspaces.length)
  })

  it("resolves detail pages to their list page and workspace", () => {
    expect(pagePathFor("/agents/build-bot")).toBe("/agents")
    expect(pagePathFor("/requests/req-1")).toBe("/requests")
    expect(workspaceForPath("/agents/build-bot")?.id).toBe("agents")
    expect(workspaceForPath("/requests/req-1")?.id).toBe("requests")
    expect(workspaceForPath("/dashboard")).toBeUndefined()
  })
})

describe("role-based visibility", () => {
  it("applies each page's existing permission check to its tab", () => {
    for (const administrator of [operator, orgAdmin, auditor, null]) {
      for (const workspace of workspaces) {
        const shown = visibleTabs(workspace, administrator).map((item) => item.path)
        const expected = workspace.tabs.filter((path) =>
          matchesPermission(administrator, navigationPermission(navigationItems.find((item) => item.path === path)!)))
        expect(shown).toEqual(expected)
      }
    }
  })

  it("hides install-operator tabs from an org's platform administrator", () => {
    const shown = workspaces.flatMap((workspace) => visibleTabs(workspace, orgAdmin)).map((item) => item.path)
    for (const path of ["/team", "/observability", "/enterprise-identity", "/abuse-protection", "/audit-integrity"]) {
      expect(shown).not.toContain(path)
    }
    expect(shown).toContain("/security-exports")
  })

  it("hides platform-administrator tabs, and empty workspaces, from an auditor", () => {
    const shown = workspaces.flatMap((workspace) => visibleTabs(workspace, auditor)).map((item) => item.path)
    expect(shown).not.toContain("/service-accounts")
    expect(shown).not.toContain("/secrets")
    expect(shown).toContain("/agents")
    expect(shown).toContain("/audit")
    const containment = workspaces.find((workspace) => workspace.id === "containment")!
    expect(visibleTabs(containment, auditor)).toEqual([])
  })

  it("only offers pages the administrator may open in search", () => {
    expect(matchPages("service", operator).map((match) => match.item.path)).toContain("/service-accounts")
    expect(matchPages("service", auditor).map((match) => match.item.path)).not.toContain("/service-accounts")
    expect(matchPages("team", orgAdmin).map((match) => match.item.path)).not.toContain("/team")
    expect(matchPages("", operator)).toEqual([])
  })

  it("ranks a page-name match above a description match", () => {
    expect(matchPages("approvals", operator)[0].item.path).toBe("/approvals")
  })
})
