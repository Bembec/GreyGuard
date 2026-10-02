import { describe, expect, it } from "vitest"
import { serviceKeyDisplay } from "../pages/ServiceAccountsPage"

describe("Service-account key display", () => {
  it("shows the safe prefix while masking secret material", () => {
    const display = serviceKeyDisplay("ggsa_1234567890")
    expect(display).toContain("ggsa_1234567890")
    expect(display).toContain("••••")
  })
})
