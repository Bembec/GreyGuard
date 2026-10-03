import {
  AlertTriangle,
  BellRing,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clock3,
  Filter,
  RefreshCw,
  Search,
  ShieldAlert,
  UserRound,
  X,
} from "lucide-react"
import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { useToast } from "../context/ToastContext"
import "../styles/incidents.css"

export type AlertStatus =
  | "OPEN"
  | "ACKNOWLEDGED"
  | "INVESTIGATING"
  | "RESOLVED"
  | "DISMISSED"

type AlertNote = {
  id: number
  timestamp: string
  actor: string
  note: string
}

export type SecurityAlert = {
  alert_id: string
  source_event_id: string
  event_type: string
  severity: "HIGH" | "CRITICAL" | string
  status: AlertStatus
  title: string
  summary: string
  agent_name: string | null
  action: string | null
  outcome: string | null
  request_id: string | null
  assigned_to: string | null
  created_at: string
  updated_at: string
  resolved_at: string | null
  evidence: Record<string, unknown>
  notes: AlertNote[]
}

type AlertListResponse = {
  alerts: SecurityAlert[]
  count: number
  filters: Record<string, unknown>
}

type AlertSummary = {
  total: number
  open: number
  active_investigations: number
  closed: number
  critical_open: number
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api"

export const incidentStatuses: AlertStatus[] = [
  "OPEN",
  "ACKNOWLEDGED",
  "INVESTIGATING",
  "RESOLVED",
  "DISMISSED",
]

export function formatIncidentStatus(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(
    /(^|\s)\S/g,
    (character) => character.toUpperCase(),
  )
}

export function isActiveIncident(status: AlertStatus) {
  return !["RESOLVED", "DISMISSED"].includes(status)
}

function adminHeaders() {
  const pin = sessionStorage.getItem("greyguard_admin_pin")
  if (!pin) throw new Error("Administrator session is missing. Sign in again.")
  return { "Content-Type": "application/json", "X-Admin-Pin": pin }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { ...adminHeaders(), ...options.headers },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = (body as { detail?: string }).detail
    throw new Error(detail ?? `Request failed with status ${response.status}.`)
  }
  return body as T
}

function formatDate(value: string | null) {
  if (!value) return "Not recorded"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date)
}

