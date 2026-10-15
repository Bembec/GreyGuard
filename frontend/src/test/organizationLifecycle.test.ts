import { describe, expect, it } from "vitest"

import { checklistProgress, exportFilename } from "../components/OrganizationLifecyclePanel"

describe("organization lifecycle panel", () => {
  it("counts completed checklist items", () => {
    expect(checklistProgress([
      { key: "a", label: "A", done: true },
      { key: "b", label: "B", done: false },
      { key: "c", label: "C", done: true },
    ])).toBe("2 of 3 complete")
  })
  it("names the export after the org and date, with nothing unsafe in the filename", () => {
    expect(exportFilename("org_abc/../x", new Date("2026-10-15T12:00:00Z"))).toBe("greyguard-org_abcx-export-2026-10-15.json")
  })
})
