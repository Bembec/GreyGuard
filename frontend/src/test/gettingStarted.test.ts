import { describe, expect, it } from "vitest"

import { onboardingSteps, progressLabel, stepFor } from "../config/onboardingSteps"
import { navigationItems } from "../config/navigation"
import { pilotHeadline, type Pilot } from "../pages/GettingStartedPage"

const pilot = (overrides: Partial<Pilot>): Pilot => ({
  status: "ACTIVE", days_remaining: 40, decision_due: false, decision_due_at: "2026-12-29T00:00:00+00:00",
  ends_at: "2027-01-13T00:00:00+00:00", extended: 0, criteria: [], criteria_met: 0, criteria_total: 6, ...overrides,
})

describe("getting started", () => {
  it("every step links only to real navigation pages", () => {
    const paths = new Set(navigationItems.map((item) => item.path))
    for (const step of Object.values(onboardingSteps)) {
      if (step.href) expect(paths.has(step.href)).toBe(true)
    }
  })
  it("covers every readiness item the backend computes", () => {
    expect(Object.keys(onboardingSteps).sort()).toEqual([
      "auditor_assigned", "export_tested", "first_agent", "integration", "mfa_everyone", "owner_active",
      "plan_assigned", "policy_baseline", "separation_of_duties",
    ])
    expect(stepFor("something_new").action).toBe("Complete this step")
  })
  it("summarizes progress and pilot state", () => {
    expect(progressLabel(4, 9)).toBe("4 of 9 steps complete")
    expect(progressLabel(9, 9)).toBe("Ready for production")
    expect(pilotHeadline(pilot({}))).toBe("40 days left in your pilot")
    expect(pilotHeadline(pilot({ decision_due: true }))).toBe("Conversion decision due")
    expect(pilotHeadline(pilot({ status: "CONVERTED" }))).toBe("Pilot converted")
  })
})
