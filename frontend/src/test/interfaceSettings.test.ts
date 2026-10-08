// @vitest-environment jsdom
// Touches localStorage and document.documentElement, neither of which exist under this
// project's default "node" vitest environment (see vitest.config.ts).
import { afterEach, describe, expect, it } from "vitest"
import { applySettings, defaultSettings, loadSettings, storageKey } from "../lib/interfaceSettings"

afterEach(() => {
  localStorage.removeItem(storageKey)
  delete document.documentElement.dataset.motion
  delete document.documentElement.dataset.density
  delete document.documentElement.dataset.accent
})

describe("loadSettings", () => {
  it("falls back to defaults with nothing stored", () => {
    expect(loadSettings()).toEqual(defaultSettings)
  })

  it("merges a stored partial preference over the defaults", () => {
    localStorage.setItem(storageKey, JSON.stringify({ reducedMotion: true }))
    expect(loadSettings()).toEqual({ ...defaultSettings, reducedMotion: true })
  })

  it("falls back to defaults on corrupt stored JSON rather than throwing", () => {
    localStorage.setItem(storageKey, "{not json")
    expect(loadSettings()).toEqual(defaultSettings)
  })
})

describe("applySettings", () => {
  it("sets data-motion to reduced only when the preference is on", () => {
    applySettings({ ...defaultSettings, reducedMotion: true })
    expect(document.documentElement.dataset.motion).toBe("reduced")
    applySettings({ ...defaultSettings, reducedMotion: false })
    expect(document.documentElement.dataset.motion).toBe("full")
  })

  it("sets data-density and data-accent from the preference", () => {
    applySettings({ ...defaultSettings, interfaceDensity: "compact", accentChoice: "violet" })
    expect(document.documentElement.dataset.density).toBe("compact")
    expect(document.documentElement.dataset.accent).toBe("violet")
  })
})
