import {describe,expect,it} from "vitest"
import {formatEvidenceHash} from "../pages/ComplianceReportsPage"

describe("security report exports",()=>{
  it("shortens long evidence hashes without hiding both ends",()=>{
    const value="a".repeat(64);const formatted=formatEvidenceHash(value)
    expect(formatted.startsWith("a".repeat(12))).toBe(true)
    expect(formatted.endsWith("a".repeat(8))).toBe(true)
  })
})
