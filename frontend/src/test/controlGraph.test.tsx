// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ControlGraphView } from "../components/controlGraph/ControlGraphView"
import { columnOf, describeEdge, layout, pathOf, previewFor, type ControlGraph } from "../lib/controlGraph"

const GRAPH: ControlGraph = {
  agent: "billing_bot",
  generated_at: "2026-10-16T12:00:00+00:00",
  window: { since: "2026-09-16T12:00:00+00:00", until: null, retained_from: "2025-10-16T12:00:00+00:00" },
  depth: 2,
  limit: 200,
  nodes: [
    { id: "agent:billing_bot", type: "agent", label: "billing_bot", status: "ACTIVE" },
    { id: "credential:billing_bot", type: "credential", label: "Credential (active)", status: "ACTIVE" },
    { id: "scope:read_file", type: "scope", label: "read_file" },
    { id: "tool:read_file", type: "tool", label: "read_file", status: "ALLOW" },
    { id: "control:global_deny", type: "control", label: "Emergency global deny", status: "ACTIVE" },
    { id: "policy:v1", type: "policy_version", label: "Policy v1", status: "ARCHIVED" },
    { id: "policy:v2", type: "policy_version", label: "Policy v2", status: "PUBLISHED" },
    { id: "request:r1", type: "request", label: "read_file · a.txt", status: "ALLOW", path: "/requests/r1" },
    { id: "request:r2", type: "request", label: "send_email", status: "BLOCK", path: "/requests/r2" },
    { id: "approval:1", type: "approval", label: "Approved by Ada", status: "APPROVED" },
  ],
  edges: [
    { from: "agent:billing_bot", to: "credential:billing_bot", kind: "authenticates_with" },
    { from: "credential:billing_bot", to: "scope:read_file", kind: "grants" },
    { from: "scope:read_file", to: "tool:read_file", kind: "reaches" },
    { from: "control:global_deny", to: "agent:billing_bot", kind: "limits" },
    { from: "policy:v2", to: "agent:billing_bot", kind: "governs" },
    { from: "agent:billing_bot", to: "request:r1", kind: "requested" },
    { from: "agent:billing_bot", to: "request:r2", kind: "requested" },
    { from: "request:r1", to: "tool:read_file", kind: "uses" },
    { from: "request:r1", to: "policy:v2", kind: "decided_by", basis: "recorded", matched_rule_id: "permission:read_file", rule_type: "PERMISSION",
      rule_name: "read_file: ALLOW", outcome: "ALLOW", policy_source: "PUBLISHED", record_intact: true, policy_matches: false },
    { from: "request:r2", to: "policy:v1", kind: "decided_by", basis: "inferred", outcome: "BLOCK",
      note: "Inferred from publication time: this request predates exact decision records." },
    { from: "request:r1", to: "approval:1", kind: "reviewed_by" },
  ],
  counts: { request: 2 },
  decision_basis: { recorded: 1, inferred: 1, unknown: 0 },
  withheld: { install_level: 2 },
  truncated: true,
  dropped: { request: 3 },
}

describe("layout", () => {
  it("puts each node in its column, and controls on the agent with identity", () => {
    const agentId = "agent:billing_bot"
    const node = (id: string) => GRAPH.nodes.find((item) => item.id === id)!
    expect(columnOf(node("control:global_deny"), GRAPH.edges, agentId)).toBe("identity")
    expect(columnOf(node("policy:v2"), GRAPH.edges, agentId)).toBe("tools")
    expect(columnOf(node("approval:1"), GRAPH.edges, agentId)).toBe("outcomes")
  })

  it("groups requests riskiest first", () => {
    expect(layout(GRAPH).requests.map((node) => node.id)).toEqual(["request:r2", "request:r1"])
  })

  it("highlights a node's path without spreading through the agent", () => {
    const path = pathOf("request:r1", GRAPH.edges, "agent:billing_bot")
    expect([...path].sort()).toEqual(["agent:billing_bot", "approval:1", "policy:v2", "request:r1", "tool:read_file"].sort())
    expect(path.has("request:r2")).toBe(false)
  })

  it("says plainly which decisions are exact and which inferred", () => {
    const nodes = new Map(GRAPH.nodes.map((node) => [node.id, node]))
    expect(describeEdge(GRAPH.edges[8], nodes)).toBe("read_file · a.txt was decided by Policy v2 (exact record, rule “read_file: ALLOW”)")
    expect(describeEdge(GRAPH.edges[9], nodes)).toBe("send_email was decided by Policy v1 (inferred from publication time, not recorded)")
  })

  it("offers a preview only for scopes, credentials and tools", () => {
    expect(previewFor(GRAPH.nodes[2])).toMatchObject({ change: "revoke_scope", target: "read_file" })
    expect(previewFor(GRAPH.nodes[1])).toMatchObject({ change: "revoke_credential" })
    expect(previewFor(GRAPH.nodes[3])).toMatchObject({ change: "disable_tool", target: "read_file" })
    expect(previewFor(GRAPH.nodes[7])).toBeNull()
  })
})

