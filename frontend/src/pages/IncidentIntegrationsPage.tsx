import { useQuery } from "@tanstack/react-query"
import { Link2, Plus, RefreshCw, ShieldCheck, TicketCheck } from "lucide-react"
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

type Destination = { destination_id: string; name: string; system_type: string; endpoint: string; credential_reference: string; project_or_table: string; enabled: boolean; credentials_stored: boolean; archived_at?: string | null }
type ApprovalLink = { link_id: string; request_id: string; expires_at: string; used_at: string | null }
type Config = { destinations: Destination[]; systems: string[]; records: Array<{ record_id: string; status: string; external_id: string | null }>; approval_links: ApprovalLink[] }

export const approvalLinkState = (used: string | null, expires: string) => (used ? "USED" : new Date(expires) <= new Date() ? "EXPIRED" : "ACTIVE")

const destinationState = (item: Destination) => destinationArchiveState(item.archived_at) ?? (item.enabled ? "ENABLED" : "DISABLED")

export default function IncidentIntegrationsPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const config = useQuery({ queryKey: ["incident-integrations"], queryFn: () => adminCall<Config>("/incident-integrations", sessionToken), enabled: Boolean(sessionToken) && administrator?.role === "PLATFORM_ADMIN" })
  const [name, setName] = useState("")
  const [system, setSystem] = useState("JIRA")
  const [endpoint, setEndpoint] = useState("")
  const [reference, setReference] = useState("")
  const [target, setTarget] = useState("")
  const [filter, setFilter] = useState("ALL")
  const [busy, setBusy] = useState(false)

  const destinations = useMemo(() => config.data?.destinations ?? [], [config.data])
  const links = config.data?.approval_links ?? []
  const visible = destinations.filter((item) => filter === "ALL" || (filter === "ARCHIVED") === Boolean(item.archived_at))

  if (administrator?.role !== "PLATFORM_ADMIN") return <Navigate to="/dashboard" replace />

  const save = async () => {
    setBusy(true)
    try {
      await adminCall("/incident-integrations/destinations", sessionToken, { method: "POST", body: { name, system_type: system, endpoint, credential_reference: reference, project_or_table: target, enabled: false } })
      pushToast({ tone: "success", title: "Incident integration registered", message: "The integration remains disabled until explicitly reviewed." })
      setName(""); setEndpoint(""); setReference(""); setTarget("")
      await config.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Configuration rejected", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  const linkColumns: Column<ApprovalLink>[] = [
    { key: "request", header: "Request", sortValue: (item) => item.request_id, render: (item) => <code className="gg-code">{item.request_id}</code> },
    { key: "expires", header: "Expires", sortValue: (item) => item.expires_at, render: (item) => new Date(item.expires_at).toLocaleString() },
    { key: "state", header: "State", sortValue: (item) => approvalLinkState(item.used_at, item.expires_at), render: (item) => <StatusBadge value={approvalLinkState(item.used_at, item.expires_at)} tone={item.used_at ? "neutral" : approvalLinkState(item.used_at, item.expires_at) === "ACTIVE" ? "warning" : "neutral"} /> },
  ]

  return (
    <section className="gg-page">
      <PageHeader
        eyebrow="Incident Response"
        title="Incident integrations"
        icon={<TicketCheck size={22} />}
        description="Send incidents to Jira or ServiceNow, and keep the evidence of expiring approval links and signed callbacks."
        actions={<button type="button" className="gg-button" onClick={() => void config.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <p className="gg-note"><ShieldCheck size={16} aria-hidden="true" /><span><strong>Human authority preserved.</strong> Approval links require an authenticated administrator, expire quickly and work only once.</span></p>

      <Guidance id="incident-integrations" title="Connecting a ticketing system">
        <ol>
          <li>Register the system with its HTTPS endpoint and the name of the environment variable that holds its credential. The credential itself never enters GreyGuard.</li>
          <li>New integrations start disabled. Enable one only after checking the endpoint and project or table.</li>
          <li>Archive an integration you no longer use: it is disabled for good, its history kept and its capacity freed.</li>
        </ol>
      </Guidance>

      {config.isLoading && <LoadingState label="Loading incident integrations" rows={3} />}
      {config.isError && <ErrorState message={config.error.message} onRetry={() => void config.refetch()} />}
      {config.data && (
        <>
          <StatGrid label="Incident integration summary">
            <StatCard label="Integrations" value={destinations.filter((item) => !item.archived_at).length} hint={`${destinations.filter((item) => item.archived_at).length} archived`} tone="info" />
            <StatCard label="Enabled" value={destinations.filter((item) => destinationState(item) === "ENABLED").length} hint="Receiving incidents" tone="success" />
            <StatCard label="Synced records" value={config.data.records.length} hint="Incidents sent to a ticketing system" />
            <StatCard label="Active approval links" value={links.filter((item) => approvalLinkState(item.used_at, item.expires_at) === "ACTIVE").length} hint="Unused and unexpired" tone={links.some((item) => approvalLinkState(item.used_at, item.expires_at) === "ACTIVE") ? "warning" : "neutral"} />
          </StatGrid>

          <Panel id="incident-register" eyebrow="New integration" title="Register an incident integration">
            <form className="gg-form" onSubmit={(event) => { event.preventDefault(); void save() }}>
              <div className="gg-form__row">
                <label className="gg-field">Name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Security incidents" /></label>
                <label className="gg-field">System<select value={system} onChange={(event) => setSystem(event.target.value)}>{(config.data.systems.length ? config.data.systems : [system]).map((item) => <option key={item}>{item}</option>)}</select></label>
                <label className="gg-field">HTTPS endpoint<input value={endpoint} onChange={(event) => setEndpoint(event.target.value)} placeholder="https://example.atlassian.net" /></label>
                <label className="gg-field">Credential reference<input value={reference} onChange={(event) => setReference(event.target.value.toUpperCase())} placeholder="JIRA_API_TOKEN" /><small>An environment variable name.</small></label>
                <label className="gg-field">{system === "JIRA" ? "Project key" : "Incident table"}<input value={target} onChange={(event) => setTarget(event.target.value)} placeholder={system === "JIRA" ? "SEC" : "incident"} /></label>
              </div>
              <div className="gg-form__actions"><button type="submit" className="gg-button gg-button--primary" disabled={busy || !name.trim() || !endpoint.trim()}><Plus size={16} aria-hidden="true" />Register disabled</button></div>
            </form>
          </Panel>

          <Panel id="incident-destinations" eyebrow="Integrations" title="Ticketing integrations">
            <FilterBar options={{ label: "Show", value: filter, onChange: setFilter, items: [              { value: "ALL", label: "All", count: destinations.length },

              { value: "CURRENT", label: "Current", count: destinations.filter((item) => !item.archived_at).length },
              { value: "ARCHIVED", label: "Archived", count: destinations.filter((item) => item.archived_at).length },
            ] }} />
            {visible.length === 0
              ? <EmptyState icon={<TicketCheck size={28} />} title={destinations.length ? "Nothing in this view" : "No incident integrations"} description={destinations.length ? "Change the filter to see other integrations." : "Register Jira or ServiceNow to send incidents automatically."} />
              : (
                <div className="gg-card-grid" style={{ marginTop: "0.85rem" }}>
                  {visible.map((item) => (
                    <article className="gg-card" key={item.destination_id}>
                      <header className="gg-card__header">
                        <span className="gg-card__icon"><TicketCheck size={18} aria-hidden="true" /></span>
                        <div><h3>{item.name}</h3><small>{item.system_type}</small></div>
                        <StatusBadge value={destinationState(item)} tone={item.archived_at ? "neutral" : item.enabled ? "success" : "neutral"} />
                      </header>
                      <code className="gg-code">{item.endpoint}</code>
                      <dl className="gg-facts">
                        <div><dt>Target</dt><dd>{item.project_or_table}</dd></div>
                        <div><dt>Credential</dt><dd>{item.credentials_stored ? "Stored" : "External reference"}</dd></div>
                      </dl>
                      <ArchiveDestinationControl kind="incident" destinationId={item.destination_id} name={item.name} archivedAt={item.archived_at} onArchived={async () => { await config.refetch() }} />
                    </article>
                  ))}
                </div>
              )}
          </Panel>

          <Panel id="incident-links" eyebrow="Evidence" title="Approval links">
            <p className="gg-muted" style={{ margin: "0 0 0.6rem", fontSize: "0.78rem" }}><Link2 size={13} aria-hidden="true" /> Link tokens are never listed after creation.</p>
            <DataTable label="Approval links" columns={linkColumns} rows={links} rowKey={(item) => item.link_id} initialSort={{ key: "expires", direction: "desc" }}
              empty={<EmptyState icon={<Link2 size={28} />} title="No approval links" description="Single-use approval links sent with incidents appear here." />} />
          </Panel>
        </>
      )}
    </section>
  )
}
