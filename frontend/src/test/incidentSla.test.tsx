// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { IncidentSlaPanel } from "../components/incident/IncidentSlaPanel"
import { AuthContext, type Administrator } from "../context/AuthContext"
import { ToastProvider } from "../context/ToastContext"
import { formatMinutes, formFrom, readForm, splitMinutes, toMinutes, type SlaSettings } from "../lib/incidentSla"

const admin: Administrator = { admin_id: "adm_1", email: "a@example.com", display_name: "A", role: "PLATFORM_ADMIN", permissions: ["read", "admin:manage"], active_org_id: "org_1" }
const SUGGESTED = { CRITICAL: { acknowledge_minutes: 15, resolve_minutes: 240 }, HIGH: { acknowledge_minutes: 60, resolve_minutes: 1440 } }
const EMPTY: SlaSettings = { org_id: "org_1", configured: false, severities: ["CRITICAL", "HIGH"], targets: {}, updated_by: null, updated_at: null,
  suggestions: SUGGESTED, basis: "Measured against your organization's current targets, from when the incident opened.", can_edit: true }
const SET: SlaSettings = { ...EMPTY, configured: true, targets: SUGGESTED, suggestions: null, updated_by: "a@example.com", updated_at: "2026-11-02T10:00:00+00:00" }

const fetchMock = vi.fn()

function serve(settings: SlaSettings) {
  fetchMock.mockImplementation(async (_url: string, init?: RequestInit) => {
    if (init?.method === "PUT") {
      const targets = JSON.parse(String(init.body)).targets
      const configured = Object.keys(targets).length > 0
      return { ok: true, status: 200, json: async () => ({ ...settings, configured, targets, suggestions: configured ? null : SUGGESTED, updated_at: configured ? "2026-11-02T11:00:00+00:00" : null }) }
    }
    return { ok: true, status: 200, json: async () => settings }
  })
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}><ToastProvider>
      <AuthContext.Provider value={{
        sessionToken: "gga_test", administrator: admin, isAuthenticated: true, isResumingSession: false, isWaitingForControlPlane: false,
        login: async () => {}, completeSso: async () => {}, completeSetup: async () => {}, switchActiveOrg: async () => {}, logout: async () => {},
      }}><IncidentSlaPanel /></AuthContext.Provider>
    </ToastProvider></QueryClientProvider>,
  )
}

function puts() {
  return fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "PUT")
}

beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe("durations", () => {
  it("round-trips stored minutes through the largest exact unit", () => {
    expect(splitMinutes(240)).toEqual({ value: "4", unit: "hours" })
    expect(splitMinutes(1440)).toEqual({ value: "1", unit: "days" })
    expect(splitMinutes(90)).toEqual({ value: "90", unit: "minutes" })
    expect(splitMinutes(null)).toEqual({ value: "", unit: "minutes" })
    expect(formatMinutes(60)).toBe("1 hour")
    expect(formatMinutes(15)).toBe("15 minutes")
  })

  it("accepts whole numbers in range only", () => {
    expect(toMinutes("", "hours")).toBeNull()
    expect(toMinutes("2", "hours")).toBe(120)
    for (const bad of ["0", "1.5", "-3", "abc", "366"]) expect(toMinutes(bad, bad === "366" ? "days" : "minutes")).toBeNaN()
  })

  it("refuses a resolve time shorter than the acknowledge time, and drops a severity with no times", () => {
    const form = formFrom({}, ["CRITICAL", "HIGH"])
    expect(readForm(form)).toEqual({ targets: {} })
    form.HIGH.acknowledge_minutes = { value: "2", unit: "hours" }
    form.HIGH.resolve_minutes = { value: "30", unit: "minutes" }
    expect(readForm(form)).toEqual({ error: "High: the time to resolve cannot be shorter than the time to acknowledge." })
  })
})

describe("the response targets panel", () => {
  it("says No SLA set, offers the suggestions, and saves nothing until Save", async () => {
    serve(EMPTY)
    renderPanel()
    expect(await screen.findByText(/No SLA set\. Incidents show no deadlines/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Fill in the suggestions" }))
    expect((screen.getByLabelText("Acknowledge within", { selector: "#sla-CRITICAL-acknowledge_minutes" }) as HTMLInputElement).value).toBe("15")
    expect(puts()).toHaveLength(0)
    fireEvent.click(screen.getByRole("button", { name: "Save targets" }))
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(String(puts()[0][0])).toContain("/organizations/org_1/incident-sla")
    expect(JSON.parse(String((puts()[0][1] as RequestInit).body))).toEqual({ targets: SUGGESTED })
  })

  it("blocks saving an invalid form and says why", async () => {
    serve(EMPTY)
    renderPanel()
    fireEvent.change(await screen.findByLabelText("Acknowledge within", { selector: "#sla-HIGH-acknowledge_minutes" }), { target: { value: "1.5" } })
    expect(screen.getByRole("alert").textContent).toContain("whole number")
    expect((screen.getByRole("button", { name: "Save targets" }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("asks before removing every target, then sends an empty set", async () => {
    serve(SET)
    renderPanel()
    fireEvent.click(await screen.findByRole("button", { name: "Remove all targets" }))
    fireEvent.click(screen.getByRole("button", { name: "Remove targets" }))
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(JSON.parse(String((puts()[0][1] as RequestInit).body))).toEqual({ targets: {} })
  })

  it("shows the targets read-only to a role that cannot change them", async () => {
    serve({ ...SET, can_edit: false })
    renderPanel()
    expect(await screen.findByText("Only a Platform Administrator can change response targets.")).toBeTruthy()
    expect(screen.getByText("Acknowledge: 15 minutes · Resolve: 4 hours")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Save targets" })).toBeNull()
  })
})
