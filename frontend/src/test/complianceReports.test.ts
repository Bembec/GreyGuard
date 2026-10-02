import { describe, expect, it } from "vitest"
import { formatEvidenceHash } from "../pages/ComplianceReportsPage"

describe("Compliance evidence fingerprints", () => {
  it("shortens long hashes while keeping both ends", () => {
    const hash = "1234567890abcdef1234567890abcdef"
    const result = formatEvidenceHash(hash)
    expect(result.startsWith("1234567890ab")).toBe(true)
    expect(result.endsWith("90abcdef")).toBe(true)
  })
})
