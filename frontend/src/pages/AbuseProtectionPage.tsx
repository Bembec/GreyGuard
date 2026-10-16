import { useQuery } from "@tanstack/react-query"
import { Activity, Gauge, RefreshCw, Save, ShieldAlert } from "lucide-react"
import { useMemo, useState } from "react"
import { Navigate } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
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

export type RateLimitPolicy = { category: string; enabled: boolean; request_limit: number; window_seconds: number; block_seconds: number; max_failed_attempts: number; updated_at: string; updated_by: string }
type AbuseEvent = { event_id: string; timestamp: string; category: string; event_type: string; severity: string; identifier_hint: string; request_count: number; detail: string }
type Overview = { summary: { events: number; quota_blocks: number; auth_lockouts: number; bursts: number; active_blocks: number }; policies: RateLimitPolicy[]; events: AbuseEvent[] }

export function formatProtectionCategory(category: string) {
  return category.toLowerCase().replaceAll("_", " ").replace(/(^|\s)\S/g, (value) => value.toUpperCase())
}

const NUMBER_FIELDS = [["request_limit", "Request limit", 1, 10000], ["window_seconds", "Window (seconds)", 1, undefined], ["block_seconds", "Block (seconds)", 1, undefined], ["max_failed_attempts", "Failed attempts", 1, 100]] as const

