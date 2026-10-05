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
    label: "Account Security",
    path: "/account-security",
    description: "MFA, credential expiry and active devices",
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
    label: "Security Exports",
    path: "/security-exports",
    description: "Signed SIEM delivery, queues and destination health",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Audit Integrity",
    path: "/audit-integrity",
    description: "Cryptographic verification, retention and legal holds",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Communications",
    path: "/communication-integrations",
    description: "Incident notifications, quiet hours and delivery evidence",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Incident Integrations",
    path: "/incident-integrations",
    description: "Jira, ServiceNow, approval links and signed callbacks",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Execution Isolation",
    path: "/execution-isolation",
    description: "Hardened Docker sandbox and emergency termination",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Isolation Operations",
    path: "/isolation-operations",
    description: "Workspaces, quarantine, network boundaries and Kubernetes jobs",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Endpoint Telemetry",
    path: "/endpoint-telemetry",
    description: "Consent-bound read-only endpoint monitoring",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Defensive Integrations",
    path: "/defensive-integrations",
    description: "Permissioned connectors and reversible response plans",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Simulation Lab",
    path: "/simulations",
    description: "Non-operational adversarial control validation",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Universal Controls",
    path: "/universal-controls",
    description: "Tier 2 and Tier 3 capability enforcement",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Capability Removal",
    path: "/capability-removals",
    description: "Guided retirement, rollback and emergency shutdown",
    requiredRole: "PLATFORM_ADMIN",
  },
  {
    label: "Threat Register",
    path: "/threat-register",
    description: "Threat ownership, residual risk and review evidence",
  },
  {
    label: "Enterprise Identity",
    path: "/enterprise-identity",
    description: "Federation, workload trust and privileged access",
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
