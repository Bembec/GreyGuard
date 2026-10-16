import { describe, expect, it } from "vitest"

import { oldestUpdate } from "../components/navigation/ShellFreshness"

const query = (key: string, updatedAt: number, active = true) => ({
  queryKey: [key],
  isActive: () => active,
  state: { dataUpdatedAt: updatedAt },
}) as unknown as Parameters<typeof oldestUpdate>[0][number]

describe("shell freshness", () => {
  it("reports the oldest data on screen, so a page never looks fresher than its stalest panel", () => {
    expect(oldestUpdate([query("agents", 3_000), query("alerts", 1_000), query("audit", 2_000)])).toBe(1_000)
  })

  it("ignores the shell's own signals, inactive queries and data never loaded", () => {
    expect(oldestUpdate([query("shell", 10), query("agents", 5_000), query("old-page", 20, false), query("loading", 0)])).toBe(5_000)
  })

  it("shows nothing for a page that loads nothing through the query cache", () => {
    expect(oldestUpdate([query("shell", 10)])).toBeUndefined()
    expect(oldestUpdate([])).toBeUndefined()
  })
})
