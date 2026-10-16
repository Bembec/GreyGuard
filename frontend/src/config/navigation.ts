import type { PermissionCheck } from "../hooks/usePermission"
import {
  AlertTriangle,
  Bell,
  Bot,
  Boxes,
  Building2,
  CheckSquare,
  ClipboardList,
  Command,
  Container,
  FileCheck2,
  FileLock2,
  FileSearch,
  Fingerprint,
  FlaskConical,
  KeyRound,
  KeySquare,
  Layers,
  LineChart,
  Lock,
  MessageSquare,
  Plug,
  Radar,
  Rocket,
  RadioTower,
  Satellite,
  Settings,
  ShieldAlert,
  ShieldEllipsis,
  ShieldPlus,
  SlidersHorizontal,
  ToggleLeft,
  Trash2,
  UploadCloud,
  UsersRound,
  Workflow,
  type LucideIcon,
} from "lucide-react"

export type NavigationGroupId = "agents" | "policies" | "operations" | "evidence" | "integrations" | "organization"

export interface NavigationItem {
  label: string
  path: string
  description: string
  requiredRole?: string
  /** Install-wide pages: visible only to install operators, whatever their role in the active org. */
  requiresInstallOperator?: boolean
  /**
   * The page opens read-only for roles that fail the check above: it is left out of their
   * navigation, but a direct link still shows it rather than the access-denied state.
   */
  readOnlyForOtherRoles?: boolean
  /** Undefined for the one pinned item (Command Center), which renders above all groups. */
  group?: NavigationGroupId
  icon: LucideIcon
}

