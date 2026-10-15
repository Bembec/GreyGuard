import register from "../../content/claims.json"
import { siteMode } from "./site"

export type Availability = "verified" | "pilot" | "preview" | "planned"

export interface Claim {
  id: string
  group: string
  kind: "capability" | "limitation"
  availability: Availability
  claim: string
  scope: string
  evidence: string[]
  owner: string
  status: "proposed" | "approved" | "withdrawn"
  approved_by: string | null
  approved_on: string | null
  review_by: string
  pages: string[]
}

const claims = new Map<string, Claim>((register.claims as Claim[]).map((claim) => [claim.id, claim]))

/**
 * The only way page copy may state something GreyGuard does. An unknown id always fails the build.
 * A publish build also fails on any claim the project owner has not approved, so an unapproved
 * statement can never reach the public site.
 */
export function getClaim(id: string): Claim {
  const claim = claims.get(id)
  if (!claim) throw new Error(`Unknown claim ${id}: add it to website/content/claims.json first.`)
  if (claim.status === "withdrawn") throw new Error(`Claim ${id} is withdrawn and may not be used.`)
  if (siteMode === "publish" && claim.status !== "approved") {
    throw new Error(`Claim ${id} is ${claim.status}, not approved; it cannot be published.`)
  }
  return claim
}

export function claimsInGroup(group: string): Claim[] {
  return [...claims.values()].filter((claim) => claim.group === group && claim.status !== "withdrawn" && (siteMode === "preview" || claim.status === "approved"))
}

export const availabilityLabel: Record<Availability, string> = {
  verified: "Verified",
  pilot: "Pilot",
  preview: "Preview",
  planned: "Planned",
}
