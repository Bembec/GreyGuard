import { describe, expect, it } from "vitest"

import { stateLabel } from "../pages/StatusPage"

describe("public status page", () => {
  it("labels known component states", () => {
    expect(stateLabel("MAJOR_OUTAGE")).toBe("Major outage")
    expect(stateLabel("NOT_CONFIGURED")).toBe("Not configured on this install")
  })
  it("falls back to a readable label for an unknown state", () => {
    expect(stateLabel("PARTIAL_OUTAGE")).toBe("partial outage")
  })
})
