import { describe, expect, it } from "vitest"

import { capacityMessage } from "../components/CapacityBanner"

const base = { plan_required: false, soft_limits_exceeded: [] as string[], limits: {}, usage: {} }

describe("capacity banner", () => {
  it("is silent when nothing is near a limit", () => {
    expect(capacityMessage(base)).toBeNull()
  })
  it("says a plan is required without implying anything stops", () => {
    expect(capacityMessage({ ...base, plan_required: true })).toMatch(/No plan is assigned.*unaffected/)
  })
  it("names the meters past their soft limit", () => {
    const message = capacityMessage({ ...base, soft_limits_exceeded: ["agents"], limits: { agents: { soft: 20, hard: 25 } }, usage: { agents: 21 } })
    expect(message).toContain("21 of 25 active agents")
    expect(message).toContain("Archive")
  })
  it("never suggests volume meters interrupt anything", () => {
    const message = capacityMessage({ ...base, soft_limits_exceeded: ["deliveries_monthly"], limits: { deliveries_monthly: { soft: 10, hard: null } }, usage: { deliveries_monthly: 12 } })
    expect(message).toContain("monitored only")
  })
})
