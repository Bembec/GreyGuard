/** Incident response targets (SLA): durations, and how a stored target is shown and edited. */

export type SlaSeverity = "CRITICAL" | "HIGH"
export type SlaTarget = { acknowledge_minutes: number | null; resolve_minutes: number | null }
export type SlaSettings = {
  org_id: string
  configured: boolean
  severities: SlaSeverity[]
  targets: Partial<Record<SlaSeverity, SlaTarget>>
  updated_by: string | null
  updated_at: string | null
  suggestions: Partial<Record<SlaSeverity, SlaTarget>> | null
  basis: string
  can_edit: boolean
}
export type SlaState = "within" | "due_soon" | "breached" | "met" | "missed" | "not_measurable"
export type IncidentSla = {
  configured: boolean
  state: SlaState | null
  text: string
  deadline?: string
  basis: string | null
}

export type Unit = "minutes" | "hours" | "days"
export const UNIT_MINUTES: Record<Unit, number> = { minutes: 1, hours: 60, days: 1440 }
export const MAX_MINUTES = 365 * 1440

/** The largest unit that divides the minutes exactly, so a stored value round-trips unchanged. */
export function splitMinutes(minutes: number | null): { value: string; unit: Unit } {
  if (minutes == null) return { value: "", unit: "minutes" }
  if (minutes % 1440 === 0) return { value: String(minutes / 1440), unit: "days" }
  if (minutes % 60 === 0) return { value: String(minutes / 60), unit: "hours" }
  return { value: String(minutes), unit: "minutes" }
}

/** null for an empty field; NaN for anything that is not a whole number of minutes in range. */
export function toMinutes(value: string, unit: Unit): number | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  if (!/^\d+$/.test(trimmed)) return Number.NaN
  const minutes = Number(trimmed) * UNIT_MINUTES[unit]
  return minutes >= 1 && minutes <= MAX_MINUTES ? minutes : Number.NaN
}

export function formatMinutes(minutes: number | null): string {
  if (minutes == null) return "No target"
  const { value, unit } = splitMinutes(minutes)
  const singular = value === "1"
  return `${value} ${singular ? unit.slice(0, -1) : unit}`
}

/** Open-incident states that need attention, and their short label for lists. */
export const ATTENTION: Partial<Record<SlaState, string>> = { breached: "SLA breached", due_soon: "SLA due soon" }

export const PHASES = [["acknowledge_minutes", "Acknowledge within"], ["resolve_minutes", "Resolve within"]] as const
export type Phase = (typeof PHASES)[number][0]
export type Field = { value: string; unit: Unit }
export type Form = Record<SlaSeverity, Record<Phase, Field>>

export function formFrom(targets: SlaSettings["targets"], severities: SlaSeverity[]): Form {
  return Object.fromEntries(severities.map((severity) => [severity, {
    acknowledge_minutes: splitMinutes(targets[severity]?.acknowledge_minutes ?? null),
    resolve_minutes: splitMinutes(targets[severity]?.resolve_minutes ?? null),
  }])) as Form
}

/** The targets to save, or the first problem with the form. */
export function readForm(form: Form): { targets: Partial<Record<SlaSeverity, SlaTarget>> } | { error: string } {
  const targets: Partial<Record<SlaSeverity, SlaTarget>> = {}
  for (const [severity, fields] of Object.entries(form) as [SlaSeverity, Record<Phase, Field>][]) {
    const acknowledge = toMinutes(fields.acknowledge_minutes.value, fields.acknowledge_minutes.unit)
    const resolve = toMinutes(fields.resolve_minutes.value, fields.resolve_minutes.unit)
    const name = severity.charAt(0) + severity.slice(1).toLowerCase()
    if (Number.isNaN(acknowledge) || Number.isNaN(resolve)) return { error: `${name}: use a whole number between 1 minute and 365 days.` }
    if (acknowledge != null && resolve != null && resolve < acknowledge) return { error: `${name}: the time to resolve cannot be shorter than the time to acknowledge.` }
    if (acknowledge != null || resolve != null) targets[severity] = { acknowledge_minutes: acknowledge, resolve_minutes: resolve }
  }
  return { targets }
}

