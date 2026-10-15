import { describe, expect, it } from "vitest"

import { billingSummary, meterSummary, restrictionSummary } from "../components/PlanUsagePanel"

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
