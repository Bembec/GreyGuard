import {
  AlertTriangle,
  BellRing,
  CheckCheck,
  CircleAlert,
  Clock3,
  Filter,
  Inbox,
  RefreshCw,
  Settings2,
  Trash2,
} from "lucide-react"
import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { useToast } from "../context/ToastContext"
import { usePermission } from "../hooks/usePermission"
import "../styles/notifications.css"

export type SecurityNotification = {
  notification_id: string
  source_alert_id: string
  created_at: string
  severity: "HIGH" | "CRITICAL" | string
  title: string
  message: string
  resource_path: string
  is_read: boolean
  read_at: string | null
  read_by: string | null
}

type NotificationList = { notifications: SecurityNotification[]; count: number }
type NotificationSummary = {
  total: number
  unread: number
  unread_critical: number
  unread_high: number
}
type RetentionResponse = {
  policy: { retention_days: number; updated_at: string; updated_by: string }
  history: Array<{ timestamp: string; actor: string; action: string; retention_days: number; deleted_count: number }>
}

export const notificationRetentionOptions = [30, 60, 90, 180, 365, 730]

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api"

export function formatNotificationDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem("greyguard_admin_pin")
  if (!token) throw new Error("Administrator session is missing. Sign in again.")
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Admin-Pin": token, ...options.headers },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error((body as { detail?: string }).detail ?? `Request failed with status ${response.status}.`)
  }
  return body as T
}

