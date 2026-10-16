import { useQuery } from "@tanstack/react-query"
import { Plus, RadioTower, RefreshCw, Send, ShieldCheck } from "lucide-react"
import { useMemo, useState } from "react"
import { Navigate } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { ArchiveDestinationControl, destinationArchiveState } from "../components/ArchiveDestinationControl"
import { DataTable, type Column } from "../components/page/DataTable"
import { FilterBar } from "../components/page/FilterBar"
import { Guidance } from "../components/page/Guidance"
import { PageHeader } from "../components/page/PageHeader"
import { Panel } from "../components/page/Panel"
import { StatCard, StatGrid } from "../components/page/StatCard"
import { StatusBadge } from "../components/page/StatusBadge"
import { relativeTime } from "../components/page/timeFormat"
import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { adminCall } from "../lib/adminApi"

type Destination = { destination_id: string; name: string; destination_type: string; endpoint: string; enabled: boolean; minimization_profile: string; rate_limit_per_minute: number; max_attempts: number; last_success_at: string | null; last_failure_at: string | null; last_error: string | null; credentials_stored: boolean; archived_at?: string | null }
type ExportRecord = { export_id: string; destination_id: string; created_at: string; status: string; attempts: number; event_type: string; delivered_at: string | null; last_error: string | null }
type ExportControl = { destinations: Destination[]; destination_types: string[]; minimization_profiles: string[]; summary: { counts: Record<string, number>; recent: ExportRecord[]; raw_secrets_exposed: boolean } }

export const destinationHealth = (item: Destination) => destinationArchiveState(item.archived_at) ?? (item.last_error ? "DEGRADED" : item.last_success_at ? "HEALTHY" : item.enabled ? "AWAITING DELIVERY" : "DISABLED")

const HEALTH_TONE = { ARCHIVED: "neutral", DEGRADED: "danger", HEALTHY: "success", "AWAITING DELIVERY": "warning", DISABLED: "neutral" } as const

