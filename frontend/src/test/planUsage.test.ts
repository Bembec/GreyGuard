import { describe, expect, it } from "vitest"

import { meterSummary } from "../components/PlanUsagePanel"

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
