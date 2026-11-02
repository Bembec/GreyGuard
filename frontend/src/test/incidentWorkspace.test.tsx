// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ToastProvider } from "../context/ToastContext"
import { safePackageFilename } from "../lib/incidentPackage"
import IncidentWorkspacePage, { type Workspace } from "../pages/IncidentWorkspacePage"

const BASE: Workspace = {
  incident: { alert_id: "a1", title: "BLOCK detected for billing_bot", summary: "Policy decision BLOCK for send_email.", severity: "HIGH",
    status: "OPEN", created_at: "2026-10-16T10:00:00+00:00", updated_at: "2026-10-16T10:00:00+00:00", event_type: "POLICY",
    agent_name: "billing_bot", request_id: "r1", resolution_note: null, install_level: false },
  owner: { name: null, email: null, kind: null, candidates: [{ email: "ada@example.com", display_name: "Ada" }] },
  sla: { configured: false, state: null, text: "No SLA set", basis: null },
  explanation: null,
  timeline: { entries: [
    { type: "NOTE_ADDED", timestamp: "2026-10-16T10:05:00+00:00", actor: "ada@example.com", text: "Note: looking", path: null, action_record: true },
    { type: "REQUEST", timestamp: "2026-10-16T10:00:00+00:00", actor: "billing_bot", text: "Requested send_email; decided BLOCK.", path: "/requests/r1", trigger: true },
  ], truncated: false, window: { since: "2026-10-15T10:00:00+00:00" } },
  agent: { agent_name: "billing_bot", known: true, status: "ACTIVE", risk_score: 40, credential_status: "ACTIVE", scopes: ["send_email"],
    path: "/agents/billing_bot", graph_path: "/agents/billing_bot?tab=relationships" },
  related: [],
  integrity: { decision_record_intact: true, policy_unchanged: true, basis: "recorded", audit_chain: null },
  actions: {
    primary: { id: "status:ACKNOWLEDGED", label: "Acknowledge", to_status: "ACKNOWLEDGED", requires_note: false, available: true, unavailable_reason: null },
    others: [
      { id: "note", label: "Add a note", available: true, unavailable_reason: null },
      { id: "status:DISMISSED", label: "Dismiss", to_status: "DISMISSED", requires_note: true, available: true, unavailable_reason: null },
      { id: "revoke_credential", label: "Revoke the agent's credential", target: "billing_bot", confirm_text: "billing_bot", available: true, unavailable_reason: null },
      { id: "terminate_isolation", label: "Stop running isolated executions", target: "TERMINATE", confirm_text: "TERMINATE", available: false,
        unavailable_reason: "Your role, Security Admin, cannot do this: it needs the Platform Administrator role." },
      { id: "export", label: "Export the incident package", available: true, unavailable_reason: null },
      { id: "verify_chain", label: "Verify the audit chain", available: false, unavailable_reason: "Only an install operator can verify the install-wide audit chain." },
    ],
  },
  why_you_see_this: "You see this because your role can read your organization's incidents.",
}

const AUDITOR_REASON = "Your role, Auditor, can view incidents but not change them."
const AUDITOR: Workspace = {
  ...BASE,
  owner: { name: null, email: null, kind: null },
  actions: {
    primary: { ...BASE.actions.primary!, available: false, unavailable_reason: AUDITOR_REASON },
    others: BASE.actions.others.map((action) => action.id === "verify_chain" ? action : { ...action, available: false, unavailable_reason: AUDITOR_REASON }),
  },
}

const fetchMock = vi.fn()

function respond(body: unknown, status = 200) {
  fetchMock.mockImplementation(async (_url: string, init?: RequestInit) => {
    if ((init?.method ?? "GET") !== "GET") return { ok: true, status: 200, json: async () => ({}) }
    return { ok: status < 400, status, json: async () => body }
  })
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}><ToastProvider><MemoryRouter initialEntries={["/incidents/a1"]}>
      <Routes><Route path="/incidents/:alertId" element={<IncidentWorkspacePage />} /></Routes>
    </MemoryRouter></ToastProvider></QueryClientProvider>,
  )
}

beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock) })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe("the incident workspace", () => {
  it("shows the incident, its owner and SLA state, the timeline and the agent", async () => {
    respond(BASE)
    renderPage()
    expect(await screen.findByRole("heading", { level: 1, name: "BLOCK detected for billing_bot" })).toBeTruthy()
    const meta = screen.getByTestId("incident-meta")
    expect(meta.textContent).toContain("No SLA set")
    expect(meta.textContent).toContain("No owner")
    expect(screen.getByRole("link", { name: "Requested send_email; decided BLOCK." }).getAttribute("href")).toBe("/requests/r1")
    expect(screen.getByRole("link", { name: /Open the Control Graph/ }).getAttribute("href")).toBe("/agents/billing_bot?tab=relationships")
  })

  it("filters the timeline to the action record", async () => {
    respond(BASE)
    renderPage()
    fireEvent.click(await screen.findByRole("button", { name: "Action record" }))
    expect(screen.getByText("Note: looking")).toBeTruthy()
    expect(screen.queryByText("Requested send_email; decided BLOCK.")).toBeNull()
  })

  it("acknowledges with a PUT that keeps the owner, and asks for a note before dismissing", async () => {
    respond(BASE)
    renderPage()
    fireEvent.click((await screen.findAllByRole("button", { name: "Acknowledge" }))[0])
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "PUT")).toBe(true))
    const put = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "PUT")!
    expect(String(put[0])).toContain("/alerts/a1")
    expect(JSON.parse(String((put[1] as RequestInit).body))).toEqual({ status: "ACKNOWLEDGED", assigned_to: null, note: null })
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }))
    const form = screen.getByLabelText("Dismiss: a note is required").closest("form")!
    expect((within(form).getByRole("button", { name: "Dismiss" }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("assigns an owner by member email, never free text", async () => {
    respond(BASE)
    renderPage()
    fireEvent.change(await screen.findByLabelText("Choose an owner"), { target: { value: "ada@example.com" } })
    fireEvent.click(screen.getByRole("button", { name: "Assign" }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "PUT")).toBe(true))
    const put = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "PUT")!
    expect(JSON.parse(String((put[1] as RequestInit).body)).assigned_to).toBe("ada@example.com")
  })

  it("shows an auditor every action disabled, with a reason from their role", async () => {
    respond(AUDITOR)
    renderPage()
    await screen.findByRole("heading", { level: 1 })
    for (const button of screen.getAllByRole("button", { name: "Acknowledge" })) expect((button as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getAllByText(AUDITOR_REASON).length).toBeGreaterThan(0)
    expect(screen.queryByLabelText("Choose an owner")).toBeNull()
    expect(screen.getByText(/Only an install operator can verify/)).toBeTruthy()
  })

  it("keeps the rest of the page when one section fails", async () => {
    respond({ ...BASE, related: { error: "The related incidents could not be loaded. Try again." } })
    renderPage()
    expect(await screen.findByText("The related incidents could not be loaded. Try again.")).toBeTruthy()
    expect(screen.getByText("Requested send_email; decided BLOCK.")).toBeTruthy()
  })

  it("says not found, without saying whether it exists elsewhere", async () => {
    respond({ detail: "Incident not found." }, 404)
    renderPage()
    expect(await screen.findByText("Incident not found")).toBeTruthy()
    expect(screen.getByText("It does not exist, or it is not in your organization.")).toBeTruthy()
  })

  it("contains only after the exact target is typed and a reason is given, and posts both", async () => {
    respond(BASE)
    renderPage()
    fireEvent.click(await screen.findByRole("button", { name: "Revoke the agent's credential" }))
    const dialog = screen.getByRole("alertdialog")
    const confirm = () => within(dialog).getAllByRole("button", { name: "Revoke the agent's credential" }).at(-1) as HTMLButtonElement
    expect(confirm().disabled).toBe(true)
    fireEvent.change(within(dialog).getByLabelText(/to confirm/), { target: { value: "billing_bo" } })
    fireEvent.change(within(dialog).getByLabelText("Reason (recorded)"), { target: { value: "leaked key" } })
    expect(confirm().disabled).toBe(true)
    fireEvent.change(within(dialog).getByLabelText(/to confirm/), { target: { value: "billing_bot" } })
    expect(confirm().disabled).toBe(false)
    fireEvent.click(confirm())
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/incidents/a1/actions"))).toBe(true))
    const post = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/incidents/a1/actions"))!
    expect((post[1] as RequestInit).method).toBe("POST")
    expect(JSON.parse(String((post[1] as RequestInit).body))).toEqual({ action: "revoke_credential", confirm: "billing_bot", reason: "leaked key" })
  })

  it("shows a containment action the role cannot take as disabled, with the reason", async () => {
    respond(BASE)
    renderPage()
    expect((await screen.findByRole("button", { name: "Stop running isolated executions" }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/it needs the Platform Administrator role/)).toBeTruthy()
  })

  it("exports the package with a POST, so the export is recorded", async () => {
    respond(BASE)
    if (!URL.createObjectURL) Object.assign(URL, { createObjectURL: () => "", revokeObjectURL: () => undefined })
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:x")
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined)
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined)
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (String(url).endsWith("/package")) return { ok: true, status: 200, json: async () => ({ manifest: { package: "abcdef0123456789" } }) }
      if ((init?.method ?? "GET") !== "GET") return { ok: true, status: 200, json: async () => ({}) }
      return { ok: true, status: 200, json: async () => BASE }
    })
    renderPage()
    fireEvent.click(await screen.findByRole("button", { name: "Export package" }))
    await waitFor(() => expect(createObjectURL).toHaveBeenCalled())
    const post = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/incidents/a1/package"))!
    expect((post[1] as RequestInit).method).toBe("POST")
    expect(await screen.findByText(/SHA-256 abcdef012345/)).toBeTruthy()
  })

  it("never lets an incident id shape the download filename", () => {
    expect(safePackageFilename("a1")).toBe("greyguard-incident-a1.json")
    expect(safePackageFilename("../../etc/x y")).toBe("greyguard-incident-------etc-x-y.json")
  })

  it("shows the SLA state with its deadline, a breach in the timeline, and a link to the targets when none are set", async () => {
    respond({ ...BASE,
      sla: { configured: true, state: "breached", text: "Acknowledge target breached (15 minutes)", deadline: "2026-10-16T10:15:00+00:00",
        basis: "Measured against your organization's current targets, from when the incident opened." },
      timeline: { truncated: false, window: { since: "2026-10-15T10:00:00+00:00" }, entries: [{ type: "SLA_BREACH", timestamp: "2026-10-16T10:15:00+00:00",
        actor: "GreyGuard", text: "SLA breached: not acknowledged within 15 minutes.", path: null }] } })
    renderPage()
    const meta = await screen.findByTestId("incident-meta")
    expect(meta.textContent).toContain("Acknowledge target breached (15 minutes) · was due")
    expect(screen.getByText("SLA breached: not acknowledged within 15 minutes.")).toBeTruthy()
    cleanup()
    respond(BASE)
    renderPage()
    expect((await screen.findByRole("link", { name: "Response targets" })).getAttribute("href")).toBe("/incidents#response-targets")
  })
})
