import { FileCheck2, KeyRound, LifeBuoy, Settings2, Siren, type LucideIcon } from "lucide-react"

import type { NavigationGroupId } from "./navigation"

export interface NavigationGroup {
  id: NavigationGroupId
  label: string
  description: string
  icon: LucideIcon
}

/**
 * Internal information-architecture labels only - not a rename of any route, module or page
 * title. Mirrors the four buyer-facing product groups the commercial roadmap already uses
 * to describe GreyGuard (Gate/Watch/Respond/Evidence), plus Administration for platform and
 * account housekeeping that isn't part of that security narrative.
 */
export const navigationGroups: NavigationGroup[] = [
  {
    id: "gate",
    label: "Gate",
    description: "Identity, scopes, tool gateway and policy enforcement",
    icon: KeyRound,
  },
  {
    id: "watch",
    label: "Watch",
    description: "Live monitoring, risk, alerts and investigation",
    icon: LifeBuoy,
  },
  {
    id: "respond",
    label: "Respond",
    description: "Suspension, incidents, isolation and recoverable containment",
    icon: Siren,
  },
  {
    id: "evidence",
    label: "Evidence",
    description: "Tamper-evident audit history, reports and exports",
    icon: FileCheck2,
  },
  {
    id: "administration",
    label: "Administration",
    description: "Operators, account security and interface settings",
    icon: Settings2,
  },
]
