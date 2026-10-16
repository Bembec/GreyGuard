// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter, useLocation } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { SavedViewsMenu } from "../components/page/SavedViewsMenu"
import { AuthContext, type Administrator } from "../context/AuthContext"
import {
  MAX_VIEWS_PER_PAGE,
  addView,
  parseViews,
  removeView,
  renameView,
  viewQuery,
  viewsStorageKey,
  type SavedView,
} from "../lib/savedViews"

const KEYS = ["q", "decision", "range", "since", "until"] as const
const NOW = "2026-10-16T12:00:00.000Z"
const view = (id: string, name: string, query = "decision=BLOCK", page = "tool-requests"): SavedView =>
  ({ id, name, query, page, scope: "personal", createdAt: NOW })

describe("the view format", () => {
  it("keeps only the page's own keys, in a stable order", () => {
    expect(viewQuery(new URLSearchParams("register=1&range=7d&decision=BLOCK&q="), KEYS)).toBe("decision=BLOCK&range=7d")
    expect(viewQuery(new URLSearchParams("range=7d&decision=BLOCK"), KEYS)).toBe(viewQuery(new URLSearchParams("decision=BLOCK&range=7d"), KEYS))
  })

  it("drops malformed, foreign and duplicate entries and anything over the limit", () => {
    const stored = [
      view("a", "Blocked"),
      { ...view("b", "Other page"), page: "incidents" },
      { ...view("c", "Shared"), scope: "team" },
      { id: "d", name: "", query: "", page: "tool-requests", scope: "personal", createdAt: NOW },
      view("a", "Duplicate id"),
      "nonsense",
      ...Array.from({ length: 30 }, (_, index) => view(`v${index}`, `View ${index}`)),
    ]
    const views = parseViews(JSON.stringify(stored), "tool-requests", KEYS)
    expect(views[0].name).toBe("Blocked")
    expect(views.map((item) => item.id)).not.toContain("b")
    expect(views.map((item) => item.id)).not.toContain("c")
    expect(views.map((item) => item.id)).not.toContain("d")
    expect(views).toHaveLength(MAX_VIEWS_PER_PAGE)
  })

  it("strips keys a stored view should never carry", () => {
    const [stored] = parseViews(JSON.stringify([view("a", "Sneaky", "decision=BLOCK&register=1&org_id=org_other")]), "tool-requests", KEYS)
    expect(stored.query).toBe("decision=BLOCK")
  })

  it("survives corrupt storage", () => {
    expect(parseViews("{not json", "tool-requests", KEYS)).toEqual([])
    expect(parseViews(JSON.stringify({ views: [] }), "tool-requests", KEYS)).toEqual([])
    expect(parseViews(null, "tool-requests", KEYS)).toEqual([])
  })

  it("is keyed by account and page", () => {
    expect(viewsStorageKey("adm_1", "incidents")).toBe("greyguard_saved_views:adm_1:incidents")
  })
})

describe("changing views", () => {
  it("adds, and replaces a view saved again under the same name", () => {
    const first = addView([], "Blocked", "decision=BLOCK", "tool-requests", "a", NOW)
    expect(first.ok).toBe(true)
    if (!first.ok) return
    const again = addView(first.views, "  blocked ", "decision=BLOCK&range=7d", "tool-requests", "b", NOW)
    expect(again.ok && again.views).toEqual([{ ...view("a", "blocked", "decision=BLOCK&range=7d") }])
  })

  it("refuses an empty or over-long name and a 21st view", () => {
    expect(addView([], "  ", "", "tool-requests", "a", NOW)).toMatchObject({ ok: false })
    expect(addView([], "x".repeat(61), "", "tool-requests", "a", NOW)).toMatchObject({ ok: false })
    const full = Array.from({ length: MAX_VIEWS_PER_PAGE }, (_, index) => view(`v${index}`, `View ${index}`))
    expect(addView(full, "One more", "", "tool-requests", "z", NOW)).toMatchObject({ ok: false, problem: expect.stringMatching(/Delete one/) })
    // Replacing an existing name is still allowed when full.
    expect(addView(full, "View 3", "q=x", "tool-requests", "z", NOW)).toMatchObject({ ok: true })
  })

  it("renames without colliding, and removes", () => {
    const views = [view("a", "One"), view("b", "Two")]
    expect(renameView(views, "a", "two")).toMatchObject({ ok: false })
    const renamed = renameView(views, "a", "First")
    expect(renamed.ok && renamed.views[0].name).toBe("First")
    expect(removeView(views, "a")).toEqual([view("b", "Two")])
  })
})

