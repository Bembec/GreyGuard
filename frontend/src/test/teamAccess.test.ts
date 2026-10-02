import { describe, expect, it } from "vitest"
import { formatRole, roleDescriptions } from "../pages/TeamAccessPage"
describe("administrator roles", () => {
  it("defines three least-privilege roles", () => {
    expect(Object.keys(roleDescriptions)).toEqual(["PLATFORM_ADMIN", "SECURITY_ANALYST", "AUDITOR"])
  })
  it("formats role labels for people", () => {
    expect(formatRole("PLATFORM_ADMIN")).toBe("Platform Admin")
  })
})
