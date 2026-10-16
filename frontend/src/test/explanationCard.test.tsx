// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it } from "vitest"

import { ExplanationCard, type Explanation } from "../components/explanation/ExplanationCard"

afterEach(cleanup)

const RECORDED: Explanation = {
  request_id: "r1", decision: "BLOCK", basis: "recorded",
  reason: "Blocked because policy v4 does not allow send_email.",
  policy: { basis: "recorded", version_id: "p4", version_number: 4, source: "PUBLISHED", published_at: "2026-10-12T09:00:00+00:00", unchanged_since_decision: true },
  matched_rule: { id: "permission:send_email", name: "send_email: BLOCK", type: "PERMISSION", snapshot: {} },
  authentication: { method: "CLIENT_CERTIFICATE", summary: "The agent authenticated with a client certificate verified at the gateway." },
  requested: { action: "send_email", target: "ops@example.com", dry_run: false, agent_name: "billing_bot", decided_at: "2026-10-16T10:00:00+00:00" },
  approval_path: { required: false, status: "NOT_REQUIRED", reviews: [], summary: "No approval needed: the decision did not ask for one." },
  next_step: { text: "If this action is legitimate for this agent, propose a policy change in Policies.", path: "/policies", available: false,
    unavailable_reason: "Your role, Auditor, can view this but cannot take this step." },
  limitations: [{ id: "prompt", text: "GreyGuard sees the tool request an agent makes, not the prompt or reasoning that led to it." }],
  integrity: { record_intact: true, policy_unchanged: true },
  why_you_see_this: "You see this because your role can read your organization's evidence.",
}

const show = (explanation: Explanation) => render(<MemoryRouter><ExplanationCard explanation={explanation} /></MemoryRouter>)

describe("the explanation card", () => {
  it("shows an exact decision with its rule, version, identity and integrity", () => {
    show(RECORDED)
    expect(screen.getByText("Exact decision record")).toBeTruthy()
    expect(screen.getByTestId("explanation-reason").textContent).toBe("Blocked because policy v4 does not allow send_email.")
    expect(screen.getByText("permission:send_email")).toBeTruthy()
    expect(screen.getByText(/client certificate verified at the gateway/)).toBeTruthy()
    expect(screen.getByText(/matches the fingerprint/)).toBeTruthy()
    expect(document.body.textContent?.toLowerCase()).not.toContain("confidence")
  })

  it("explains why a step is unavailable, from the viewer's role only, and offers no link", () => {
    show(RECORDED)
    expect(screen.getByText(/Why is this unavailable\?/).parentElement?.textContent).toContain("Your role, Auditor,")
    expect(screen.queryByRole("link", { name: "Open Policies" })).toBeNull()
  })

  it("labels an inferred decision plainly and never claims a record", () => {
    show({ ...RECORDED, basis: "inferred", matched_rule: null,
      policy: { ...RECORDED.policy, basis: "inferred", source: null, unchanged_since_decision: null },
      integrity: { record_intact: null, policy_unchanged: null } })
    expect(screen.getByText("Inferred, not recorded")).toBeTruthy()
    expect(screen.getByText("(inferred from publication time)")).toBeTruthy()
    expect(screen.getByText("Not recorded for this request.")).toBeTruthy()
    expect(screen.queryByText(/matches the fingerprint/)).toBeNull()
  })

  it("warns when a record no longer matches its fingerprint", () => {
    show({ ...RECORDED, integrity: { record_intact: false, policy_unchanged: null } })
    expect(screen.getByText(/Treat it as tampered/)).toBeTruthy()
  })

  it("links the next step when the viewer may take it", () => {
    show({ ...RECORDED, next_step: { text: "Review it in Approvals.", path: "/approvals", available: true } })
    expect(screen.getByRole("link", { name: "Open Approvals" }).getAttribute("href")).toBe("/approvals")
  })
})
