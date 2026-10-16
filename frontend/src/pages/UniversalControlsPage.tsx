import { useQuery } from "@tanstack/react-query"
import { LockKeyhole, Power, RefreshCw, ShieldOff } from "lucide-react"
import { useMemo, useState } from "react"
import { Navigate } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { ConfirmDialog } from "../components/ConfirmDialog"
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

type Control = { capability: string; enabled: boolean; owner: string; purpose: string; permissions: string[]; expires_at: string | null; human_approval: boolean; dry_run: boolean; rate_limit_per_minute: number; resource_limit: number; global_kill_switch: boolean; integration_kill_switch: boolean }

export const controlState = (item: Pick<Control, "enabled" | "global_kill_switch" | "integration_kill_switch">) =>
  item.global_kill_switch || item.integration_kill_switch ? "KILLED" : item.enabled ? "ENABLED" : "DISABLED"

const STATE_TONE = { KILLED: "danger", ENABLED: "warning", DISABLED: "neutral" } as const

export default function UniversalControlsPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const controls = useQuery({ queryKey: ["universal-controls"], queryFn: () => adminCall<{ controls: Control[] }>("/universal-controls", sessionToken), enabled: Boolean(sessionToken) && administrator?.role === "PLATFORM_ADMIN" })
  const [filter, setFilter] = useState("ALL")
  const [search, setSearch] = useState("")
  const [pending, setPending] = useState<{ item: Control; enable: boolean } | null>(null)
  const [busy, setBusy] = useState(false)

  const items = useMemo(() => controls.data?.controls ?? [], [controls.data])
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return items.filter((item) => (filter === "ALL" || controlState(item) === filter)
      && (!needle || `${item.capability} ${item.owner} ${item.purpose}`.toLowerCase().includes(needle)))
  }, [items, filter, search])

  if (administrator?.role !== "PLATFORM_ADMIN") return <Navigate to="/dashboard" replace />

  const count = (state: string) => items.filter((item) => controlState(item) === state).length

  // The same request bodies the backend has always received for authorize and kill.
  const update = async (item: Control, enable: boolean) => {
    const body = enable
      ? { ...item, enabled: true, owner: administrator?.email ?? "Platform Administrator", purpose: "Time-limited controlled security operation", permissions: ["RUN"], expires_at: new Date(Date.now() + 3600000).toISOString(), human_approval: true, dry_run: true, global_kill_switch: false, integration_kill_switch: false }
      : { ...item, enabled: false, integration_kill_switch: true }
    setBusy(true)
    try {
      await adminCall(`/universal-controls/${item.capability}`, sessionToken, { method: "PUT", body })
      pushToast({ tone: "success", title: enable ? "Capability authorized" : "Capability killed", message: "The control change and evidence were recorded." })
      setPending(null)
      await controls.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Control rejected", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  const columns: Column<Control>[] = [
    { key: "capability", header: "Capability", sortValue: (item) => item.capability, render: (item) => <div className="gg-cell-stack"><strong>{item.capability.replaceAll("_", " ")}</strong><small>{item.purpose || "Disabled until a purpose and permission manifest are configured."}</small></div> },
    { key: "state", header: "State", sortValue: (item) => controlState(item), render: (item) => <StatusBadge value={controlState(item)} tone={STATE_TONE[controlState(item)]} /> },
    { key: "owner", header: "Owner", secondary: true, sortValue: (item) => item.owner, render: (item) => item.owner || <span className="gg-muted">Unassigned</span> },
    { key: "guards", header: "Guards", secondary: true, render: (item) => <div className="gg-cell-stack"><span>Approval {item.human_approval ? "required" : "optional"} · dry run {item.dry_run ? "required" : "off"}</span><small>{item.rate_limit_per_minute}/min · {item.resource_limit} resources · {item.permissions.length} permissions</small></div> },
    { key: "expires", header: "Authorized until", sortValue: (item) => item.expires_at, render: (item) => item.expires_at ? new Date(item.expires_at).toLocaleString() : <span className="gg-muted">Not authorized</span> },
    {
      key: "actions", header: "Actions", align: "end",
      render: (item) => item.enabled
        ? <button type="button" className="gg-button gg-button--danger" onClick={() => setPending({ item, enable: false })} aria-label={`Kill ${item.capability}`}><Power size={14} aria-hidden="true" />Kill</button>
        : <button type="button" className="gg-button" onClick={() => setPending({ item, enable: true })} aria-label={`Authorize ${item.capability} for one hour`}><Power size={14} aria-hidden="true" />Authorize 1 hour</button>,
    },
  ]

  return (
    <section className="gg-page">
      <PageHeader
        title="Universal controls"
        icon={<LockKeyhole size={22} />}
        description="Every Tier 2 and Tier 3 capability needs an owner, a purpose, an expiry, human approval and an allowlist before the backend lets it run."
        actions={<button type="button" className="gg-button" onClick={() => void controls.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <p className="gg-note gg-note--warning"><ShieldOff size={16} aria-hidden="true" /><span><strong>Fail closed is mandatory.</strong> A missing, expired, disabled, unapproved or out-of-scope configuration is blocked by the backend, whatever this page shows.</span></p>

      <Guidance id="universal-controls" title="How a capability is authorized">
        <ol>
          <li><strong>Authorize</strong> opens one capability for one hour, in dry-run mode, with human approval required and you as owner.</li>
          <li>Requests that use it still pass through policy and approval as normal.</li>
          <li><strong>Kill</strong> sets the integration kill switch at once. Authorization lapses on its own when it expires.</li>
        </ol>
      </Guidance>

      {controls.isLoading && <LoadingState label="Loading universal controls" rows={4} />}
      {controls.isError && <ErrorState message={controls.error.message} onRetry={() => void controls.refetch()} />}
      {controls.data && (
        <>
          <StatGrid label="Capability summary">
            <StatCard label="Capabilities" value={items.length} hint="Under universal control" tone="info" />
            <StatCard label="Authorized" value={count("ENABLED")} hint="Currently able to run" tone={count("ENABLED") ? "warning" : "success"} />
            <StatCard label="Killed" value={count("KILLED")} hint="Kill switch active" tone={count("KILLED") ? "danger" : "neutral"} />
            <StatCard label="Disabled" value={count("DISABLED")} hint="Fail-closed default" />
          </StatGrid>
          <Panel id="controls-list" eyebrow="Capabilities" title="Control register">
            <FilterBar
              search={{ value: search, onChange: setSearch, placeholder: "Search capability, owner or purpose" }}
              options={{ label: "State", value: filter, onChange: setFilter, items: [
                { value: "ALL", label: "All", count: items.length },
                { value: "ENABLED", label: "Authorized", count: count("ENABLED") },
                { value: "KILLED", label: "Killed", count: count("KILLED") },
                { value: "DISABLED", label: "Disabled", count: count("DISABLED") },
              ] }}
              summary={`${visible.length} of ${items.length} shown`}
            />
            <DataTable
              label="Universal controls"
              columns={columns}
              rows={visible}
              rowKey={(item) => item.capability}
              rowTone={(item) => (controlState(item) === "KILLED" ? "danger" : controlState(item) === "ENABLED" ? "warning" : undefined)}
              empty={<EmptyState icon={<LockKeyhole size={28} />} title={items.length ? "No matching capabilities" : "No capabilities registered"} description={items.length ? "Change the search or state filter." : "High-impact capabilities appear here once they are registered with the control plane."} />}
            />
          </Panel>
        </>
      )}

      <ConfirmDialog
        open={Boolean(pending)}
        title={pending?.enable ? `Authorize ${pending.item.capability.replaceAll("_", " ")}?` : `Kill ${pending?.item.capability.replaceAll("_", " ") ?? "capability"}?`}
        description={pending?.enable
          ? "The capability is authorized for one hour, in dry-run mode, with human approval required and you recorded as owner. The change is audited."
          : "The integration kill switch is set immediately and the capability stops running. The change is audited."}
        confirmLabel={pending?.enable ? "Authorize for 1 hour" : "Kill capability"}
        tone={pending?.enable ? "warning" : "danger"}
        busy={busy}
        onCancel={() => setPending(null)}
        onConfirm={() => pending && void update(pending.item, pending.enable)}
      />
    </section>
  )
}
