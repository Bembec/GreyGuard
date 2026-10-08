// @vitest-environment jsdom
// This suite renders real components to exercise focus/keyboard behavior, unlike the rest
// of this project's tests (environment: "node" in vitest.config.ts) - scoped to this file
// only via the pragma above rather than changing the project-wide default. jest-dom's
// matchers (toHaveFocus, etc.) aren't globally registered either, so import them here too.
import "@testing-library/jest-dom/vitest"
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react"
import { useRef, useState } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { useDismissableLayer } from "../hooks/useDismissableLayer"

// This project's vitest config does not register @testing-library/react's auto-cleanup
// (no setupFiles, isolate: false), so each render must be torn down explicitly or
// subsequent tests in this file see duplicate elements from prior renders.
afterEach(cleanup)

function Harness({ trapFocus = false, startOpen = true }: { trapFocus?: boolean; startOpen?: boolean }) {
  const [open, setOpen] = useState(startOpen)
  const onClose = vi.fn(() => setOpen(false))
  const firstRef = useRef<HTMLButtonElement>(null)
  const containerRef = useDismissableLayer<HTMLDivElement>({ open, onClose, trapFocus, initialFocusRef: firstRef })
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>outside-trigger</button>
      {open && (
        <div ref={containerRef} data-testid="layer">
          <button type="button" ref={firstRef}>first</button>
          <button type="button">last</button>
        </div>
      )}
    </div>
  )
}

describe("useDismissableLayer", () => {
  it("moves focus to the initial focus target on open", async () => {
    render(<Harness />)
    // The hook defers the initial focus move by one tick (window.setTimeout(..., 0)), the
    // same defensive pattern GlobalSearchDialog used before this hook was extracted from it.
    await waitFor(() => expect(screen.getByText("first")).toHaveFocus())
  })

  it("calls onClose on Escape", () => {
    render(<Harness />)
    fireEvent.keyDown(document, { key: "Escape" })
    expect(screen.queryByTestId("layer")).not.toBeInTheDocument()
  })

  it("restores focus to the element that was focused right before the layer opened", async () => {
    render(<Harness startOpen={false} />)
    const trigger = screen.getByText("outside-trigger")
    trigger.focus()
    fireEvent.click(trigger) // opens the layer; "previous" is captured as `trigger`
    await waitFor(() => expect(screen.getByText("first")).toHaveFocus())
    fireEvent.keyDown(document, { key: "Escape" })
    expect(trigger).toHaveFocus()
  })

  it("wraps Tab from the last to the first focusable element when trapFocus is set", () => {
    render(<Harness trapFocus />)
    screen.getByText("last").focus()
    fireEvent.keyDown(document, { key: "Tab" })
    expect(screen.getByText("first")).toHaveFocus()
  })

  it("wraps Shift+Tab from the first to the last focusable element when trapFocus is set", () => {
    render(<Harness trapFocus />)
    screen.getByText("first").focus()
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true })
    expect(screen.getByText("last")).toHaveFocus()
  })

  it("does not trap Tab when trapFocus is false", () => {
    render(<Harness trapFocus={false} />)
    screen.getByText("last").focus()
    fireEvent.keyDown(document, { key: "Tab" })
    // No wrap applied - focus stays wherever the browser's default Tab order would leave it,
    // which in jsdom (no real layout) means focus is simply not forced back to "first".
    expect(screen.getByText("first")).not.toHaveFocus()
  })
})