export const navigationItems: NavigationItem[] = [
  {
    label: "Command Center",
    path: "/dashboard",
    description: "Security overview and live posture",
    icon: Command,
  },
  {
    label: "Getting Started",
    path: "/getting-started",
    description: "Onboarding steps and pilot progress",
    group: "organization",
    icon: Rocket,
  },
  {
    label: "Live Operations",
    path: "/live",
    description: "Real-time security event monitoring",
    group: "operations",
    icon: RadioTower,
  },
  {
    label: "Agents",
    path: "/agents",
    description: "Identity, scopes and agent states",
    group: "agents",
    icon: Bot,
  },
  {
    label: "Tool Requests",
    path: "/requests",
    description: "Controlled execution requests",
    group: "policies",
    icon: Boxes,
  },
  {
    label: "Approvals",
    path: "/approvals",
    description: "Human authorization queue",
    group: "policies",
    icon: CheckSquare,
  },
  {
    label: "Policies",
    path: "/policies",
    description: "Action permissions and boundaries",
    group: "policies",
    icon: SlidersHorizontal,
  },
  {
    label: "Risk Center",
    path: "/risk",
    description: "Risk scores and suspensions",
    group: "operations",
    icon: Radar,
  },
  {
    label: "Incident Center",
    path: "/incidents",
    description: "Alert ownership and response workflow",
    group: "operations",
    icon: ShieldAlert,
  },
  {
    label: "Notifications",
    path: "/notifications",
    description: "Prioritized security signal inbox",
    group: "operations",
    icon: Bell,
  },
  {
    label: "Audit Trail",
    path: "/audit",
    description: "Security decision evidence",
    group: "evidence",
    icon: FileSearch,
  },
  {
    label: "Compliance Reports",
    path: "/compliance",
    description: "Evidence snapshots and exports",
    group: "evidence",
    icon: FileCheck2,
  },
  {
    label: "Authentication",
    path: "/authentication",
    description: "Credential and scope events",
    group: "agents",
    icon: Fingerprint,
  },
  {
    label: "Account Security",
    path: "/account-security",
    description: "MFA, credential expiry and active devices",
    group: "agents",
    icon: Lock,
  },
  {
    label: "Sandbox",
    path: "/sandbox",
    description: "Contained tool environment",
    group: "policies",
    icon: ClipboardList,
  },
  {
    label: "Team & Access",
    path: "/team",
    description: "Administrator identities and roles",
    requiresInstallOperator: true,
    group: "agents",
    icon: UsersRound,
  },
  {
    label: "Secret Management",
    path: "/secrets",
    description: "References, rotation and emergency revocation",
    requiredRole: "PLATFORM_ADMIN",
    readOnlyForOtherRoles: true,
    group: "integrations",
    icon: KeySquare,
  },
  {
    label: "Service Accounts",
    path: "/service-accounts",
    description: "Scoped machine identities and API keys",
    requiredRole: "PLATFORM_ADMIN",
    readOnlyForOtherRoles: true,
    group: "agents",
    icon: KeyRound,
  },
  {
    label: "Agent Adapters",
    path: "/adapters",
    description: "Framework manifests, tests and emergency kill switches",
    requiredRole: "PLATFORM_ADMIN",
    group: "integrations",
    icon: Plug,
  },
  {
    label: "Observability",
    path: "/observability",
    description: "Tracing, metrics, correlation and export controls",
    requiresInstallOperator: true,
    group: "organization",
    icon: LineChart,
  },
  {
    label: "Security Exports",
    path: "/security-exports",
    description: "Signed SIEM delivery, queues and destination health",
    requiredRole: "PLATFORM_ADMIN",
    group: "evidence",
    icon: UploadCloud,
  },
  {
    label: "Audit Integrity",
    path: "/audit-integrity",
    description: "Cryptographic verification, retention and legal holds",
    requiresInstallOperator: true,
    group: "evidence",
    icon: FileLock2,
  },
  {
    label: "Communications",
    path: "/communication-integrations",
    description: "Incident notifications, quiet hours and delivery evidence",
    requiredRole: "PLATFORM_ADMIN",
    group: "integrations",
    icon: MessageSquare,
  },
  {
    label: "Incident Integrations",
    path: "/incident-integrations",
    description: "Jira, ServiceNow, approval links and signed callbacks",
    requiredRole: "PLATFORM_ADMIN",
    group: "integrations",
    icon: Workflow,
  },
  {
    label: "Execution Isolation",
    path: "/execution-isolation",
    description: "Hardened Docker sandbox and emergency termination",
    requiredRole: "PLATFORM_ADMIN",
    group: "operations",
    icon: Container,
  },
  {
    label: "Isolation Operations",
    path: "/isolation-operations",
    description: "Workspaces, quarantine, network boundaries and Kubernetes jobs",
    requiredRole: "PLATFORM_ADMIN",
    group: "operations",
    icon: Layers,
  },
  {
    label: "Endpoint Telemetry",
    path: "/endpoint-telemetry",
    description: "Consent-bound read-only endpoint monitoring",
    requiredRole: "PLATFORM_ADMIN",
    group: "integrations",
    icon: Satellite,
  },
  {
    label: "Defensive Integrations",
    path: "/defensive-integrations",
    description: "Permissioned connectors and reversible response plans",
    requiredRole: "PLATFORM_ADMIN",
    group: "integrations",
    icon: ShieldPlus,
  },
  {
    label: "Simulation Lab",
    path: "/simulations",
    description: "Non-operational adversarial control validation",
    requiredRole: "PLATFORM_ADMIN",
    group: "operations",
    icon: FlaskConical,
  },
  {
    label: "Universal Controls",
    path: "/universal-controls",
    description: "Tier 2 and Tier 3 capability enforcement",
    requiredRole: "PLATFORM_ADMIN",
    group: "policies",
    icon: ToggleLeft,
  },
  {
    label: "Capability Removal",
    path: "/capability-removals",
    description: "Guided retirement, rollback and emergency shutdown",
    requiredRole: "PLATFORM_ADMIN",
    group: "policies",
    icon: Trash2,
  },
  {
    label: "Threat Register",
    path: "/threat-register",
    description: "Threat ownership, residual risk and review evidence",
    group: "operations",
    icon: AlertTriangle,
  },
  {
    label: "Enterprise Identity",
    path: "/enterprise-identity",
    description: "Federation, workload trust and privileged access",
    requiresInstallOperator: true,
    group: "agents",
    icon: Building2,
  },
  {
    label: "Abuse Protection",
    path: "/abuse-protection",
    description: "Rate limits, lockouts and burst controls",
    requiresInstallOperator: true,
    group: "organization",
    icon: ShieldEllipsis,
  },
  {
    label: "Settings",
    path: "/settings",
    description: "Interface and control settings",
    group: "organization",
    icon: Settings,
  },
]

/** The permission check that decides whether a navigation item is shown. */
/** Whether this role is refused the page outright (shown the access-denied state). */
export function pageRefused(item: NavigationItem, allowed: (check?: PermissionCheck) => boolean): boolean {
  return !item.readOnlyForOtherRoles && !allowed(navigationPermission(item))
}

export function navigationPermission(item: NavigationItem): PermissionCheck | undefined {
  if (item.requiresInstallOperator) return { installOperator: true }
  return item.requiredRole ? { role: item.requiredRole as "PLATFORM_ADMIN" } : undefined
}
