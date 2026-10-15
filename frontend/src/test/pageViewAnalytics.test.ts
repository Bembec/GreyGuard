import { describe, expect, it } from "vitest"

import { pageViewPath } from "../lib/pageViewAnalytics"

describe("page-view analytics", () => {
  it("counts exact navigation paths only", () => {
    expect(pageViewPath("/agents", null)).toBe("/agents")
    expect(pageViewPath("/agents/secret-billing-agent", null)).toBeNull()
    expect(pageViewPath("/requests/3f2a9c", null)).toBeNull()
  })
  it("sends nothing when the browser asks not to be tracked", () => {
    expect(pageViewPath("/agents", "1")).toBeNull()
  })
})
