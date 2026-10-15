import type { StatTone } from "./StatCard"

const TONES: Record<string, StatTone> = {
  ACTIVE: "success", APPROVED: "success", ALLOW: "success", ALLOWED: "success", HEALTHY: "success", OPERATIONAL: "success",
  RESOLVED: "success", MITIGATED: "success", VERIFIED: "success", COMPLETED: "success", EXECUTED: "success", LOW: "success",
  PENDING: "warning", ASK: "warning", MEDIUM: "warning", ACKNOWLEDGED: "warning", INVESTIGATING: "warning", DEGRADED: "warning",
  NEEDS_REVIEW: "warning", MONITORED: "info", OPEN: "danger", HIGH: "danger", CRITICAL: "danger", BLOCK: "danger", BLOCKED: "danger",
  DENIED: "danger", REFUSED: "danger", SUSPENDED: "danger", REVOKED: "danger", FAILED: "danger", OUTAGE: "danger",
}

export function toneFor(value: string | null | undefined): StatTone {
  return value ? TONES[value.toUpperCase()] ?? "neutral" : "neutral"
}