export default function NotificationsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { pushToast } = useToast()
  const canManage = usePermission({ permission: "incident:manage" })
  const canManageRetention = usePermission({ permission: "admin:manage" })
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [severity, setSeverity] = useState("ALL")
  const [retentionDays, setRetentionDays] = useState(90)
  const [confirmCleanup, setConfirmCleanup] = useState(false)

  const summary = useQuery({
    queryKey: ["notification-summary"],
    queryFn: () => request<NotificationSummary>("/notifications/summary"),
    refetchInterval: 15_000,
  })
  const notifications = useQuery({
    queryKey: ["notifications", unreadOnly, severity],
    queryFn: () => {
      const query = new URLSearchParams({ limit: "200", unread_only: String(unreadOnly) })
      if (severity !== "ALL") query.set("severity", severity)
      return request<NotificationList>(`/notifications?${query}`)
    },
    refetchInterval: 15_000,
  })
  const retention = useQuery({
    queryKey: ["notification-retention"],
    queryFn: async () => {
      const result = await request<RetentionResponse>("/notifications/retention")
      setRetentionDays(result.policy.retention_days)
      return result
    },
    enabled: canManageRetention,
  })

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
      queryClient.invalidateQueries({ queryKey: ["notification-summary"] }),
    ])
  }
  const markRead = useMutation({
    mutationFn: (id: string) => request(`/notifications/${id}/read`, { method: "PUT" }),
    onSuccess: refresh,
    onError: (error: Error) => pushToast({ tone: "error", title: "Could not review notification", message: error.message }),
  })
  const markAll = useMutation({
    mutationFn: () => request("/notifications/read-all", { method: "PUT" }),
    onSuccess: async () => {
      await refresh()
      pushToast({ tone: "success", title: "Notifications reviewed", message: "All unread security notifications were marked as reviewed." })
    },
    onError: (error: Error) => pushToast({ tone: "error", title: "Could not review notifications", message: error.message }),
  })
  const saveRetention = useMutation({
    mutationFn: () => request("/notifications/retention", { method: "PUT", body: JSON.stringify({ retention_days: retentionDays }) }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["notification-retention"] })
      pushToast({ tone: "success", title: "Retention policy updated", message: `Notifications will be retained for ${retentionDays} days.` })
    },
    onError: (error: Error) => pushToast({ tone: "error", title: "Could not update retention", message: error.message }),
  })
  const cleanup = useMutation({
    mutationFn: () => request<{ deleted: number; retention_days: number }>("/notifications/retention/cleanup", { method: "POST" }),
    onSuccess: async (result) => {
      setConfirmCleanup(false)
      await Promise.all([refresh(), queryClient.invalidateQueries({ queryKey: ["notification-retention"] })])
      pushToast({ tone: "success", title: "Retention cleanup completed", message: `${result.deleted} expired notification${result.deleted === 1 ? " was" : "s were"} removed.` })
    },
    onError: (error: Error) => { setConfirmCleanup(false); pushToast({ tone: "error", title: "Cleanup failed", message: error.message }) },
  })

  const entries = useMemo(() => notifications.data?.notifications ?? [], [notifications.data])

  const openIncident = async (notification: SecurityNotification) => {
    if (!notification.is_read && canManage) await markRead.mutateAsync(notification.notification_id)
    navigate(notification.resource_path)
  }

  return <main className="notifications-page">
    <section className="notifications-hero">
      <div>
        <p><BellRing size={15} /> Security awareness</p>
        <h1>Notification Center</h1>
        <span>Prioritized security signals connected directly to investigation evidence.</span>
      </div>
      <div className="notifications-actions">
        {canManage && <button type="button" onClick={() => markAll.mutate()} disabled={!summary.data?.unread || markAll.isPending}>
          <CheckCheck size={17} /> Mark all reviewed
        </button>}
        <button type="button" onClick={() => void refresh()}><RefreshCw size={17} /> Refresh</button>
      </div>
    </section>

    <section className="notifications-metrics" aria-label="Notification summary">
      <article><Inbox /><div><strong>{summary.data?.unread ?? 0}</strong><span>Unread</span></div></article>
      <article className="critical"><AlertTriangle /><div><strong>{summary.data?.unread_critical ?? 0}</strong><span>Critical unread</span></div></article>
      <article className="high"><CircleAlert /><div><strong>{summary.data?.unread_high ?? 0}</strong><span>High unread</span></div></article>
      <article><BellRing /><div><strong>{summary.data?.total ?? 0}</strong><span>Total history</span></div></article>
    </section>

    {canManageRetention && <section className="notification-retention">
      <div><span><Settings2 size={18}/></span><div><strong>Notification retention</strong><small>Expired records are removed automatically while cleanup actions remain auditable.</small></div></div>
      <label>Retention period<select value={retentionDays} onChange={(event) => setRetentionDays(Number(event.target.value))}>{notificationRetentionOptions.map((days) => <option value={days} key={days}>{days} days</option>)}</select></label>
      <button type="button" onClick={() => saveRetention.mutate()} disabled={saveRetention.isPending || retentionDays === retention.data?.policy.retention_days}>Save policy</button>
      <button className="retention-cleanup" type="button" onClick={() => setConfirmCleanup(true)}><Trash2 size={16}/> Clean up now</button>
    </section>}

    <section className="notifications-panel">
      <header>
        <div><Filter size={17} /><strong>Inbox filters</strong></div>
        <label><input type="checkbox" checked={unreadOnly} onChange={(event) => setUnreadOnly(event.target.checked)} /> Unread only</label>
        <select value={severity} onChange={(event) => setSeverity(event.target.value)} aria-label="Filter severity">
          <option value="ALL">All severities</option><option value="CRITICAL">Critical</option><option value="HIGH">High</option>
        </select>
      </header>

      {notifications.isLoading && <LoadingState label="Loading security notifications" rows={4}/>}
      {notifications.isError && <ErrorState message={notifications.error.message} onRetry={() => void notifications.refetch()}/>}
      {!notifications.isLoading && !notifications.isError && entries.length === 0 && <EmptyState icon={<Inbox size={30}/>} title="Inbox clear" description="No notifications match these filters."/>}

      <div className="notifications-list">
        {entries.map((item) => <button type="button" key={item.notification_id} className={`notification-row ${item.is_read ? "read" : "unread"}`} onClick={() => void openIncident(item)}>
          <span className={`notification-severity ${item.severity.toLowerCase()}`}>{item.severity === "CRITICAL" ? <AlertTriangle size={18} /> : <CircleAlert size={18} />}</span>
          <span className="notification-copy"><strong>{item.title}</strong><small>{item.message}</small></span>
          <span className="notification-meta"><span className="notification-status">{item.is_read ? "Reviewed" : "New"}</span><small><Clock3 size={13} /> {formatNotificationDate(item.created_at)}</small></span>
        </button>)}
      </div>
    </section>
    {!canManage && <p className="notifications-readonly">Auditor access is read-only. Security Analysts and Platform Administrators can acknowledge notifications.</p>}
    <ConfirmDialog open={confirmCleanup} title="Remove expired notifications?" description={`Notifications older than ${retentionDays} days will be permanently removed. Retention evidence will be preserved.`} confirmLabel="Run cleanup" busy={cleanup.isPending} onCancel={() => setConfirmCleanup(false)} onConfirm={() => cleanup.mutate()}/>
  </main>
}
