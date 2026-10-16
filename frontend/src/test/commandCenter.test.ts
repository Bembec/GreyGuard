import { describe, expect, it } from "vitest"

import {
  PANEL_ORDER,
  PRESETS,
  defaultPresetFor,
  parseCustomization,
  presetsFor,
  resolveLayout,
  togglePanel,
  type Customization,
} from "../config/commandCenter"
import type { Administrator } from "../context/AuthContext"

const base = { admin_id: "a", email: "a@example.com", display_name: "A", permissions: [] as string[], install_operator: false }
const admin = { ...base, role: "PLATFORM_ADMIN", permissions: ["read", "incident:manage", "approval:manage", "identity:manage"], governance_role: "OWNER" } as Administrator
const analyst = { ...base, role: "SECURITY_ANALYST", permissions: ["read", "incident:manage", "approval:manage"], governance_role: "MEMBER" } as Administrator
const auditor = { ...base, role: "AUDITOR", permissions: ["read"], governance_role: "MEMBER" } as Administrator
const billingAuditor = { ...auditor, governance_role: "BILLING_ADMIN" } as Administrator
const none: Customization = { pinned: [], hidden: [] }

const ids = (administrator: Administrator) => presetsFor(administrator).map((preset) => preset.id)

describe("command center presets", () => {
  it("defines the six v3 presets, each with two to five KPIs and at least one panel", () => {
    expect(PRESETS.map((preset) => preset.label)).toEqual([
      "Platform Administrator", "Security Analyst", "Approver", "Auditor", "Organization Owner", "Billing Administrator",
    ])
    for (const preset of PRESETS) {
      expect(preset.kpis.length, preset.id).toBeLessThanOrEqual(5)
      expect(preset.panels.length, preset.id).toBeGreaterThan(0)
      for (const panel of preset.panels) expect(PANEL_ORDER).toContain(panel)
    }
  })

  it("starts each person on their operational role's view", () => {
    expect(defaultPresetFor(admin).id).toBe("platform-admin")
    expect(defaultPresetFor(analyst).id).toBe("security-analyst")
    expect(defaultPresetFor(auditor).id).toBe("auditor")
    expect(defaultPresetFor(null).id).toBe("auditor")
  })

  it("offers only the views a person's roles allow", () => {
    expect(ids(admin)).toEqual(["platform-admin", "security-analyst", "approver", "auditor", "owner", "billing"])
    expect(ids(analyst)).toEqual(["security-analyst", "approver", "auditor"])
    expect(ids(auditor)).toEqual(["auditor"])
    expect(ids(billingAuditor)).toEqual(["auditor", "billing"])
    expect(presetsFor(null)).toEqual([])
  })

  it("falls back to the default when a stored view is no longer allowed", () => {
    expect(resolveLayout(auditor, { ...none, preset: "platform-admin" }).preset.id).toBe("auditor")
    expect(resolveLayout(analyst, { ...none, preset: "approver" }).preset.id).toBe("approver")
  })
})

describe("pinning", () => {
  it("adds pins after the preset's panels and drops hidden ones", () => {
    const layout = resolveLayout(auditor, { pinned: ["plan", "evidence"], hidden: ["risk"] })
    expect(layout.panels).toEqual(["evidence", "reports", "readiness", "plan"])
  })

  it("keeps a customization minimal when a panel is shown or hidden again", () => {
    const preset = defaultPresetFor(auditor)
    let custom = togglePanel(none, preset, "plan", true)
    expect(custom).toEqual({ pinned: ["plan"], hidden: [] })
    custom = togglePanel(custom, preset, "plan", false)
    expect(custom).toEqual({ pinned: [], hidden: [] })
    custom = togglePanel(custom, preset, "risk", false)
    expect(custom).toEqual({ pinned: [], hidden: ["risk"] })
    custom = togglePanel(custom, preset, "risk", true)
    expect(custom).toEqual({ pinned: [], hidden: [] })
  })

  it("ignores tampered or malformed stored values", () => {
    expect(parseCustomization('{"preset":"root","pinned":["plan","<script>",3,"plan"],"hidden":"risk"}')).toEqual({ preset: undefined, pinned: ["plan"], hidden: [] })
    expect(parseCustomization("{not json")).toEqual(none)
    expect(parseCustomization(null)).toEqual(none)
  })
})
