import { useQuery } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import { useAuth } from "../context/AuthContext"
import { adminCall } from "./adminApi"

type NotificationSummary = { unread: number; unread_critical: number; unread_high: number }
type ServiceStatus = { status: string }

// One minute keeps the shell well inside the API's per-client request limits.
const REFRESH = 60_000
// The page's own data loads first; the shell's two signals follow once that burst is over.
export const SHELL_SIGNAL_DELAY = 3_000

export type PostureTone = "ok" | "warning" | "danger" | "unknown"

export interface Posture {
  tone: PostureTone
  title: string
  detail: string
}

/** What the sidebar says about the control plane: only ever a measured state, never a fixed claim. */
export function describePosture(status: string | undefined, failed: boolean): Posture {
  if (failed) return { tone: "unknown", title: "Status unavailable", detail: "The control plane did not answer" }
  switch (status) {
    case undefined: return { tone: "unknown", title: "Checking status", detail: "Asking the control plane" }
    case "OPERATIONAL": return { tone: "ok", title: "Control plane operational", detail: "All service components are up" }
    case "MAINTENANCE": return { tone: "warning", title: "Maintenance in progress", detail: "Some components are in maintenance" }
    case "DEGRADED": return { tone: "warning", title: "Control plane degraded", detail: "Some components need attention" }
    case "MAJOR_OUTAGE": return { tone: "danger", title: "Major outage", detail: "A core component is down" }
    default: return { tone: "unknown", title: "Status unknown", detail: `Reported as ${status.toLowerCase().replace(/_/g, " ")}` }
  }
}

/** The unread count behind the bell and the measured posture behind the sidebar's status line. */
export function useShellSignals(): { unread: number | null; posture: Posture } {
  const { sessionToken } = useAuth()
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const timer = window.setTimeout(() => setReady(true), SHELL_SIGNAL_DELAY)
    return () => window.clearTimeout(timer)
  }, [])
  const summary = useQuery({
    queryKey: ["shell", "notification-summary"],
    queryFn: () => adminCall<NotificationSummary>("/notifications/summary", sessionToken),
    enabled: ready && Boolean(sessionToken),
    refetchInterval: REFRESH,
    retry: false,
  })
  const status = useQuery({
    queryKey: ["shell", "status"],
    queryFn: () => adminCall<ServiceStatus>("/status", sessionToken),
    enabled: ready,
    refetchInterval: REFRESH,
    retry: false,
  })
  return {
    unread: summary.data?.unread ?? null,
    posture: describePosture(status.data?.status, status.isError),
  }
}