export default function IncidentCenterPage() {
  const queryClient = useQueryClient()
  const { pushToast } = useToast()
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("ALL")
  const [severity, setSeverity] = useState("ALL")
  const [selected, setSelected] = useState<SecurityAlert | null>(null)
  const [nextStatus, setNextStatus] = useState<AlertStatus>("INVESTIGATING")
  const [assignee, setAssignee] = useState("")
  const [note, setNote] = useState("")

  const summary = useQuery({
    queryKey: ["alert-summary"],
    queryFn: () => request<AlertSummary>("/alerts/summary"),
    refetchInterval: 15_000,
  })
  const alerts = useQuery({
    queryKey: ["alerts", status, severity],
    queryFn: () => {
      const parameters = new URLSearchParams({ limit: "200" })
      if (status !== "ALL") parameters.set("status", status)
      if (severity !== "ALL") parameters.set("severity", severity)
      return request<AlertListResponse>(`/alerts?${parameters}`)
    },
    refetchInterval: 15_000,
  })

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["alerts"] }),
      queryClient.invalidateQueries({ queryKey: ["alert-summary"] }),
    ])
  }

  const update = useMutation({
    mutationFn: () => request<SecurityAlert>(`/alerts/${selected?.alert_id}`, {
      method: "PUT",
      body: JSON.stringify({
        status: nextStatus,
        assigned_to: assignee.trim() || null,
        note: note.trim() || null,
      }),
    }),
    onSuccess: async (updated) => {
      setSelected(updated)
      setNote("")
      pushToast({ tone: "success", title: "Incident updated", message: "The change was recorded in the evidence trail." })
      await refresh()
    },
    onError: (error: Error) => pushToast({ tone: "error", title: "Could not update incident", message: error.message }),
  })

  const visibleAlerts = useMemo(() => {
    const needle = search.trim().toLowerCase()
    const entries = alerts.data?.alerts ?? []
    if (!needle) return entries
    return entries.filter((entry) => [
      entry.alert_id,
      entry.title,
      entry.summary,
      entry.agent_name,
      entry.action,
      entry.outcome,
      entry.assigned_to,
    ].some((value) => String(value ?? "").toLowerCase().includes(needle)))
  }, [alerts.data, search])

  const openDetails = (alert: SecurityAlert) => {
    setSelected(alert)
    setNextStatus(alert.status)
    setAssignee(alert.assigned_to ?? "")
    setNote("")
  }

  return (
    <main className="incident-page">
      <section className="incident-hero">
        <div>
          <p className="incident-eyebrow"><ShieldAlert size={15} /> Response operations</p>
          <h1>Incident Center</h1>
          <p>Turn high-risk GreyGuard evidence into owned, reviewable security investigations.</p>
        </div>
        <button className="incident-refresh" type="button" onClick={() => void refresh()}>
          <RefreshCw size={17} /> Refresh evidence
        </button>
      </section>

      <section className="incident-metrics" aria-label="Incident summary">
        {[
          ["Open alerts", summary.data?.open ?? 0, BellRing, "amber"],
          ["Investigating", summary.data?.active_investigations ?? 0, CircleDot, "blue"],
          ["Critical open", summary.data?.critical_open ?? 0, AlertTriangle, "red"],
          ["Closed", summary.data?.closed ?? 0, CheckCircle2, "green"],
        ].map(([label, value, Icon, tone]) => {
          const MetricIcon = Icon as typeof BellRing
          return <article className={`incident-metric incident-metric--${tone}`} key={String(label)}>
            <span><MetricIcon size={19} /></span>
            <div><strong>{String(value)}</strong><small>{String(label)}</small></div>
          </article>
        })}
      </section>

      <section className="incident-panel">
        <header className="incident-toolbar">
          <label className="incident-search">
            <Search size={17} />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search alerts, agents or actions" />
          </label>
          <label><Filter size={16} /><select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="ALL">All statuses</option>
            {incidentStatuses.map((item) => <option key={item} value={item}>{formatIncidentStatus(item)}</option>)}
          </select></label>
          <label><select value={severity} onChange={(event) => setSeverity(event.target.value)}>
            <option value="ALL">All severities</option><option value="CRITICAL">Critical</option><option value="HIGH">High</option>
          </select></label>
        </header>

        {alerts.isLoading && <LoadingState label="Loading incident evidence" rows={4}/>} 
        {alerts.isError && <ErrorState message={alerts.error.message} onRetry={() => void alerts.refetch()}/>} 
        {!alerts.isLoading && !alerts.isError && visibleAlerts.length === 0 && <EmptyState title="No matching incidents" description="No alerts match the current filters."/>}

        <div className="incident-list">
          {visibleAlerts.map((alert) => <button type="button" className="incident-row" key={alert.alert_id} onClick={() => openDetails(alert)}>
            <span className={`incident-severity incident-severity--${alert.severity.toLowerCase()}`}>{alert.severity}</span>
            <span className="incident-row__main"><strong>{alert.title}</strong><small>{alert.summary}</small></span>
            <span className="incident-row__meta"><strong>{formatIncidentStatus(alert.status)}</strong><small>{alert.agent_name ?? "System event"}</small></span>
            <span className="incident-row__time"><Clock3 size={14} />{formatDate(alert.created_at)}</span>
            <ChevronRight size={18} />
          </button>)}
        </div>
      </section>

      {selected && <div className="incident-modal" role="dialog" aria-modal="true" aria-label="Incident details">
        <button className="incident-modal__backdrop" type="button" onClick={() => setSelected(null)} aria-label="Close incident" />
        <section className="incident-drawer">
          <header><div><span className={`incident-severity incident-severity--${selected.severity.toLowerCase()}`}>{selected.severity}</span><h2>{selected.title}</h2><p>{selected.alert_id}</p></div><button type="button" onClick={() => setSelected(null)} aria-label="Close"><X size={20} /></button></header>
          <div className="incident-drawer__body">
            <article className="incident-evidence"><h3>Evidence summary</h3><p>{selected.summary}</p><dl>
              <div><dt>Agent</dt><dd>{selected.agent_name ?? "System"}</dd></div><div><dt>Action</dt><dd>{selected.action ?? "—"}</dd></div><div><dt>Outcome</dt><dd>{selected.outcome ?? "—"}</dd></div><div><dt>Source event</dt><dd>{selected.source_event_id}</dd></div>
            </dl></article>
            <article className="incident-workflow"><h3>Response workflow</h3>
              <label>Status<select value={nextStatus} onChange={(event) => setNextStatus(event.target.value as AlertStatus)}>{incidentStatuses.map((item) => <option key={item} value={item}>{formatIncidentStatus(item)}</option>)}</select></label>
              <label>Assigned investigator<div className="incident-input"><UserRound size={16} /><input value={assignee} onChange={(event) => setAssignee(event.target.value)} placeholder="e.g. security-team" /></div></label>
              <label>Investigation note<textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Record the reason, findings or response decision." rows={4} /></label>
              <button type="button" disabled={update.isPending} onClick={() => update.mutate()}>{update.isPending ? "Saving…" : "Save incident update"}</button>
            </article>
            <article className="incident-notes"><h3>Investigation history</h3>{selected.notes.length === 0 ? <p>No notes recorded yet.</p> : selected.notes.map((entry) => <div key={entry.id}><span>{entry.actor} · {formatDate(entry.timestamp)}</span><p>{entry.note}</p></div>)}</article>
          </div>
        </section>
      </div>}
    </main>
  )
}