export default function SecurityExportsPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const control = useQuery({ queryKey: ["security-exports"], queryFn: () => adminCall<ExportControl>("/security-exports", sessionToken), enabled: Boolean(sessionToken) && administrator?.role === "PLATFORM_ADMIN" })
  const [name, setName] = useState("")
  const [type, setType] = useState("SIGNED_WEBHOOK")
  const [endpoint, setEndpoint] = useState("")
  const [profile, setProfile] = useState("STANDARD")
  const [keyReference, setKeyReference] = useState("")
  const [filter, setFilter] = useState("ALL")
  const [busy, setBusy] = useState(false)

  const destinations = useMemo(() => control.data?.destinations ?? [], [control.data])
  const recent = control.data?.summary.recent ?? []
  const counts = control.data?.summary.counts ?? {}
  const names = new Map(destinations.map((item) => [item.destination_id, item.name]))
  const visible = destinations.filter((item) => filter === "ALL" || (filter === "ARCHIVED") === Boolean(item.archived_at))

  if (administrator?.role !== "PLATFORM_ADMIN") return <Navigate to="/dashboard" replace />

  // The same request body the backend has always received: new destinations start disabled.
  const save = async () => {
    setBusy(true)
    try {
      await adminCall("/security-exports/destinations", sessionToken, { method: "POST", body: { name, destination_type: type, endpoint, enabled: false, signing_key_reference: keyReference || null, minimization_profile: profile, rate_limit_per_minute: 60, max_attempts: 5 } })
      pushToast({ tone: "success", title: "Destination registered disabled", message: "Review and explicitly enable it before any evidence can be queued." })
      setName(""); setEndpoint(""); setKeyReference("")
      await control.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Destination rejected", message: error instanceof Error ? error.message : "Configuration failed." })
    } finally {
      setBusy(false)
    }
  }

  const recordColumns: Column<ExportRecord>[] = [
    { key: "event", header: "Event", sortValue: (item) => item.event_type, render: (item) => <div className="gg-cell-stack"><strong>{item.event_type.replaceAll("_", " ")}</strong><small>{names.get(item.destination_id) ?? item.destination_id}</small></div> },
    { key: "status", header: "Status", sortValue: (item) => item.status, render: (item) => <StatusBadge value={item.status} tone={item.status === "DELIVERED" ? "success" : item.status === "DEAD_LETTER" ? "danger" : item.status === "QUEUED" ? "warning" : undefined} /> },
    { key: "attempts", header: "Attempts", align: "end", secondary: true, sortValue: (item) => item.attempts, render: (item) => item.attempts },
    { key: "error", header: "Last error", secondary: true, render: (item) => item.last_error ?? <span className="gg-muted">None</span> },
    { key: "when", header: "Queued", sortValue: (item) => item.created_at, render: (item) => <span title={item.created_at}>{relativeTime(item.created_at)}</span> },
  ]

  return (
    <section className="gg-page">
      <PageHeader
        title="Security exports"
        icon={<RadioTower size={22} />}
        description="Signed delivery of minimized security evidence to your SIEM and observability destinations, with queue and destination health."
        actions={<button type="button" className="gg-button" onClick={() => void control.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <p className="gg-note"><ShieldCheck size={16} aria-hidden="true" /><span><strong>Fail closed by default.</strong> New destinations are disabled, credentials stay external, and every payload is redacted before it is queued.</span></p>

      <Guidance id="security-exports" title="Adding a SIEM destination">
        <ol>
          <li>Register the destination with its endpoint, a data-minimization profile and, optionally, the environment variable holding its signing key.</li>
          <li>Review it, then enable it. Only then is evidence queued for it, at up to 60 events a minute with 5 delivery attempts.</li>
          <li>Repeated failures move an event to the dead-letter queue and mark the destination degraded.</li>
        </ol>
      </Guidance>

      {control.isLoading && <LoadingState label="Loading security export controls" rows={3} />}
      {control.isError && <ErrorState message={control.error.message} onRetry={() => void control.refetch()} />}
      {control.data && (
        <>
          <StatGrid label="Security export summary">
            <StatCard label="Destinations" value={destinations.filter((item) => !item.archived_at).length} hint={`${destinations.filter((item) => destinationHealth(item) === "HEALTHY").length} healthy`} tone="info" />
            <StatCard label="Queued" value={counts.QUEUED ?? 0} hint="Waiting for delivery" tone={counts.QUEUED ? "warning" : "neutral"} />
            <StatCard label="Dead letter" value={counts.DEAD_LETTER ?? 0} hint="Gave up after retries" tone={counts.DEAD_LETTER ? "danger" : "success"} />
            <StatCard label="Degraded destinations" value={destinations.filter((item) => destinationHealth(item) === "DEGRADED").length} hint="Last delivery failed" tone={destinations.some((item) => destinationHealth(item) === "DEGRADED") ? "danger" : "success"} />
          </StatGrid>

          <Panel id="exports-register" eyebrow="New destination" title="Register a destination">
            <form className="gg-form" onSubmit={(event) => { event.preventDefault(); void save() }}>
              <div className="gg-form__row">
                <label className="gg-field">Name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Production SIEM" /></label>
                <label className="gg-field">Type<select value={type} onChange={(event) => setType(event.target.value)}>{(control.data.destination_types.length ? control.data.destination_types : [type]).map((item) => <option key={item}>{item}</option>)}</select></label>
                <label className="gg-field">Endpoint<input value={endpoint} onChange={(event) => setEndpoint(event.target.value)} placeholder={type === "SYSLOG" ? "tls://syslog.example.com:6514" : "https://security.example.com/ingest"} /></label>
                <label className="gg-field">Data profile<select value={profile} onChange={(event) => setProfile(event.target.value)}>{(control.data.minimization_profiles.length ? control.data.minimization_profiles : [profile]).map((item) => <option key={item}>{item}</option>)}</select></label>
                <label className="gg-field">Signing key reference<input value={keyReference} onChange={(event) => setKeyReference(event.target.value.toUpperCase())} placeholder="SIEM_SIGNING_KEY" /><small>Optional. An environment variable name.</small></label>
              </div>
              <div className="gg-form__actions"><button type="submit" className="gg-button gg-button--primary" disabled={busy || !name.trim() || !endpoint.trim()}><Plus size={16} aria-hidden="true" />Register disabled</button></div>
            </form>
          </Panel>

          <Panel id="exports-destinations" eyebrow="Destinations" title="Export destinations">
            <FilterBar options={{ label: "Show", value: filter, onChange: setFilter, items: [              { value: "ALL", label: "All", count: destinations.length },

              { value: "CURRENT", label: "Current", count: destinations.filter((item) => !item.archived_at).length },
              { value: "ARCHIVED", label: "Archived", count: destinations.filter((item) => item.archived_at).length },
            ] }} />
            {visible.length === 0
              ? <EmptyState icon={<RadioTower size={28} />} title={destinations.length ? "Nothing in this view" : "No export destinations"} description={destinations.length ? "Change the filter to see other destinations." : "Register an approved destination. It remains disabled until explicitly enabled."} />
              : (
                <div className="gg-card-grid" style={{ marginTop: "0.85rem" }}>
                  {visible.map((item) => (
                    <article className="gg-card" key={item.destination_id}>
                      <header className="gg-card__header">
                        <span className="gg-card__icon"><RadioTower size={18} aria-hidden="true" /></span>
                        <div><h3>{item.name}</h3><small>{item.destination_type}</small></div>
                        <StatusBadge value={destinationHealth(item)} tone={HEALTH_TONE[destinationHealth(item) as keyof typeof HEALTH_TONE]} />
                      </header>
                      <code className="gg-code">{item.endpoint}</code>
                      <dl className="gg-facts">
                        <div><dt>Data profile</dt><dd>{item.minimization_profile}</dd></div>
                        <div><dt>Rate limit</dt><dd>{item.rate_limit_per_minute}/minute</dd></div>
                        <div><dt>Credentials stored</dt><dd>{item.credentials_stored ? "Yes" : "No"}</dd></div>
                        <div><dt>Last success</dt><dd title={item.last_success_at ?? undefined}>{relativeTime(item.last_success_at)}</dd></div>
                      </dl>
                      {item.last_error && <p className="gg-note gg-note--danger">{item.last_error}</p>}
                      <ArchiveDestinationControl kind="security_export" destinationId={item.destination_id} name={item.name} archivedAt={item.archived_at} onArchived={async () => { await control.refetch() }} />
                    </article>
                  ))}
                </div>
              )}
          </Panel>

          <Panel id="exports-recent" eyebrow="Queue" title="Recent exports">
            <DataTable label="Recent exports" columns={recordColumns} rows={recent} rowKey={(item) => item.export_id} initialSort={{ key: "when", direction: "desc" }}
              rowTone={(item) => (item.status === "DEAD_LETTER" ? "danger" : undefined)}
              empty={<EmptyState icon={<Send size={28} />} title="Nothing exported yet" description="Evidence queued for an enabled destination appears here." />} />
          </Panel>
        </>
      )}
    </section>
  )
}
