import { describe, expect, it } from "vitest"

import { MAX_FAVOURITES, MAX_RECENT, readPaths, recordRecentPage, toggleFavourite } from "../lib/pageShortcuts"
import { navigationItems } from "../config/navigation"

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial))
  return { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => { values.set(key, value) } }
}

const RECENT = "greyguard_recent_pages"
const FAVOURITES = "greyguard_favourite_pages"

describe("recent pages", () => {
  it("records the newest visit first without duplicates", () => {
    const storage = memoryStorage()
    recordRecentPage("/agents", storage)
    recordRecentPage("/policies", storage)
    recordRecentPage("/agents", storage)
    expect(readPaths(RECENT, storage)).toEqual(["/agents", "/policies"])
  })

  it("stores a detail URL as its list page, never the identifier", () => {
    const storage = memoryStorage()
    recordRecentPage("/agents/agent-secret-id", storage)
    recordRecentPage("/requests/req-123", storage)
    expect(readPaths(RECENT, storage)).toEqual(["/requests", "/agents"])
    expect(storage.getItem(RECENT)).not.toContain("secret")
  })

  it("ignores the Command Center and unknown paths", () => {
    const storage = memoryStorage()
    recordRecentPage("/dashboard", storage)
    recordRecentPage("/not-a-page", storage)
    expect(readPaths(RECENT, storage)).toEqual([])
  })

  it("keeps only the most recent pages", () => {
    const storage = memoryStorage()
    const paths = navigationItems.map((item) => item.path).filter((path) => path !== "/dashboard")
    for (const path of paths) recordRecentPage(path, storage)
    expect(readPaths(RECENT, storage)).toEqual(paths.slice(-MAX_RECENT).reverse())
  })
})

describe("favourites", () => {
  it("toggles a page on and off", () => {
    const storage = memoryStorage()
    expect(toggleFavourite("/approvals", storage)).toBe(true)
    expect(readPaths(FAVOURITES, storage)).toEqual(["/approvals"])
    expect(toggleFavourite("/approvals", storage)).toBe(false)
    expect(readPaths(FAVOURITES, storage)).toEqual([])
  })

  it("refuses paths that are not console pages", () => {
    const storage = memoryStorage()
    expect(toggleFavourite("https://example.com", storage)).toBe(false)
    expect(storage.getItem(FAVOURITES)).toBeNull()
  })

  it("caps the list, dropping the oldest", () => {
    const storage = memoryStorage()
    const paths = navigationItems.map((item) => item.path).slice(0, MAX_FAVOURITES + 2)
    for (const path of paths) toggleFavourite(path, storage)
    expect(readPaths(FAVOURITES, storage)).toEqual(paths.slice(-MAX_FAVOURITES))
  })
})

describe("stored values", () => {
  it("drops tampered or malformed entries", () => {
    expect(readPaths(FAVOURITES, memoryStorage({ [FAVOURITES]: JSON.stringify(["/agents", "javascript:alert(1)", 7, "/agents/x"]) }))).toEqual(["/agents"])
    expect(readPaths(FAVOURITES, memoryStorage({ [FAVOURITES]: "{not json" }))).toEqual([])
    expect(readPaths(FAVOURITES, memoryStorage({ [FAVOURITES]: JSON.stringify({ path: "/agents" }) }))).toEqual([])
  })

  it("treats blocked storage as empty", () => {
    const blocked = { getItem: () => { throw new Error("blocked") }, setItem: () => { throw new Error("blocked") } }
    expect(readPaths(RECENT, blocked)).toEqual([])
    expect(() => recordRecentPage("/agents", blocked)).not.toThrow()
  })
})
