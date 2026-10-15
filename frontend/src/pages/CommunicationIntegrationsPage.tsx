import { useQuery } from "@tanstack/react-query"
import { BellRing, Plus, RefreshCw, Send, ShieldCheck } from "lucide-react"
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
import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { adminCall } from "../lib/adminApi"

type Destination = { destination_id: string; name: string; channel: string; endpoint_reference: string; enabled: boolean; minimum_severity: string; quiet_start_hour: number | null; quiet_end_hour: number | null; critical_bypass: boolean; escalation_minutes: number; credentials_stored: boolean; archived_at?: string | null }
type Delivery = { delivery_id: string; status: string; subject: string; attempts: number }
type Config = { destinations: Destination[]; channels: string[]; templates: unknown[]; recent_deliveries: Delivery[] }

export const deliveryState = (enabled: boolean) => (enabled ? "ENABLED" : "DISABLED")

const hour = (value: number | null) => (value === null ? "–" : `${String(value).padStart(2, "0")}:00`)

export default function CommunicationIntegrationsPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const config = useQuery({ queryKey: ["notification-delivery"], queryFn: () => adminCall<Config>("/notification-delivery", sessionToken), enabled: Boolean(sessionToken) && administrator?.role === "PLATFORM_ADMIN" })
  const [name, setName] = useState("")
  const [channel, setChannel] = useState("EMAIL")
  const [reference, setReference] = useState("")
  const [filter, setFilter] = useState("ALL")
  const [busy, setBusy] = useState(false)

  const destinations = useMemo(() => config.data?.destinations ?? [], [config.data])
  const deliveries = config.data?.recent_deliveries ?? []
  const visible = destinations.filter((item) => filter === "ALL" || (filter === "ARCHIVED") === Boolean(item.archived_at))

  if (administrator?.role !== "PLATFORM_ADMIN") return <Navigate to="/dashboard" replace />

  // The same defaults the backend has always received for a new destination.
  const save = async () => {
    setBusy(true)
    try {
      await adminCall("/notification-delivery/destinations", sessionToken, { method: "POST", body: { name, channel, endpoint_reference: reference, enabled: false, minimum_severity: "HIGH", quiet_start_hour: 22, quiet_end_hour: 7, critical_bypass: true, escalation_minutes: 15 } })
      pushToast({ tone: "success", title: "Destination registered disabled", message: "Enable only after the external credential and recipient are verified." })
      setName(""); setReference("")
      await config.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Configuration rejected", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  const deliveryColumns: Column<Delivery>[] = [
    { key: "subject", header: "Notification", sortValue: (item) => item.subject, render: (item) => <strong>{item.subject}</strong> },
    { key: "status", header: "Status", sortValue: (item) => item.status, render: (item) => <StatusBadge value={item.status} /> },
    { key: "attempts", header: "Attempts", align: "end", sortValue: (item) => item.attempts, render: (item) => item.attempts },
  ]

  return (
    <section className="gg-page">
      <PageHeader
        eyebrow="Incident Response"
        title="Communications"
        icon={<BellRing size={22} />}
        description="External security notifications for your responders: which channels receive which severities, quiet hours, escalation, and the evidence of each delivery."
        actions={<button type="button" className="gg-button" onClick={() => void config.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <p className="gg-note"><ShieldCheck size={16} aria-hidden="true" /><span><strong>Disabled by default.</strong> Credentials remain external, and a destination must be explicitly enabled after its recipient is verified.</span></p>

      <Guidance id="communications" title="How notifications reach responders">
        <ul>
          <li>A new destination receives <strong>high</strong> and <strong>critical</strong> notifications, stays quiet from 22:00 to 07:00, and escalates after 15 minutes.</li>
          <li>Critical notifications bypass quiet hours.</li>
          <li>Each delivery attempt is recorded below. Archive a destination you no longer use.</li>
        </ul>
      </Guidance>

      {config.isLoading && <LoadingState label="Loading communication integrations" rows={3} />}
      {config.isError && <ErrorState message={config.error.message} onRetry={() => void config.refetch()} />}
      {config.data && (
        <>
          <StatGrid label="Communications summary">
            <StatCard label="Destinations" value={destinations.filter((item) => !item.archived_at).length} hint={`${destinations.filter((item) => item.archived_at).length} archived`} tone="info" />
            <StatCard label="Enabled" value={destinations.filter((item) => !item.archived_at && item.enabled).length} hint="Receiving notifications" tone="success" />
            <StatCard label="Recent deliveries" value={deliveries.length} hint="Latest attempts" />
            <StatCard label="Failed deliveries" value={deliveries.filter((item) => item.status === "FAILED" || item.status === "DEAD_LETTER").length} hint="In recent attempts" tone={deliveries.some((item) => item.status === "FAILED" || item.status === "DEAD_LETTER") ? "danger" : "success"} />
          </StatGrid>

          <Panel id="communications-register" eyebrow="New destination" title="Register a destination">
            <form className="gg-form" onSubmit={(event) => { event.preventDefault(); void save() }}>
              <div className="gg-form__row">
                <label className="gg-field">Name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Security on-call" /></label>
                <label className="gg-field">Channel<select value={channel} onChange={(event) => setChannel(event.target.value)}>{(config.data.channels.length ? config.data.channels : [channel]).map((item) => <option key={item}>{item}</option>)}</select></label>
                <label className="gg-field">Endpoint reference<input value={reference} onChange={(event) => setReference(event.target.value.toUpperCase())} placeholder="SECOPS_EMAIL" /><small>An environment variable holding the credential or address.</small></label>
              </div>
              <div className="gg-form__actions"><button type="submit" className="gg-button gg-button--primary" disabled={busy || !name.trim() || !reference.trim()}><Plus size={16} aria-hidden="true" />Register disabled</button></div>
            </form>
          </Panel>

          <Panel id="communications-destinations" eyebrow="Destinations" title="Notification destinations">
            <FilterBar options={{ label: "Show", value: filter, onChange: setFilter, items: [              { value: "ALL", label: "All", count: destinations.length },

              { value: "CURRENT", label: "Current", count: destinations.filter((item) => !item.archived_at).length },
              { value: "ARCHIVED", label: "Archived", count: destinations.filter((item) => item.archived_at).length },
            ] }} />
            {visible.length === 0
              ? <EmptyState icon={<BellRing size={28} />} title={destinations.length ? "Nothing in this view" : "No destinations"} description={destinations.length ? "Change the filter to see other destinations." : "Register an email or chat destination for security notifications."} />
              : (
                <div className="gg-card-grid" style={{ marginTop: "0.85rem" }}>
                  {visible.map((item) => (
                    <article className="gg-card" key={item.destination_id}>
                      <header className="gg-card__header">
                        <span className="gg-card__icon"><BellRing size={18} aria-hidden="true" /></span>
                        <div><h3>{item.name}</h3><small>{item.channel}</small></div>
                        <StatusBadge value={destinationArchiveState(item.archived_at) ?? deliveryState(item.enabled)} tone={item.archived_at ? "neutral" : item.enabled ? "success" : "neutral"} />
                      </header>
                      <code className="gg-code">{item.endpoint_reference}</code>
                      <dl className="gg-facts">
                        <div><dt>Minimum severity</dt><dd>{item.minimum_severity}</dd></div>
                        <div><dt>Quiet hours</dt><dd>{hour(item.quiet_start_hour)}–{hour(item.quiet_end_hour)}</dd></div>
                        <div><dt>Critical bypasses quiet</dt><dd>{item.critical_bypass ? "Yes" : "No"}</dd></div>
                        <div><dt>Escalation</dt><dd>{item.escalation_minutes} min</dd></div>
                        <div><dt>Credentials stored</dt><dd>{item.credentials_stored ? "Yes" : "No"}</dd></div>
                      </dl>
                      <ArchiveDestinationControl kind="notification" destinationId={item.destination_id} name={item.name} archivedAt={item.archived_at} onArchived={async () => { await config.refetch() }} />
                    </article>
                  ))}
                </div>
              )}
          </Panel>

          <Panel id="communications-deliveries" eyebrow="Evidence" title="Recent deliveries">
            <DataTable label="Recent deliveries" columns={deliveryColumns} rows={deliveries} rowKey={(item) => item.delivery_id}
              rowTone={(item) => (item.status === "FAILED" || item.status === "DEAD_LETTER" ? "danger" : undefined)}
              empty={<EmptyState icon={<Send size={28} />} title="No deliveries yet" description="Delivery attempts appear here once a destination is enabled and a notification is sent." />} />
          </Panel>
        </>
      )}
    </section>
  )
}
