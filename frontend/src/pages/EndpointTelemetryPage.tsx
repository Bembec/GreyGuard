import { useQuery } from "@tanstack/react-query"
import { Eye, MonitorCheck, Power, RefreshCw, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { Navigate } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { FilterBar } from "../components/page/FilterBar"
import { Guidance } from "../components/page/Guidance"
import { PageHeader } from "../components/page/PageHeader"
import { Panel } from "../components/page/Panel"
import { StatCard, StatGrid } from "../components/page/StatCard"
import { StatusBadge } from "../components/page/StatusBadge"
import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { adminCall } from "../lib/adminApi"

type Collector = { collector_id: string; name: string; owner: string; purpose: string; enabled: boolean; visible_indicator: boolean; permissions: string[]; approved_directories: string[]; retention_days: number; consent_reference: string }

export const telemetryState = (enabled: boolean) => (enabled ? "MONITORING" : "DISABLED")

type PendingAction = { item: Collector; kind: "toggle" | "uninstall" }

export default function EndpointTelemetryPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const telemetry = useQuery({ queryKey: ["endpoint-telemetry"], queryFn: () => adminCall<{ collectors: Collector[] }>("/endpoint-telemetry", sessionToken), enabled: Boolean(sessionToken) && administrator?.role === "PLATFORM_ADMIN" })
  const [filter, setFilter] = useState("ALL")
  const [search, setSearch] = useState("")
  const [pending, setPending] = useState<PendingAction | null>(null)
  const [busy, setBusy] = useState(false)

  const collectors = useMemo(() => telemetry.data?.collectors ?? [], [telemetry.data])
  const visible = collectors.filter((item) => {
    const needle = search.trim().toLowerCase()
    return (filter === "ALL" || telemetryState(item.enabled) === filter)
      && (!needle || `${item.name} ${item.owner} ${item.purpose}`.toLowerCase().includes(needle))
  })

  if (administrator?.role !== "PLATFORM_ADMIN") return <Navigate to="/dashboard" replace />

  const monitoring = collectors.filter((item) => item.enabled).length
  const confirm = async () => {
    if (!pending) return
    const { item, kind } = pending
    setBusy(true)
    try {
      if (kind === "toggle") await adminCall(`/endpoint-telemetry/collectors/${item.collector_id}`, sessionToken, { method: "PUT", body: { enabled: !item.enabled } })
      else await adminCall(`/endpoint-telemetry/collectors/${item.collector_id}?confirm=true`, sessionToken, { method: "DELETE" })
      pushToast({ tone: "success", title: kind === "toggle" ? "Collector state updated" : "Uninstall started", message: "The telemetry decision was recorded." })
      setPending(null)
      await telemetry.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Change blocked", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="gg-page">
      <PageHeader
        eyebrow="Telemetry & Sensors"
        title="Endpoint telemetry"
        icon={<Eye size={22} />}
        description="Consent-bound, read-only metadata from endpoints you have registered. Each collector is visible to the people it monitors and stays off until an administrator enables it."
        actions={<button type="button" className="gg-button" onClick={() => void telemetry.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <p className="gg-note"><MonitorCheck size={16} aria-hidden="true" /><span><strong>No payload, credential, screen, microphone or keystroke capture.</strong> Collectors remain disabled until a Platform Administrator explicitly enables them.</span></p>

      <Guidance id="endpoint-telemetry" title="Before enabling a collector">
        <ul>
          <li>Confirm the <strong>consent reference</strong> covers the people and devices being monitored.</li>
          <li>Check that the permissions and approved directories are the minimum needed, and that the visible indicator is required.</li>
          <li><strong>Uninstall</strong> disables the collector and starts revocation on the endpoint. Collected metadata follows its retention period.</li>
        </ul>
      </Guidance>

      {telemetry.isLoading && <LoadingState label="Loading endpoint telemetry" rows={3} />}
      {telemetry.isError && <ErrorState message={telemetry.error.message} onRetry={() => void telemetry.refetch()} />}
      {telemetry.data && (
        <>
          <StatGrid label="Endpoint telemetry summary">
            <StatCard label="Collectors" value={collectors.length} hint="Registered endpoints" tone="info" />
            <StatCard label="Monitoring" value={monitoring} hint="Enabled and collecting" tone={monitoring ? "warning" : "neutral"} />
            <StatCard label="Indicator missing" value={collectors.filter((item) => !item.visible_indicator).length} hint="Collectors without a visible indicator" tone={collectors.some((item) => !item.visible_indicator) ? "danger" : "success"} />
          </StatGrid>

          <Panel id="telemetry-collectors" eyebrow="Collectors" title="Registered collectors">
            <FilterBar
              search={{ value: search, onChange: setSearch, placeholder: "Search collector, owner or purpose" }}
              options={{ label: "State", value: filter, onChange: setFilter, items: [
                { value: "ALL", label: "All", count: collectors.length },
                { value: "MONITORING", label: "Monitoring", count: monitoring },
                { value: "DISABLED", label: "Disabled", count: collectors.length - monitoring },
              ] }}
              summary={`${visible.length} of ${collectors.length} shown`}
            />
            {visible.length === 0
              ? <EmptyState icon={<MonitorCheck size={28} />} title={collectors.length ? "No matching collectors" : "No collectors registered"} description={collectors.length ? "Change the search or state filter." : "Collectors appear here when an endpoint is registered with GreyGuard."} />
              : (
                <div className="gg-card-grid" style={{ marginTop: "0.85rem" }}>
                  {visible.map((item) => (
                    <article className="gg-card" key={item.collector_id} aria-label={item.name}>
                      <header className="gg-card__header">
                        <span className="gg-card__icon"><MonitorCheck size={18} aria-hidden="true" /></span>
                        <div><h3>{item.name}</h3><small>{item.owner} · consent {item.consent_reference}</small></div>
                        <StatusBadge value={telemetryState(item.enabled)} tone={item.enabled ? "warning" : "neutral"} />
                      </header>
                      <p>{item.purpose}</p>
                      <dl className="gg-facts">
                        <div><dt>Permissions</dt><dd>{item.permissions.map((value) => value.replaceAll("_", " ")).join(", ") || "None"}</dd></div>
                        <div><dt>Directories</dt><dd>{item.approved_directories.length || "None"}</dd></div>
                        <div><dt>Retention</dt><dd>{item.retention_days} days</dd></div>
                        <div><dt>Visible indicator</dt><dd>{item.visible_indicator ? "Required" : "Missing"}</dd></div>
                      </dl>
                      <div className="gg-form__actions">
                        <button type="button" className="gg-button" onClick={() => setPending({ item, kind: "toggle" })}><Power size={14} aria-hidden="true" />{item.enabled ? "Disable" : "Enable"}</button>
                        <button type="button" className="gg-button gg-button--danger" onClick={() => setPending({ item, kind: "uninstall" })}><Trash2 size={14} aria-hidden="true" />Uninstall</button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
          </Panel>
        </>
      )}

      <ConfirmDialog
        open={Boolean(pending)}
        title={pending?.kind === "uninstall" ? `Uninstall ${pending.item.name}?` : `${pending?.item.enabled ? "Disable" : "Enable"} ${pending?.item.name ?? "collector"}?`}
        description={pending?.kind === "uninstall"
          ? "The collector is disabled and uninstall and revocation begin on the endpoint."
          : pending?.item.enabled ? "Collection stops at once." : "Collection starts under the permissions, directories and retention shown. The endpoint shows its visible indicator."}
        confirmLabel={pending?.kind === "uninstall" ? "Uninstall collector" : pending?.item.enabled ? "Disable collector" : "Enable collector"}
        tone={pending?.kind === "uninstall" ? "danger" : "warning"}
        busy={busy}
        onCancel={() => setPending(null)}
        onConfirm={() => void confirm()}
      />
    </section>
  )
}