const PREVIEW = {
  read_only: true, unreachable_tools: ["read_file"], remaining_tools: [],
  affected_requests: { count: 1, sample: [{ request_id: "r1", timestamp: "2026-10-16T10:00:00+00:00", action: "read_file", policy_decision: "ALLOW", path: "/requests/r1" }] },
  window: { since: "2026-09-16T12:00:00+00:00", retained_from: "2025-10-16T12:00:00+00:00" },
  note: null, how_to_apply: "Nothing changes here. Make the change on the Agents or Policies page, where it is confirmed and recorded.",
}

describe("the Relationships view", () => {
  const fetchMock = vi.fn()
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockImplementation(async (url: string) => ({
      ok: true,
      json: async () => (String(url).includes("/impact-preview") ? PREVIEW : GRAPH),
    }))
    vi.stubGlobal("fetch", fetchMock)
  })
  afterEach(() => { cleanup(); vi.unstubAllGlobals() })

  function renderView() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return render(<QueryClientProvider client={client}><MemoryRouter><ControlGraphView agentName="billing_bot" /></MemoryRouter></QueryClientProvider>)
  }

  it("loads 30 days by default and states the retention horizon, the cap and what is withheld", async () => {
    renderView()
    const summary = await screen.findByTestId("graph-summary")
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/agents\/billing_bot\/graph\?since=/)
    expect(summary.textContent).toContain("1 with an exact decision record")
    expect(summary.textContent).toContain("1 inferred from publication time")
    expect(summary.textContent).toContain("older history is not retained")
    expect(screen.getByText(/limited to 200 items/).textContent).toContain("3 request")
    expect(screen.getByText(/2 install-level incidents/)).toBeTruthy()
  })

  it("labels exact and inferred decisions differently, everywhere", async () => {
    renderView()
    const exact = await screen.findByRole("button", { name: /Request: read_file · a.txt, ALLOW, exact decision record/ })
    expect(within(exact).getByText("Exact")).toBeTruthy()
    const inferred = screen.getByRole("button", { name: /Request: send_email, BLOCK, inferred decision/ })
    expect(within(inferred).getByText("Inferred")).toBeTruthy()

    fireEvent.click(exact)
    const evidence = screen.getByRole("region", { name: "Decision evidence" })
    expect(evidence.textContent).toContain("Exact decision record")
    expect(evidence.textContent).toContain("permission:read_file")
    expect(evidence.textContent).toContain("The stored policy version has changed since this decision")

    fireEvent.click(inferred)
    expect(screen.getByRole("region", { name: "Decision evidence" }).textContent).toContain("Inferred, not recorded")
  })

  it("highlights the selected node's path", async () => {
    renderView()
    fireEvent.click(await screen.findByRole("button", { name: /Request: read_file · a.txt/ }))
    expect(screen.getByRole("button", { name: /Policy version: Policy v2/ }).className).toContain("is-on-path")
    expect(screen.getByRole("button", { name: /Policy version: Policy v1/ }).className).not.toContain("is-on-path")
  })

  it("previews impact read-only, with GET requests only", async () => {
    renderView()
    fireEvent.click(await screen.findByRole("button", { name: /Scope: read_file/ }))
    const preview = screen.getByRole("region", { name: "Impact preview" })
    expect(within(preview).getByText("Read-only")).toBeTruthy()
    fireEvent.click(within(preview).getByRole("button", { name: "Preview impact" }))
    await waitFor(() => expect(screen.getByTestId("impact-preview")).toBeTruthy())
    expect(screen.getByTestId("impact-preview").textContent).toContain("Nothing changes here")
    for (const [, init] of fetchMock.mock.calls) expect((init as RequestInit | undefined)?.method ?? "GET").toBe("GET")
    expect(String(fetchMock.mock.calls.at(-1)?.[0])).toContain("/impact-preview?change=revoke_scope&target=read_file")
  })

  it("offers the same relationships as a list", async () => {
    renderView()
    await screen.findByTestId("graph-summary")
    fireEvent.click(screen.getByRole("button", { name: "Show as a list" }))
    expect(screen.getByText("send_email was decided by Policy v1 (inferred from publication time, not recorded)")).toBeTruthy()
  })
})
