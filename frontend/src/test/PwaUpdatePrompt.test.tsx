// @vitest-environment jsdom
// virtual:pwa-register only resolves under the real Vite build (via vite-plugin-pwa) -
// vitest.config.ts aliases it to src/test/mocks/virtual-pwa-register.ts, which this file
// drives directly (vi.mock can't intercept a "virtual:" specifier - Vite's own
// import-analysis plugin resolves it first and errors if nothing provides it).
import "@testing-library/jest-dom/vitest"
import { cleanup, render, screen, fireEvent, act } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { PwaUpdatePrompt } from "../components/PwaUpdatePrompt"
import { registerSW } from "./mocks/virtual-pwa-register"

afterEach(cleanup)

describe("PwaUpdatePrompt", () => {
  it("renders nothing until an update or offline-ready callback fires", () => {
    render(<PwaUpdatePrompt />)
    expect(screen.queryByRole("status")).not.toBeInTheDocument()
  })

  it("shows a reload banner on onNeedRefresh and calls the updater on click", async () => {
    const update = vi.fn().mockResolvedValue(undefined)
    registerSW.mockImplementation((options: { onNeedRefresh?: () => void }) => {
      options.onNeedRefresh?.()
      return update
    })
    render(<PwaUpdatePrompt />)
    expect(await screen.findByText(/new GreyGuard build is available/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: /reload now/i }))
    expect(update).toHaveBeenCalledWith(true)
  })

  it("dismisses the offline-ready banner without reloading", async () => {
    registerSW.mockImplementation((options: { onOfflineReady?: () => void }) => {
      options.onOfflineReady?.()
      return vi.fn()
    })
    render(<PwaUpdatePrompt />)
    expect(await screen.findByText(/ready to load offline/i)).toBeInTheDocument()
    act(() => { fireEvent.click(screen.getByRole("button", { name: /dismiss/i })) })
    expect(screen.queryByText(/ready to load offline/i)).not.toBeInTheDocument()
  })
})
