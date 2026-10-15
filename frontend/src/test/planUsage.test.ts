import { describe, expect, it } from "vitest"

import { ASSIGNABLE_PLANS, billingSummary, meterSummary, planAssignmentPayload, restrictionSummary, type PlanForm } from "../components/PlanUsagePanel"

describe("plan usage meters", () => {
  it("shows usage against the hard limit when there is one", () => {
    expect(meterSummary(3, { soft: 2, hard: 5 })).toBe("3 of 5")
  })
  it("falls back to the soft limit for report-only meters", () => {
    expect(meterSummary(1200, { soft: 50000, hard: null })).toBe(`${(1200).toLocaleString()} of ${(50000).toLocaleString()}`)
  })
  it("says unlimited when the plan sets no limit", () => {
    expect(meterSummary(7, { soft: null, hard: null })).toBe("7 · unlimited")
  })
})

describe("plan restrictions and billing", () => {
  it("names every reason an org is restricted", () => {
    expect(restrictionSummary(["PLAN_SUSPENDED", "PAYMENT_OVERDUE"])).toBe("the plan is suspended and payment is overdue")
  })
  it("shows nothing for an org without a billing account", () => {
    expect(billingSummary({ enabled: true, linked: false })).toBeNull()
  })
  it("shows the grace deadline while a payment is overdue", () => {
    const grace = "2026-11-01T00:00:00+00:00"
    expect(billingSummary({ enabled: true, linked: true, billing_state: "PAST_DUE", grace_ends_at: grace })).toBe(
      `Payment overdue · grace until ${new Date(grace).toLocaleDateString()}`,
    )
  })
})

describe("planAssignmentPayload", () => {
  const base: PlanForm = { plan: "FOUNDATION", status: "ACTIVE", trialDays: "30", agentsSoft: "", agentsHard: "", integrationsSoft: "", integrationsHard: "" }

  it("sends only plan and status for a standard active plan", () => {
    expect(planAssignmentPayload(base)).toEqual({ body: { plan: "FOUNDATION", status: "ACTIVE" } })
  })

  it("requires a trial length within the server's bounds", () => {
    expect(planAssignmentPayload({ ...base, status: "TRIAL", trialDays: "14" })).toEqual({ body: { plan: "FOUNDATION", status: "TRIAL", trial_days: 14 } })
    expect(planAssignmentPayload({ ...base, status: "TRIAL", trialDays: "91" })).toHaveProperty("error")
    expect(planAssignmentPayload({ ...base, status: "TRIAL", trialDays: "1.5" })).toHaveProperty("error")
  })

  it("requires whole-number contract limits for Dedicated, soft never above hard", () => {
    const dedicated = { ...base, plan: "DEDICATED" as const, agentsSoft: "40", agentsHard: "50", integrationsSoft: "8", integrationsHard: "10" }
    expect(planAssignmentPayload(dedicated)).toEqual({ body: { plan: "DEDICATED", status: "ACTIVE",
      contract_limits: { agents: { soft: 40, hard: 50 }, integrations: { soft: 8, hard: 10 } } } })
    expect(planAssignmentPayload({ ...dedicated, integrationsHard: "" })).toHaveProperty("error")
    expect(planAssignmentPayload({ ...dedicated, agentsSoft: "60" })).toHaveProperty("error")
  })

  it("never offers TRANSITIONAL as an assignable plan", () => {
    expect(ASSIGNABLE_PLANS).not.toContain("TRANSITIONAL")
  })
})
