import type { Administrator } from "../context/AuthContext"
import { matchesPermission } from "../hooks/usePermission"

/**
 * The composable Command Center (Master Roadmap v3, P7.5 item 2): one home with a preset per
 * role and per-user pinning, rather than six separate dashboards.
 *
 * Every panel and KPI here reads data that every role may read (all are GET routes), so no
 * preset ever shows a panel only to disable it. Presets decide what is relevant, not what is
 * allowed; acting on what a panel shows still happens on the page it links to, under that
 * page's own permission checks.
 */

export type PanelId = "approvals" | "incidents" | "risk" | "readiness" | "evidence" | "plan" | "reports"
export type KpiId = "pending" | "incidents" | "signals" | "agents" | "highRisk" | "blocked"
export type PresetId = "platform-admin" | "security-analyst" | "approver" | "auditor" | "owner" | "billing"

export interface PanelDefinition {
  id: PanelId
  title: string
  description: string
  /** Wide panels take two of the three columns on a desktop screen. */
  wide: boolean
}

export const PANELS: Record<PanelId, PanelDefinition> = {
  approvals: { id: "approvals", title: "Approval queue", description: "Requests waiting for a human decision", wide: true },
  incidents: { id: "incidents", title: "Open incidents", description: "Incidents nobody has closed yet", wide: false },
  risk: { id: "risk", title: "Agent risk", description: "Agents ranked by accumulated risk", wide: true },
  readiness: { id: "readiness", title: "Readiness", description: "Onboarding steps and service components", wide: false },
  evidence: { id: "evidence", title: "Latest decisions and events", description: "The newest tamper-evident evidence", wide: true },
  plan: { id: "plan", title: "Plan & usage", description: "The plan, its limits and current usage", wide: false },
  reports: { id: "reports", title: "Compliance reports", description: "The newest sealed evidence snapshots", wide: false },
}

export const PANEL_ORDER: PanelId[] = ["approvals", "incidents", "risk", "readiness", "evidence", "plan", "reports"]

export interface Preset {
  id: PresetId
  label: string
  /** One line on what this view is for, shown in the switcher. */
  purpose: string
  kpis: KpiId[]
  panels: PanelId[]
  /** Who may choose this view. */
  availableTo: (administrator: Administrator) => boolean
}

const canApprove = (administrator: Administrator) => matchesPermission(administrator, { permission: "approval:manage" })
const governs = (administrator: Administrator, ...roles: string[]) => roles.includes(administrator.governance_role ?? "")

export const PRESETS: Preset[] = [
  {
    id: "platform-admin",
    label: "Platform Administrator",
    purpose: "Decisions, incidents, agent risk and organization readiness",
    kpis: ["pending", "incidents", "signals", "agents", "highRisk"],
    panels: ["approvals", "incidents", "risk", "readiness", "evidence"],
    availableTo: (administrator) => administrator.role === "PLATFORM_ADMIN",
  },
  {
    id: "security-analyst",
    label: "Security Analyst",
    purpose: "Incidents and signals first, then the decisions and risk behind them",
    kpis: ["incidents", "signals", "pending", "highRisk"],
    panels: ["incidents", "approvals", "risk", "evidence"],
    availableTo: (administrator) => administrator.role === "PLATFORM_ADMIN" || administrator.role === "SECURITY_ANALYST",
  },
  {
    id: "approver",
    label: "Approver",
    purpose: "Only the requests waiting for your decision, and the evidence behind them",
    kpis: ["pending", "highRisk", "blocked"],
    panels: ["approvals", "evidence"],
    availableTo: canApprove,
  },
  {
    id: "auditor",
    label: "Auditor",
    purpose: "Evidence, sealed reports and how agents have behaved",
    kpis: ["agents", "blocked", "incidents"],
    panels: ["evidence", "reports", "risk", "readiness"],
    availableTo: () => true,
  },
  {
    id: "owner",
    label: "Organization Owner",
    purpose: "Readiness, plan, open incidents and the reports reviewers will ask for",
    kpis: ["incidents", "agents", "pending"],
    panels: ["readiness", "plan", "incidents", "reports"],
    availableTo: (administrator) => governs(administrator, "OWNER"),
  },
  {
    id: "billing",
    label: "Billing Administrator",
    purpose: "The plan, its limits and what is in use",
    kpis: ["agents"],
    panels: ["plan", "readiness"],
    availableTo: (administrator) => governs(administrator, "OWNER", "BILLING_ADMIN"),
  },
]

