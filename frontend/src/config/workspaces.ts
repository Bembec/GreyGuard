import {
  Bot,
  ClipboardCheck,
  FileLock2,
  FileOutput,
  Gauge,
  Radar,
  RadioTower,
  Rocket,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Container,
  UsersRound,
  type LucideIcon,
} from "lucide-react"

import type { Administrator } from "../context/AuthContext"
import { matchesPermission } from "../hooks/usePermission"
import { navigationItems, navigationPermission, type NavigationGroupId, type NavigationItem } from "./navigation"

/**
 * A workspace gathers the pages that serve one job into a single sidebar entry. Its pages become
 * tabs on that workspace. Every page keeps its own URL, so deep links, bookmarks and the e2e
 * suite still reach it directly, and each tab is permission-filtered exactly like the sidebar
 * entry it replaced.
 */
export interface Workspace {
  id: string
  label: string
  description: string
  domain: NavigationGroupId
  icon: LucideIcon
  /** Page paths, in tab order. Each must be a navigationItems path. */
  tabs: string[]
}

export const workspaces: Workspace[] = [
  {
    id: "agents",
    label: "Agents & Identity",
    description: "Agent identities, machine accounts, federation and adapters",
    domain: "gate",
    icon: Bot,
    tabs: ["/agents", "/service-accounts", "/enterprise-identity", "/adapters"],
  },
  {
    id: "requests",
    label: "Requests & Approvals",
    description: "Human authorization, tool requests and the sandbox",
    domain: "gate",
    icon: ClipboardCheck,
    tabs: ["/approvals", "/requests", "/sandbox"],
  },
  {
    id: "controls",
    label: "Policies & Controls",
    description: "Policies, capability tiers, removal and secret references",
    domain: "gate",
    icon: SlidersHorizontal,
    tabs: ["/policies", "/universal-controls", "/capability-removals", "/secrets"],
  },
  {
    id: "monitoring",
    label: "Live Monitoring",
    description: "Live events, prioritized signals and authentication activity",
    domain: "watch",
    icon: RadioTower,
    tabs: ["/live", "/notifications", "/authentication"],
  },
  {
    id: "risk",
    label: "Risk & Threats",
    description: "Agent risk, the threat register and control validation",
    domain: "watch",
    icon: Radar,
    tabs: ["/risk", "/threat-register", "/simulations"],
  },
  {
    id: "telemetry",
    label: "Telemetry & Sensors",
    description: "Endpoint telemetry, defensive connectors and observability",
    domain: "watch",
    icon: Gauge,
    tabs: ["/endpoint-telemetry", "/defensive-integrations", "/observability"],
  },
  {
    id: "incidents",
    label: "Incident Response",
    description: "Incident ownership, ticketing and notifications",
    domain: "respond",
    icon: ShieldAlert,
    tabs: ["/incidents", "/incident-integrations", "/communication-integrations"],
  },
  {
    id: "containment",
    label: "Containment",
    description: "Hardened execution, workspaces and quarantine",
    domain: "respond",
    icon: Container,
    tabs: ["/execution-isolation", "/isolation-operations"],
  },
  {
    id: "audit",
    label: "Audit & Integrity",
    description: "Decision evidence, verification, retention and legal holds",
    domain: "evidence",
    icon: FileLock2,
    tabs: ["/audit", "/audit-integrity"],
  },
  {
    id: "reports",
    label: "Reports & Exports",
    description: "Compliance snapshots and signed SIEM delivery",
    domain: "evidence",
    icon: FileOutput,
    tabs: ["/compliance", "/security-exports"],
  },
  {
    id: "organization",
    label: "Organization",
    description: "Onboarding, plan, lifecycle and interface settings",
    domain: "administration",
    icon: Rocket,
    tabs: ["/getting-started", "/settings"],
  },
  {
    id: "access",
    label: "Access & Accounts",
    description: "Operators, your account security and abuse protection",
    domain: "administration",
    icon: UsersRound,
    tabs: ["/team", "/account-security", "/abuse-protection"],
  },
]

/** The pinned Command Center, which belongs to no workspace. */
export const commandCenter = navigationItems.find((item) => !item.group)!
export const commandCenterIcon = ShieldCheck

const itemsByPath = new Map(navigationItems.map((item) => [item.path, item]))

export function workspaceTabs(workspace: Workspace): NavigationItem[] {
  return workspace.tabs.map((path) => itemsByPath.get(path)!)
}

/** The tabs this administrator may open; the same check the sidebar has always used. */
export function visibleTabs(workspace: Workspace, administrator: Administrator | null): NavigationItem[] {
  return workspaceTabs(workspace).filter((item) => matchesPermission(administrator, navigationPermission(item)))
}

/** The page path a URL belongs to: detail routes resolve to their list page. */
export function pagePathFor(pathname: string): string {
  if (pathname.startsWith("/agents/")) return "/agents"
  if (pathname.startsWith("/requests/")) return "/requests"
  return pathname
}

export function workspaceForPath(pathname: string): Workspace | undefined {
  const page = pagePathFor(pathname)
  return workspaces.find((workspace) => workspace.tabs.includes(page))
}

export function pageForPath(pathname: string): NavigationItem | undefined {
  return itemsByPath.get(pagePathFor(pathname))
}

export interface PageMatch {
  item: NavigationItem
  workspace?: Workspace
}

/**
 * Pages whose name, description or workspace matches the query, for jumping straight to a page
 * from search. Only pages this administrator may open are returned.
 */
export function matchPages(query: string, administrator: Administrator | null, limit = 5): PageMatch[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return []
  return navigationItems
    .filter((item) => matchesPermission(administrator, navigationPermission(item)))
    .map((item) => ({ item, workspace: workspaceForPath(item.path) }))
    .map((match) => {
      const label = match.item.label.toLowerCase()
      const rank = label.startsWith(needle) ? 0
        : label.includes(needle) ? 1
        : match.workspace?.label.toLowerCase().includes(needle) ? 2
        : match.item.description.toLowerCase().includes(needle) ? 3
        : -1
      return { match, rank }
    })
    .filter(({ rank }) => rank >= 0)
    .sort((a, b) => a.rank - b.rank)
    .slice(0, limit)
    .map(({ match }) => match)
}
