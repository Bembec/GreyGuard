import { describe, expect, it } from "vitest"
import { formatAgentEvidenceDate } from "../pages/AgentDetailPage"

describe("Agent investigation", () => {
  it("formats evidence timestamps", () => {
    expect(formatAgentEvidenceDate("2026-10-03T08:00:00Z")).not.toBe("2026-10-03T08:00:00Z")
  })
  it("labels absent lifecycle evidence", () => {
    expect(formatAgentEvidenceDate(null)).toBe("Not recorded")
  })
})
