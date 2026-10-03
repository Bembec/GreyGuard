export interface NavigationItem {
  label: string
  path: string
  description: string
  requiredRole?: string
}

export const navigationItems: NavigationItem[] = [
  {
    label: "Command Center",
    path: "/dashboard",
    description: "Security overview and live posture",
  },
  {
    label: "Live Operations",
    path: "/live",
    description: "Real-time security event monitoring",
  },
  {
    label: "Agents",
    path: "/agents",
    description: "Identity, scopes and agent states",
  },
  {
    label: "Tool Requests",
    path: "/requests",
    description: "Controlled execution requests",
  },
  {
    label: "Approvals",
    path: "/approvals",
    description: "Human authorization queue",
  },
  {
    label: "Policies",
    path: "/policies",
    description: "Action permissions and boundaries",
  },
  {
    label: "Risk Center",
    path: "/risk",
    description: "Risk scores and suspensions",
  },
  {
    label: "Incident Center",
    path: "/incidents",
    description: "Alert ownership and response workflow",
  },
  {
    label: "Notifications",
    path: "/notifications",
    description: "Prioritized security signal inbox",
  },
  {
    label: "Audit Trail",
    path: "/audit",
    description: "Security decision evidence",
  },
  {
    label: "Compliance Reports",
    path: "/compliance",
    description: "Evidence snapshots and exports",
  },
  {
    label: "Authentication",
    path: "/authentication",
    description: "Credential and scope events",
  },
  {
    label: "Sandbox",
    path: "/sandbox",
    description: "Contained tool environment",
  },
  {
    label: "Team & Access",
    path: "/team",
    description: "Administrator identities and roles",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Secret Management",
    path: "/secrets",
    description: "References, rotation and emergency revocation",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Service Accounts",
    path: "/service-accounts",
    description: "Scoped machine identities and API keys",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Agent Adapters",
    path: "/adapters",
    description: "Framework manifests, tests and emergency kill switches",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Observability",
    path: "/observability",
    description: "Tracing, metrics, correlation and export controls",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Abuse Protection",
    path: "/abuse-protection",
    description: "Rate limits, lockouts and burst controls",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Settings",
    path: "/settings",
    description: "Interface and control settings",
  },
]
