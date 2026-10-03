import { describe, expect, it } from "vitest"
import { readRecentSearches, saveRecentSearch } from "../components/GlobalSearchDialog"

function memoryStorage(initial: string | null = null) {
  let value = initial
  return { getItem: () => value, setItem: (_key: string, next: string) => { value = next } }
}

describe("Global search history", () => {
  it("stores the newest unique searches first", () => {
    const storage = memoryStorage()
    saveRecentSearch("billing-agent", storage)
    saveRecentSearch("request 42", storage)
    saveRecentSearch("BILLING-AGENT", storage)
    expect(readRecentSearches(storage)).toEqual(["BILLING-AGENT", "request 42"])
  })

  it("ignores invalid stored history", () => {
    expect(readRecentSearches(memoryStorage("not-json"))).toEqual([])
  })
})
