import { describe, expect, it } from "vitest"
import { formatNotificationDate, notificationRetentionOptions } from "../pages/NotificationsPage"

describe("Notification Center", () => {
  it("formats a valid security timestamp", () => {
    expect(formatNotificationDate("2026-10-02T12:00:00Z")).not.toBe("2026-10-02T12:00:00Z")
  })

  it("preserves an invalid timestamp for evidence visibility", () => {
    expect(formatNotificationDate("unknown")).toBe("unknown")
  })

  it("offers bounded retention periods", () => {
    expect(notificationRetentionOptions).toEqual([30, 60, 90, 180, 365, 730])
  })
})
