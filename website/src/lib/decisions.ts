// Typed, read-only access to config/decisions.json: the one place approved public facts live.
// Pages never hard-code a contact, domain, price or legal status; they ask here, and an open
// decision returns null so the page can show its safe temporary state.
import registry from "../../../config/decisions.json"
import { siteMode } from "./site"

interface Decision { id: string; status: "open" | "in_progress" | "decided"; value: unknown; question: string; temporary_behaviour: string }

const decisions = new Map<string, Decision>((registry.decisions as Decision[]).map((item) => [item.id, item]))

function record(id: string): Decision {
  const item = decisions.get(id)
  if (!item) throw new Error(`Unknown decision ${id}: add it to config/decisions.json`)
  return item
}

/** The decided value, or null while the decision is open. Never returns an undecided value. */
export function decided<T = string>(id: string): T | null {
  const item = record(id)
  return item.status === "decided" ? (item.value as T) : null
}

export function isDecided(id: string): boolean {
  return record(id).status === "decided"
}

export const productName = decided("BRAND-NAME") ?? "GreyGuard"
export const tagline = decided("BRAND-04")

/** Public company information. Each is null until decided. */
export const company = {
  legalEntity: decided("CO-05"),
  supportEmail: decided("CO-02"),
  securityContact: decided("CO-03"),
  securityMailbox: decided("CO-04"),
  statusPage: decided("CO-08"),
  socialLinks: decided<string[]>("CO-07") ?? [],
}

/** Where demo and sales requests go (COM-07): a booking URL or mailto:, or null while undecided. */
export const demoDestination = decided("COM-07")

/** Published prices (COM-02). Null means the site shows "Contact sales". */
export const pricing = decided("COM-02")

export type LegalDocument = "privacy" | "terms" | "cookies" | "subprocessors" | "accessibility"
const LEGAL_DECISIONS: Record<LegalDocument, string> = { privacy: "LEG-01", terms: "LEG-02", cookies: "LEG-03", subprocessors: "LEG-05", accessibility: "LEG-11" }

/** A legal or policy document's approval state. A publish build refuses an unapproved document. */
export function legalDocument(document: LegalDocument): { approved: boolean; decision: string } {
  const decision = LEGAL_DECISIONS[document]
  const approved = isDecided(decision)
  if (siteMode === "publish" && !approved) {
    throw new Error(`The ${document} document is not approved (${decision}); it cannot be published.`)
  }
  return { approved, decision }
}
