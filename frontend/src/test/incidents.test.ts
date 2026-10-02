import { describe, expect, it } from "vitest"
import { formatIncidentStatus, incidentStatuses, isActiveIncident } from "../pages/IncidentCenterPage"

describe("incident workflow", () => {
  it("contains the complete review lifecycle", () => {
    expect(incidentStatuses).toEqual([
      "OPEN", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "DISMISSED",
    ])
  })
  it("formats machine status labels", () => {
    expect(formatIncidentStatus("AWAITING_REVIEW")).toBe("Awaiting Review")
  })
  it("distinguishes active and closed incidents", () => {
    expect(isActiveIncident("INVESTIGATING")).toBe(true)
    expect(isActiveIncident("RESOLVED")).toBe(false)
    expect(isActiveIncident("DISMISSED")).toBe(false)
  })
})
