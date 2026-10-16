import { describe, expect, it } from "vitest"

import { accessRequirement } from "../components/page/AccessDenied"
import { navigationItems, pageRefused } from "../config/navigation"
import type { Administrator } from "../context/AuthContext"
import { matchesPermission } from "../hooks/usePermission"
import { describePosture } from "../lib/shellSignals"

const base: Administrator = {
  admin_id: "a", email: "a@example.com", display_name: "A", role: "PLATFORM_ADMIN", permissions: [],
} as Administrator
const operator: Administrator = { ...base, install_operator: true }
const orgAdmin: Administrator = { ...base, install_operator: false }
const auditor: Administrator = { ...base, role: "AUDITOR", install_operator: false }

const item = (path: string) => navigationItems.find((entry) => entry.path === path)!
const refused = (path: string, administrator: Administrator) => pageRefused(item(path), (check) => matchesPermission(administrator, check))

describe("route access", () => {
  it("never refuses an install operator who is a platform administrator", () => {
    for (const entry of navigationItems) expect(refused(entry.path, operator), entry.path).toBe(false)
  })

  it("refuses an auditor role-restricted pages but keeps read-only pages open", () => {
    expect(refused("/simulations", auditor)).toBe(true)
    expect(refused("/abuse-protection", auditor)).toBe(true)
    expect(refused("/secrets", auditor)).toBe(false)
    expect(refused("/service-accounts", auditor)).toBe(false)
    expect(refused("/agents", auditor)).toBe(false)
  })

  it("refuses an org administrator install-wide pages only", () => {
    expect(refused("/observability", orgAdmin)).toBe(true)
    expect(refused("/team", orgAdmin)).toBe(true)
    expect(refused("/security-exports", orgAdmin)).toBe(false)
  })

  it("explains a refusal by the role it needs, not by what the page holds", () => {
    expect(accessRequirement(item("/observability")).title).toBe("Install operator access required")
    expect(accessRequirement(item("/simulations")).title).toBe("Platform Administrator access required")
  })
})

describe("control-plane posture", () => {
  it("only reports what /status measured", () => {
    expect(describePosture("OPERATIONAL", false).tone).toBe("ok")
    expect(describePosture("DEGRADED", false).tone).toBe("warning")
    expect(describePosture("MAINTENANCE", false).tone).toBe("warning")
    expect(describePosture("MAJOR_OUTAGE", false).tone).toBe("danger")
  })

  it("never claims the control plane is up without an answer", () => {
    for (const posture of [describePosture(undefined, false), describePosture(undefined, true), describePosture("SOMETHING_NEW", false)]) {
      expect(posture.tone).toBe("unknown")
      expect(posture.title.toLowerCase()).not.toContain("operational")
    }
  })
})

describe("session resume", () => {
  it("ends a session only when the server rejects it", async () => {
    const { isSessionRejected } = await import("../context/AuthContext")
    const { ApiError } = await import("../api/client")
    expect(isSessionRejected(new ApiError("expired", 401))).toBe(true)
    expect(isSessionRejected(new ApiError("forbidden", 403))).toBe(true)
    expect(isSessionRejected(new ApiError("slow down", 429))).toBe(false)
    expect(isSessionRejected(new ApiError("unavailable", 503))).toBe(false)
    expect(isSessionRejected(new TypeError("Failed to fetch"))).toBe(false)
  })

  it("backs off, then retries every 30 seconds", async () => {
    const { resumeRetryDelay } = await import("../context/AuthContext")
    expect([0, 1, 2, 3, 4, 10].map(resumeRetryDelay)).toEqual([2_000, 4_000, 8_000, 16_000, 30_000, 30_000])
  })
})
