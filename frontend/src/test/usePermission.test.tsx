// @vitest-environment jsdom
import { renderHook } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it } from "vitest"

import { AuthContext, type Administrator } from "../context/AuthContext"
import { usePermission } from "../hooks/usePermission"

function wrapperFor(administrator: Administrator | null) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <AuthContext.Provider
        value={{
          sessionToken: administrator ? "gga_test" : null,
          administrator,
          agents: [],
          isAuthenticated: Boolean(administrator),
          isResumingSession: false,
          login: async () => {},
          completeSso: async () => {},
          completeSetup: async () => {},
          switchActiveOrg: async () => {},
          logout: async () => {},
        }}
      >
        {children}
      </AuthContext.Provider>
    )
  }
}

const platformAdmin: Administrator = {
  admin_id: "adm_1", email: "owner@example.com", display_name: "Owner",
  role: "PLATFORM_ADMIN", permissions: ["read", "admin:manage"],
}

const auditor: Administrator = {
  admin_id: "adm_2", email: "auditor@example.com", display_name: "Auditor",
  role: "AUDITOR", permissions: ["read"],
}

describe("usePermission", () => {
  it("passes a missing check unconditionally, even with no administrator", () => {
    const { result } = renderHook(() => usePermission(undefined), { wrapper: wrapperFor(null) })
    expect(result.current).toBe(true)
  })

  it("fails any real check when there is no administrator", () => {
    const { result } = renderHook(() => usePermission({ role: "PLATFORM_ADMIN" }), { wrapper: wrapperFor(null) })
    expect(result.current).toBe(false)
  })

  it("matches an exact role", () => {
    const { result } = renderHook(() => usePermission({ role: "PLATFORM_ADMIN" }), { wrapper: wrapperFor(platformAdmin) })
    expect(result.current).toBe(true)
  })

  it("rejects a non-matching exact role", () => {
    const { result } = renderHook(() => usePermission({ role: "PLATFORM_ADMIN" }), { wrapper: wrapperFor(auditor) })
    expect(result.current).toBe(false)
  })

  it("matches anyRole - fixes the single exact-match limitation nav filtering had", () => {
    const { result } = renderHook(
      () => usePermission({ anyRole: ["PLATFORM_ADMIN", "AUDITOR"] }),
      { wrapper: wrapperFor(auditor) },
    )
    expect(result.current).toBe(true)
  })

  it("matches a held permission string", () => {
    const { result } = renderHook(() => usePermission({ permission: "admin:manage" }), { wrapper: wrapperFor(platformAdmin) })
    expect(result.current).toBe(true)
  })

  it("rejects a permission the administrator does not hold", () => {
    const { result } = renderHook(() => usePermission({ permission: "admin:manage" }), { wrapper: wrapperFor(auditor) })
    expect(result.current).toBe(false)
  })

  it("matches anyPermission when at least one is held", () => {
    const { result } = renderHook(
      () => usePermission({ anyPermission: ["admin:manage", "read"] }),
      { wrapper: wrapperFor(auditor) },
    )
    expect(result.current).toBe(true)
  })
})
