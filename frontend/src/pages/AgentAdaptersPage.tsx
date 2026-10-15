import { useQuery } from "@tanstack/react-query"
import { Cable, FlaskConical, Network, RefreshCw, Save, ShieldOff } from "lucide-react"
import { useMemo, useState } from "react"
import { Navigate } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
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

type Manifest = { adapter_id: string; protocol: string; inbound_only: boolean; network_egress: boolean; arbitrary_code: boolean; credential_storage: boolean; requires_registered_agent: boolean; allowed_actions: string[] }
export type Adapter = { adapter_id: string; name: string; protocol: string; description: string; enabled: boolean; owner: string | null; purpose: string | null; allowed_actions: string[]; updated_at: string; updated_by: string; manifest: Manifest }
type Overview = { adapters: Adapter[]; disabled_by_default: boolean; network_egress: boolean }

export const adapterStateLabel = (enabled: boolean) => (enabled ? "Enabled" : "Kill switch active")

const yesNo = (value: boolean) => (value ? "Yes" : "No")

export default function AgentAdaptersPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const overview = useQuery({ queryKey: ["adapters"], queryFn: () => adminCall<Overview>("/adapters", sessionToken), enabled: Boolean(sessionToken) && administrator?.role === "PLATFORM_ADMIN" })
  // Unsaved edits per adapter, laid over what the server holds.
  const [edits, setEdits] = useState<Record<string, Partial<Adapter>>>({})
  const [busy, setBusy] = useState("")
  const [filter, setFilter] = useState("ALL")
  const [search, setSearch] = useState("")

  const saved = useMemo(() => new Map((overview.data?.adapters ?? []).map((item) => [item.adapter_id, item])), [overview.data])
  const items = (overview.data?.adapters ?? []).map((item) => ({ ...item, ...edits[item.adapter_id] }))
  const visible = items.filter((item) => {
    const needle = search.trim().toLowerCase()
    return (filter === "ALL" || (filter === "ENABLED") === saved.get(item.adapter_id)?.enabled)
      && (!needle || `${item.name} ${item.protocol} ${item.owner ?? ""}`.toLowerCase().includes(needle))
  })

  if (administrator?.role !== "PLATFORM_ADMIN") return <Navigate to="/dashboard" replace />

  const enabledCount = [...saved.values()].filter((item) => item.enabled).length
  const patch = (id: string, value: Partial<Adapter>) => setEdits((current) => ({ ...current, [id]: { ...current[id], ...value } }))
  const isDirty = (item: Adapter) => {
    const original = saved.get(item.adapter_id)
    return Boolean(original) && JSON.stringify([original!.enabled, original!.owner ?? "", original!.purpose ?? "", [...original!.allowed_actions].sort()]) !== JSON.stringify([item.enabled, item.owner ?? "", item.purpose ?? "", [...item.allowed_actions].sort()])
  }

  const save = async (item: Adapter) => {
    setBusy(item.adapter_id)
    try {
      await adminCall(`/adapters/${item.adapter_id}`, sessionToken, { method: "PUT", body: { enabled: item.enabled, owner: item.owner ?? "", purpose: item.purpose ?? "", allowed_actions: item.allowed_actions } })
      pushToast({ tone: "success", title: "Adapter controls saved", message: `${item.name} configuration saved and audited.` })
      await overview.refetch()
      setEdits((current) => { const next = { ...current }; delete next[item.adapter_id]; return next })
    } catch (error) {
      pushToast({ tone: "error", title: "Adapter update failed", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy("")
    }
  }

  const test = async (item: Adapter) => {
    setBusy(item.adapter_id)
    try {
      await adminCall(`/adapters/${item.adapter_id}/test`, sessionToken, { method: "POST" })
      pushToast({ tone: "success", title: "Isolated test passed", message: `${item.name} translated a test request without network access or a stored request.` })
    } catch (error) {
      pushToast({ tone: "error", title: "Adapter test failed", message: error instanceof Error ? error.message : "Test failed." })
    } finally {
      setBusy("")
    }
  }

  return (
    <section className="gg-page">
      <PageHeader
        eyebrow="Agents & Identity"
        title="Agent adapters"
        icon={<Network size={22} />}
        description="Framework adapters translate agent requests into GreyGuard's gateway. Review each adapter's capability manifest, test it in isolation, and stop it immediately with its kill switch."
        actions={<button type="button" className="gg-button" onClick={() => void overview.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <p className="gg-note gg-note--warning"><ShieldOff size={16} aria-hidden="true" /><span><strong>Fail-closed boundary.</strong> Adapters are disabled by default. No adapter receives network egress, arbitrary-code access or credential storage.</span></p>

      <Guidance id="agent-adapters" title="How to bring an adapter into service">
        <ol>
          <li>Name a responsible <strong>owner</strong> and an approved <strong>purpose</strong>.</li>
          <li>Allow only the <strong>actions</strong> the integration needs, from the adapter's manifest.</li>
          <li>Run the <strong>isolated test</strong>, then enable the adapter and save. Turning it off again sets the kill switch at once.</li>
        </ol>
      </Guidance>

      {overview.isLoading && <LoadingState label="Loading adapter controls" rows={3} />}
      {overview.isError && <ErrorState message={overview.error.message} onRetry={() => void overview.refetch()} />}
      {overview.data && (
        <>
          <StatGrid label="Adapter summary">
            <StatCard label="Adapters" value={items.length} hint="Available framework adapters" tone="info" />
            <StatCard label="Enabled" value={enabledCount} hint="Accepting agent requests" tone={enabledCount ? "warning" : "success"} />
            <StatCard label="Kill switch active" value={items.length - enabledCount} hint="Disabled, the safe default" />
            <StatCard label="Network egress" value={overview.data.network_egress ? "Allowed" : "None"} hint="For any adapter" tone={overview.data.network_egress ? "danger" : "success"} />
          </StatGrid>

          <Panel id="adapter-list" eyebrow="Adapters" title="Adapter controls">
            <FilterBar
              search={{ value: search, onChange: setSearch, placeholder: "Search adapter, protocol or owner" }}
              options={{ label: "State", value: filter, onChange: setFilter, items: [
                { value: "ALL", label: "All", count: items.length },
                { value: "ENABLED", label: "Enabled", count: enabledCount },
                { value: "DISABLED", label: "Kill switch active", count: items.length - enabledCount },
              ] }}
              summary={`${visible.length} of ${items.length} shown`}
            />
            {visible.length === 0
              ? <EmptyState icon={<Cable size={28} />} title={items.length ? "No matching adapters" : "No adapters available"} description={items.length ? "Change the search or state filter." : "Framework adapters appear here when they are installed."} />
              : (
                <div className="gg-card-grid" style={{ marginTop: "0.85rem" }}>
                  {visible.map((item) => {
                    const original = saved.get(item.adapter_id)
                    return (
                      <article className="gg-card" key={item.adapter_id} aria-label={item.name}>
                        <header className="gg-card__header">
                          <span className="gg-card__icon"><Cable size={18} aria-hidden="true" /></span>
                          <div><h3>{item.name}</h3><small>{item.protocol} · {item.adapter_id}</small></div>
                          <StatusBadge value={adapterStateLabel(Boolean(original?.enabled))} tone={original?.enabled ? "warning" : "neutral"} />
                        </header>
                        <p>{item.description}</p>
                        <dl className="gg-facts" aria-label="Capability manifest">
                          <div><dt>Inbound only</dt><dd>{yesNo(item.manifest.inbound_only)}</dd></div>
                          <div><dt>Network egress</dt><dd>{yesNo(item.manifest.network_egress)}</dd></div>
                          <div><dt>Arbitrary code</dt><dd>{yesNo(item.manifest.arbitrary_code)}</dd></div>
                          <div><dt>Credentials stored</dt><dd>{yesNo(item.manifest.credential_storage)}</dd></div>
                          <div><dt>Registered agent required</dt><dd>{yesNo(item.manifest.requires_registered_agent)}</dd></div>
                          <div><dt>Last changed</dt><dd title={item.updated_at}>{relativeTime(item.updated_at)}</dd></div>
                        </dl>
                        <div className="gg-form">
                          <label className="gg-field">Responsible owner<input value={item.owner ?? ""} onChange={(event) => patch(item.adapter_id, { owner: event.target.value })} placeholder="Security Engineering" /></label>
                          <label className="gg-field">Purpose statement<textarea value={item.purpose ?? ""} onChange={(event) => patch(item.adapter_id, { purpose: event.target.value })} placeholder="Describe the approved integration purpose" /></label>
                          <fieldset className="gg-fieldset">
                            <legend>Allowed actions</legend>
                            {item.manifest.allowed_actions.map((action) => (
                              <label className="gg-check" key={action}>
                                <input type="checkbox" checked={item.allowed_actions.includes(action)} onChange={(event) => patch(item.adapter_id, { allowed_actions: event.target.checked ? [...item.allowed_actions, action] : item.allowed_actions.filter((value) => value !== action) })} />
                                {action}
                              </label>
                            ))}
                          </fieldset>
                          <label className="gg-check">
                            <input type="checkbox" checked={item.enabled} onChange={(event) => patch(item.adapter_id, { enabled: event.target.checked })} />
                            <span>{item.enabled ? "Adapter enabled" : "Emergency kill switch active"}</span>
                          </label>
                          <div className="gg-form__actions">
                            {isDirty(item) && <span className="gg-muted" style={{ marginRight: "auto", fontSize: "0.74rem" }}>Unsaved changes</span>}
                            <button type="button" className="gg-button" disabled={busy === item.adapter_id} onClick={() => void test(item)}><FlaskConical size={15} aria-hidden="true" />Isolated test</button>
                            <button type="button" className="gg-button gg-button--primary" disabled={busy === item.adapter_id || !isDirty(item)} onClick={() => void save(item)}><Save size={15} aria-hidden="true" />Save controls</button>
                          </div>
                        </div>
                      </article>
                    )
                  })}
                </div>
              )}
          </Panel>
        </>
      )}
    </section>
  )
}