export default function AbuseProtectionPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  // GET /abuse-protection itself calls require_install_operator() server-side, so the whole page,
  // not just its writes, is install-operator-only and other roles are redirected.
  const overview = useQuery({ queryKey: ["abuse-protection"], queryFn: () => adminCall<Overview>("/abuse-protection", sessionToken), enabled: Boolean(sessionToken) && Boolean(administrator?.install_operator) })
  const [edits, setEdits] = useState<Record<string, Partial<RateLimitPolicy>>>({})
  const [category, setCategory] = useState("ALL")
  const [busy, setBusy] = useState("")

  const events = useMemo(() => overview.data?.events ?? [], [overview.data])
  const categories = [...new Set(events.map((item) => item.category))]
  const visibleEvents = events.filter((item) => category === "ALL" || item.category === category)

  if (!administrator?.install_operator) return <Navigate to="/dashboard" replace />

  const policies = (overview.data?.policies ?? []).map((policy) => ({ ...policy, ...edits[policy.category] }))
  const summary = overview.data?.summary
  const update = (key: string, field: keyof RateLimitPolicy, value: number | boolean) => setEdits((current) => ({ ...current, [key]: { ...current[key], [field]: value } }))

  const save = async (policy: RateLimitPolicy) => {
    setBusy(policy.category)
    try {
      await adminCall(`/abuse-protection/policies/${policy.category}`, sessionToken, { method: "PUT", body: { enabled: policy.enabled, request_limit: policy.request_limit, window_seconds: policy.window_seconds, block_seconds: policy.block_seconds, max_failed_attempts: policy.max_failed_attempts } })
      pushToast({ tone: "success", title: "Protection policy updated", message: `${formatProtectionCategory(policy.category)} changes take effect immediately.` })
      await overview.refetch()
      setEdits((current) => { const next = { ...current }; delete next[policy.category]; return next })
    } catch (error) {
      pushToast({ tone: "error", title: "Policy update failed", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy("")
    }
  }

  const eventColumns: Column<AbuseEvent>[] = [
    { key: "type", header: "Event", sortValue: (item) => item.event_type, render: (item) => <div className="gg-cell-stack"><strong>{formatProtectionCategory(item.event_type)}</strong><small>{item.detail}</small></div> },
    { key: "severity", header: "Severity", sortValue: (item) => item.severity, render: (item) => <StatusBadge value={item.severity} /> },
    { key: "category", header: "Category", sortValue: (item) => item.category, render: (item) => formatProtectionCategory(item.category) },
    { key: "source", header: "Source", secondary: true, render: (item) => <code className="gg-code">{item.identifier_hint}</code> },
    { key: "count", header: "Requests", align: "end", secondary: true, sortValue: (item) => item.request_count, render: (item) => item.request_count },
    { key: "when", header: "When", sortValue: (item) => item.timestamp, render: (item) => <span title={item.timestamp}>{relativeTime(item.timestamp)}</span> },
  ]

  return (
    <section className="gg-page">
      <PageHeader
        title="Abuse protection"
        icon={<ShieldAlert size={22} />}
        description="Install-wide request throttling, lockouts after repeated failures, and evidence of suspicious bursts."
        actions={<button type="button" className="gg-button" onClick={() => void overview.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <Guidance id="abuse-protection" title="How the limits work">
        <ul>
          <li>Each category counts requests per client in a fixed <strong>window</strong>. Going over the <strong>request limit</strong> blocks that client for the <strong>block</strong> period.</li>
          <li>Reaching 80% of a limit records a burst warning. Too many <strong>failed attempts</strong> locks the client out.</li>
          <li>Administrator sign-in has the strictest limits. Loosen them only with a clear reason: they protect every account on the install.</li>
        </ul>
      </Guidance>

      {overview.isLoading && <LoadingState label="Loading abuse protection" rows={3} />}
      {overview.isError && <ErrorState message={overview.error.message} onRetry={() => void overview.refetch()} />}
      {overview.data && (
        <>
          <StatGrid label="Abuse protection summary">
            <StatCard label="Active blocks" value={summary?.active_blocks ?? 0} hint="Clients blocked right now" tone={summary?.active_blocks ? "danger" : "success"} />
            <StatCard label="Quota blocks" value={summary?.quota_blocks ?? 0} hint="Limits exceeded" tone={summary?.quota_blocks ? "warning" : "neutral"} />
            <StatCard label="Sign-in lockouts" value={summary?.auth_lockouts ?? 0} hint="Too many failed attempts" tone={summary?.auth_lockouts ? "warning" : "neutral"} />
            <StatCard label="Burst warnings" value={summary?.bursts ?? 0} hint="80% of a limit reached" />
          </StatGrid>

          <Panel id="abuse-policies" eyebrow="Policies" title="Protection policies">
            <div className="gg-card-grid">
              {policies.map((policy) => {
                const dirty = Boolean(edits[policy.category])
                return (
                  <article className="gg-card" key={policy.category} aria-label={formatProtectionCategory(policy.category)}>
                    <header className="gg-card__header">
                      <span className="gg-card__icon"><Gauge size={18} aria-hidden="true" /></span>
                      <div><h3>{formatProtectionCategory(policy.category)}</h3><small>Changed {relativeTime(policy.updated_at)} by {policy.updated_by}</small></div>
                      <StatusBadge value={policy.enabled ? "ENFORCED" : "OFF"} tone={policy.enabled ? "success" : "danger"} />
                    </header>
                    <form className="gg-form" onSubmit={(event) => { event.preventDefault(); void save(policy) }}>
                      <div className="gg-form__row">
                        {NUMBER_FIELDS.map(([field, label, min, max]) => (
                          <label className="gg-field" key={field}>{label}<input type="number" min={min} max={max} value={policy[field]} onChange={(event) => update(policy.category, field, Number(event.target.value))} /></label>
                        ))}
                      </div>
                      <label className="gg-check"><input type="checkbox" checked={policy.enabled} onChange={(event) => update(policy.category, "enabled", event.target.checked)} /><span>Enforce this policy</span></label>
                      {!policy.enabled && <p className="gg-note gg-note--danger">With enforcement off, this category is not rate limited at all.</p>}
                      <div className="gg-form__actions">
                        {dirty && <button type="button" className="gg-button" onClick={() => setEdits((current) => { const next = { ...current }; delete next[policy.category]; return next })}>Discard</button>}
                        <button type="submit" className="gg-button gg-button--primary" disabled={busy === policy.category || !dirty}><Save size={15} aria-hidden="true" />Save policy</button>
                      </div>
                    </form>
                  </article>
                )
              })}
            </div>
          </Panel>

          <Panel id="abuse-events" eyebrow="Evidence" title="Abuse events">
            <FilterBar options={{ label: "Category", value: category, onChange: setCategory, items: [
              { value: "ALL", label: "All", count: events.length },
              ...categories.map((value) => ({ value, label: formatProtectionCategory(value), count: events.filter((item) => item.category === value).length })),
            ] }} summary={`${visibleEvents.length} of ${events.length} shown`} />
            <DataTable label="Abuse events" columns={eventColumns} rows={visibleEvents} rowKey={(item) => item.event_id} initialSort={{ key: "when", direction: "desc" }}
              rowTone={(item) => (item.severity === "HIGH" || item.severity === "CRITICAL" ? "danger" : undefined)}
              empty={<EmptyState icon={<Activity size={28} />} title="No abuse events recorded" description="GreyGuard has not detected a quota violation, lockout or suspicious burst." />} />
          </Panel>
        </>
      )}
    </section>
  )
}
