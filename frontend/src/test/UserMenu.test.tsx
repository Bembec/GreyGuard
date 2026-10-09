// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest"
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"

import { AuthContext, type Administrator } from "../context/AuthContext"
import { UserMenu } from "../components/navigation/UserMenu"

afterEach(cleanup)

const baseAdministrator: Administrator = {
  admin_id: "adm_1",
  email: "owner@example.com",
  display_name: "Owner",
  role: "PLATFORM_ADMIN",
  permissions: ["read", "admin:manage"],
}

function renderWithAuth(administrator: Administrator, switchActiveOrg = vi.fn()) {
  return render(
    <MemoryRouter>
      <AuthContext.Provider
        value={{
          sessionToken: "gga_test",
          administrator,
          agents: [],
          isAuthenticated: true,
          isResumingSession: false,
          login: async () => {},
          completeSso: async () => {},
          completeSetup: async () => {},
          switchActiveOrg,
          logout: async () => {},
        }}
      >
        <UserMenu />
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

describe("UserMenu org switcher", () => {
  it("shows no org switcher for an administrator with a single organization", () => {
    renderWithAuth({
      ...baseAdministrator,
      organizations: [{ org_id: "org_default", org_name: "Default Organization", operational_role: "PLATFORM_ADMIN", governance_role: "OWNER", status: "ACTIVE", created_at: "2026-01-01" }],
      active_org_id: "org_default",
    })
    fireEvent.click(screen.getByRole("button", { name: /Owner/i }))
    expect(screen.queryByText(/Organization/i)).not.toBeInTheDocument()
  })

  it("lists every organization and marks the active one when there is more than one", () => {
    renderWithAuth({
      ...baseAdministrator,
      organizations: [
        { org_id: "org_default", org_name: "Default Organization", operational_role: "PLATFORM_ADMIN", governance_role: "OWNER", status: "ACTIVE", created_at: "2026-01-01" },
        { org_id: "org_second", org_name: "Second Org", operational_role: "AUDITOR", governance_role: "MEMBER", status: "ACTIVE", created_at: "2026-01-02" },
      ],
      active_org_id: "org_default",
    })
    fireEvent.click(screen.getByRole("button", { name: /Owner/i }))
    const defaultOption = screen.getByRole("menuitemradio", { name: "Default Organization" })
    const secondOption = screen.getByRole("menuitemradio", { name: "Second Org" })
    expect(defaultOption).toHaveAttribute("aria-checked", "true")
    expect(secondOption).toHaveAttribute("aria-checked", "false")
  })

  it("switches to the clicked organization", async () => {
    const switchActiveOrg = vi.fn().mockResolvedValue(undefined)
    renderWithAuth({
      ...baseAdministrator,
      organizations: [
        { org_id: "org_default", org_name: "Default Organization", operational_role: "PLATFORM_ADMIN", governance_role: "OWNER", status: "ACTIVE", created_at: "2026-01-01" },
        { org_id: "org_second", org_name: "Second Org", operational_role: "AUDITOR", governance_role: "MEMBER", status: "ACTIVE", created_at: "2026-01-02" },
      ],
      active_org_id: "org_default",
    }, switchActiveOrg)
    fireEvent.click(screen.getByRole("button", { name: /Owner/i }))
    fireEvent.click(screen.getByRole("menuitemradio", { name: "Second Org" }))
    await waitFor(() => expect(switchActiveOrg).toHaveBeenCalledWith("org_second"))
  })

  it("does not switch when clicking the already-active organization", () => {
    const switchActiveOrg = vi.fn()
    renderWithAuth({
      ...baseAdministrator,
      organizations: [
        { org_id: "org_default", org_name: "Default Organization", operational_role: "PLATFORM_ADMIN", governance_role: "OWNER", status: "ACTIVE", created_at: "2026-01-01" },
        { org_id: "org_second", org_name: "Second Org", operational_role: "AUDITOR", governance_role: "MEMBER", status: "ACTIVE", created_at: "2026-01-02" },
      ],
      active_org_id: "org_default",
    }, switchActiveOrg)
    fireEvent.click(screen.getByRole("button", { name: /Owner/i }))
    fireEvent.click(screen.getByRole("menuitemradio", { name: "Default Organization" }))
    expect(switchActiveOrg).not.toHaveBeenCalled()
  })
})
