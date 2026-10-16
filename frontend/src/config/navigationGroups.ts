import { Bot, FileCheck2, Plug, Settings2, Siren, SlidersHorizontal, type LucideIcon } from "lucide-react"

import type { NavigationGroupId } from "./navigation"

export interface NavigationGroup {
  id: NavigationGroupId
  label: string
  description: string
  icon: LucideIcon
}

/**
 * The console's task domains (roadmap v3, decision V1). With the pinned Command Center they make
 * the seven domains used everywhere in the console: the sidebar, the collapsed mega-menu, the
 * breadcrumb trail, page eyebrows and Ctrl+K. Operators work by task, so these differ on purpose
 * from the buyer-facing Gate, Watch, Respond and Evidence names the website uses.
 */
export const navigationGroups: NavigationGroup[] = [
  {
    id: "agents",
    label: "Agents & Access",
    description: "Agent identities, machine accounts, federation and operator access",
    icon: Bot,
  },
  {
    id: "policies",
    label: "Policies & Approvals",
    description: "Policies, capability controls, human approval and tool requests",
    icon: SlidersHorizontal,
  },
  {
    id: "operations",
    label: "Operations & Incidents",
    description: "Live monitoring, risk, incidents and containment",
    icon: Siren,
  },
  {
    id: "evidence",
    label: "Evidence & Reports",
    description: "Tamper-evident audit history, integrity, reports and exports",
    icon: FileCheck2,
  },
  {
    id: "integrations",
    label: "Integrations",
    description: "Agent adapters, secret references, alerting, ticketing and sensors",
    icon: Plug,
  },
  {
    id: "organization",
    label: "Organization & Administration",
    description: "Onboarding, plan and lifecycle settings, and platform health",
    icon: Settings2,
  },
]