const presetsById = new Map(PRESETS.map((preset) => [preset.id, preset]))

export function presetsFor(administrator: Administrator | null): Preset[] {
  return administrator ? PRESETS.filter((preset) => preset.availableTo(administrator)) : []
}

/** The view a person starts on: their operational role's, which every account has. */
export function defaultPresetFor(administrator: Administrator | null): Preset {
  const id: PresetId = administrator?.role === "PLATFORM_ADMIN" ? "platform-admin"
    : administrator?.role === "SECURITY_ANALYST" ? "security-analyst"
    : "auditor"
  return presetsById.get(id)!
}

/** What one person has changed, kept on this device under their own account id. */
export interface Customization {
  preset?: PresetId
  /** Panels added to the preset's own. */
  pinned: PanelId[]
  /** The preset's panels this person has hidden. */
  hidden: PanelId[]
}

const EMPTY: Customization = { pinned: [], hidden: [] }
const panelIds = new Set<string>(PANEL_ORDER)
const isPanelId = (value: unknown): value is PanelId => typeof value === "string" && panelIds.has(value)

export function storageKeyFor(adminId: string): string {
  return `greyguard_command_center:${adminId}`
}

/** Reads a stored customization, dropping anything that is not a known preset or panel. */
export function parseCustomization(raw: string | null): Customization {
  try {
    const value = JSON.parse(raw ?? "null") as Partial<Record<keyof Customization, unknown>> | null
    if (!value || typeof value !== "object") return EMPTY
    return {
      preset: typeof value.preset === "string" && presetsById.has(value.preset as PresetId) ? value.preset as PresetId : undefined,
      pinned: Array.isArray(value.pinned) ? [...new Set(value.pinned.filter(isPanelId))] : [],
      hidden: Array.isArray(value.hidden) ? [...new Set(value.hidden.filter(isPanelId))] : [],
    }
  } catch {
    return EMPTY
  }
}

export interface Layout {
  preset: Preset
  presets: Preset[]
  kpis: KpiId[]
  panels: PanelId[]
}

/**
 * The layout to draw: the chosen preset if this person may still use it (a role can change),
 * otherwise their default; its panels minus the hidden ones, then their pins in panel order.
 */
export function resolveLayout(administrator: Administrator | null, customization: Customization): Layout {
  const presets = presetsFor(administrator)
  const chosen = customization.preset ? presets.find((preset) => preset.id === customization.preset) : undefined
  const preset = chosen ?? defaultPresetFor(administrator)
  const base = preset.panels.filter((id) => !customization.hidden.includes(id))
  const extra = PANEL_ORDER.filter((id) => customization.pinned.includes(id) && !base.includes(id))
  return { preset, presets, kpis: preset.kpis, panels: [...base, ...extra] }
}

/** Shows or hides one panel for the current preset, keeping pins and hides minimal. */
export function togglePanel(customization: Customization, preset: Preset, panel: PanelId, show: boolean): Customization {
  const inPreset = preset.panels.includes(panel)
  const pinned = customization.pinned.filter((id) => id !== panel)
  const hidden = customization.hidden.filter((id) => id !== panel)
  if (show && !inPreset) pinned.push(panel)
  if (!show && inPreset) hidden.push(panel)
  return { ...customization, pinned, hidden }
}