const administrator: Administrator = { admin_id: "adm_1", email: "a@example.com", display_name: "A", role: "AUDITOR", permissions: ["read"] }

function Location() {
  return <output data-testid="url">{useLocation().search}</output>
}

function renderMenu(url: string, who: Administrator | null = administrator) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <AuthContext.Provider value={{
        sessionToken: "gga_test", administrator: who, isAuthenticated: true, isResumingSession: false, isWaitingForControlPlane: false,
        login: async () => {}, completeSso: async () => {}, completeSetup: async () => {}, switchActiveOrg: async () => {}, logout: async () => {},
      }}>
        <SavedViewsMenu page="tool-requests" keys={KEYS} />
        <Location />
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

describe("the views menu", () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => { cleanup(); vi.restoreAllMocks() })

  it("saves the current filters, then applies them, leaving other URL keys alone", () => {
    renderMenu("/requests?decision=BLOCK&range=7d&register=1")
    fireEvent.click(screen.getByRole("button", { name: /Views/ }))
    fireEvent.change(screen.getByLabelText("Save the current filters as"), { target: { value: "Blocked this week" } })
    fireEvent.click(screen.getByRole("button", { name: "Save" }))
    const stored = JSON.parse(localStorage.getItem("greyguard_saved_views:adm_1:tool-requests") ?? "[]")
    expect(stored).toHaveLength(1)
    expect(stored[0]).toMatchObject({ name: "Blocked this week", query: "decision=BLOCK&range=7d", scope: "personal" })
    // The trigger names the view that matches the current filters.
    expect(screen.getByRole("button", { name: /Blocked this week/, expanded: true })).toBeTruthy()
    cleanup()

    renderMenu("/requests?decision=ALLOW&q=abc&register=1")
    fireEvent.click(screen.getByRole("button", { name: /Views/ }))
    fireEvent.click(screen.getByRole("button", { name: "Blocked this week" }))
    const search = new URLSearchParams(screen.getByTestId("url").textContent ?? "")
    expect(search.get("decision")).toBe("BLOCK")
    expect(search.get("range")).toBe("7d")
    expect(search.get("q")).toBeNull()
    expect(search.get("register")).toBe("1")
  })

  it("keeps each account's views apart", () => {
    localStorage.setItem(viewsStorageKey("adm_other", "tool-requests"), JSON.stringify([view("x", "Theirs")]))
    renderMenu("/requests")
    fireEvent.click(screen.getByRole("button", { name: /Views/ }))
    expect(screen.queryByText("Theirs")).toBeNull()
    expect(screen.getByText(/No saved views yet/)).toBeTruthy()
  })

  it("works for the visit when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked") })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked") })
    renderMenu("/requests?decision=BLOCK")
    fireEvent.click(screen.getByRole("button", { name: /Views/ }))
    fireEvent.change(screen.getByLabelText("Save the current filters as"), { target: { value: "Temp" } })
    fireEvent.click(screen.getByRole("button", { name: "Save" }))
    // Listed, and named on the trigger as the view matching the current filters.
    expect(screen.getAllByRole("button", { name: "Temp" })).toHaveLength(2)
  })

  it("says plainly where views are kept", () => {
    renderMenu("/requests")
    fireEvent.click(screen.getByRole("button", { name: /Views/ }))
    expect(screen.getByText(/Saved in this browser, for your account only/)).toBeTruthy()
  })
})
