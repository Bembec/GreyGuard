import { useQuery } from "@tanstack/react-query"
import { Fingerprint, Gavel, LockKeyhole, Plus, RefreshCw, ShieldCheck } from "lucide-react"
import { useState } from "react"
import { Navigate } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { DataTable, type Column } from "../components/page/DataTable"
import { Guidance } from "../components/page/Guidance"
import { PageHeader } from "../components/page/PageHeader"
import { Panel } from "../components/page/Panel"
import { StatCard, StatGrid } from "../components/page/StatCard"
import { StatusBadge } from "../components/page/StatusBadge"
import { relativeTime } from "../components/page/timeFormat"
import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { adminCall } from "../lib/adminApi"

type Hold = { hold_id: string; name: string; reason: string; active: boolean; agent_name: string | null; created_at: string }
type Controls = { config: { retention_days: number; immutable_enabled: boolean }; legal_holds: Hold[]; chain_records: number; last_check: { valid: number; checked_at: string; records_checked: number } | null }

export const integrityLabel = (value: number | boolean | undefined) => (value ? "VERIFIED" : "NOT VERIFIED")

type Pending = { kind: "immutable" } | { kind: "release"; hold: Hold }

export default function AuditIntegrityPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const controls = useQuery({ queryKey: ["audit-integrity"], queryFn: () => adminCall<Controls>("/audit-integrity", sessionToken), enabled: Boolean(sessionToken) && Boolean(administrator?.install_operator) })
  const [days, setDays] = useState<number | null>(null)
  const [name, setName] = useState("")
  const [reason, setReason] = useState("")
  const [pending, setPending] = useState<Pending | null>(null)
  const [busy, setBusy] = useState("")

  if (!administrator?.install_operator) return <Navigate to="/dashboard" replace />

  const data = controls.data
  const retentionDays = days ?? data?.config.retention_days ?? 365

  const call = async (key: string, path: string, method = "POST", body?: unknown) => {
    setBusy(key)
    try {
      await adminCall(path, sessionToken, { method, body })
      pushToast({ tone: "success", title: "Audit control updated", message: "Integrity evidence has been recorded." })
      setName(""); setReason(""); setPending(null); setDays(null)
      await controls.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Operation blocked", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy("")
    }
  }

  const holdColumns: Column<Hold>[] = [
    { key: "name", header: "Hold", sortValue: (item) => item.name, render: (item) => <div className="gg-cell-stack"><strong>{item.name}</strong><small>{item.reason}</small></div> },
    { key: "scope", header: "Scope", render: (item) => item.agent_name ?? "All evidence" },
    { key: "state", header: "State", sortValue: (item) => String(item.active), render: (item) => <StatusBadge value={item.active ? "ACTIVE" : "RELEASED"} tone={item.active ? "warning" : "neutral"} /> },
    { key: "created", header: "Created", secondary: true, sortValue: (item) => item.created_at, render: (item) => <span title={item.created_at}>{relativeTime(item.created_at)}</span> },
    { key: "actions", header: "Actions", align: "end", render: (item) => item.active ? <button type="button" className="gg-button" onClick={() => setPending({ kind: "release", hold: item })}>Release</button> : null },
  ]

  return (
    <section className="gg-page">
      <PageHeader
        eyebrow="Audit & Integrity"
        title="Audit integrity"
        icon={<Fingerprint size={22} />}
        description="Install-wide evidence protection: hash-chained audit records, chain verification, retention and legal holds."
        actions={
          <>
            <button type="button" className="gg-button" onClick={() => void controls.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>
            {data && <button type="button" className="gg-button gg-button--primary" disabled={busy === "verify"} onClick={() => void call("verify", "/audit-integrity/verify")}><ShieldCheck size={16} aria-hidden="true" />{busy === "verify" ? "Verifying…" : "Verify complete chain"}</button>}
          </>
        }
      />

      <Guidance id="audit-integrity" title="How evidence is protected">
        <ul>
          <li>Each record is sealed with a hash of its source and of the record before it. <strong>Verify</strong> seals new records and checks every link in the chain.</li>
          <li><strong>Retention</strong> sets how long evidence is kept. Immutable mode cannot be turned off through GreyGuard once enabled.</li>
          <li>A <strong>legal hold</strong> preserves evidence beyond retention until it is released.</li>
        </ul>
      </Guidance>

      {controls.isLoading && <LoadingState label="Loading audit integrity controls" rows={3} />}
      {controls.isError && <ErrorState message={controls.error.message} onRetry={() => void controls.refetch()} />}
      {data && (
        <>
          <StatGrid label="Audit integrity summary">
            <StatCard label="Sealed records" value={data.chain_records} hint="In the hash chain" tone="info" />
            <StatCard label="Last verification" value={integrityLabel(data.last_check?.valid)} hint={data.last_check ? `${data.last_check.records_checked} records · ${relativeTime(data.last_check.checked_at)}` : "Never verified"} tone={data.last_check?.valid ? "success" : "warning"} />
            <StatCard label="Retention" value={`${data.config.retention_days} days`} hint={data.config.immutable_enabled ? "Immutable mode on" : "Immutable mode optional"} tone={data.config.immutable_enabled ? "success" : "neutral"} />
            <StatCard label="Active legal holds" value={data.legal_holds.filter((item) => item.active).length} hint={`${data.legal_holds.length} in total`} tone={data.legal_holds.some((item) => item.active) ? "warning" : "neutral"} />
          </StatGrid>

          <div className="gg-layout gg-layout--even">
            <Panel id="integrity-retention" eyebrow="Retention" title="Retention protection">
              <form className="gg-form" onSubmit={(event) => { event.preventDefault(); void call("retention", "/audit-integrity/retention", "PUT", { retention_days: retentionDays, immutable_enabled: data.config.immutable_enabled }) }}>
                <label className="gg-field">Keep evidence for (days)<input type="number" min="30" max="3650" value={retentionDays} onChange={(event) => setDays(Number(event.target.value))} /><small>Between 30 and 3,650 days.</small></label>
                <div className="gg-form__actions">
                  {!data.config.immutable_enabled && <button type="button" className="gg-button gg-button--danger" onClick={() => setPending({ kind: "immutable" })}><LockKeyhole size={16} aria-hidden="true" />Enable immutable mode</button>}
                  <button type="submit" className="gg-button gg-button--primary" disabled={busy === "retention" || retentionDays === data.config.retention_days}>Save retention</button>
                </div>
              </form>
            </Panel>

            <Panel id="integrity-new-hold" eyebrow="Preservation" title="Create a legal hold">
              <form className="gg-form" onSubmit={(event) => { event.preventDefault(); void call("hold", "/audit-integrity/legal-holds", "POST", { name, reason, agent_name: null, starts_at: null, ends_at: null }) }}>
                <label className="gg-field">Hold name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Matter 2026-014" /></label>
                <label className="gg-field">Reason and preservation purpose<textarea value={reason} onChange={(event) => setReason(event.target.value)} /></label>
                <div className="gg-form__actions"><button type="submit" className="gg-button gg-button--primary" disabled={busy === "hold" || !name.trim() || !reason.trim()}><Plus size={16} aria-hidden="true" />Create hold</button></div>
              </form>
            </Panel>
          </div>

          <Panel id="integrity-holds" eyebrow="Preservation" title="Legal holds">
            <DataTable label="Legal holds" columns={holdColumns} rows={data.legal_holds} rowKey={(item) => item.hold_id} initialSort={{ key: "state", direction: "desc" }}
              empty={<EmptyState icon={<Gavel size={28} />} title="No legal holds" description="Create a hold to preserve evidence beyond its retention period." />} />
          </Panel>
        </>
      )}

      <ConfirmDialog
        open={Boolean(pending)}
        title={pending?.kind === "release" ? `Release ${pending.hold.name}?` : "Enable immutable mode?"}
        description={pending?.kind === "release"
          ? "Evidence under this hold returns to normal retention. The release is recorded."
          : "Immutable mode cannot be disabled through GreyGuard. Evidence can then no longer be deleted before its retention period ends."}
        confirmLabel={pending?.kind === "release" ? "Release hold" : "Enable immutable mode"}
        busy={Boolean(busy)}
        onCancel={() => setPending(null)}
        onConfirm={() => {
          if (pending?.kind === "release") void call("release", `/audit-integrity/legal-holds/${pending.hold.hold_id}/release`)
          else if (data) void call("immutable", "/audit-integrity/retention", "PUT", { retention_days: retentionDays, immutable_enabled: true })
        }}
      />
    </section>
  )
}
