import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, CalendarClock, RefreshCw, ShieldCheck, X } from "lucide-react"
import { useMemo, useRef, useState } from "react"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { DataTable, type Column } from "../components/page/DataTable"
import { FilterBar } from "../components/page/FilterBar"
import { Guidance } from "../components/page/Guidance"
import { PageHeader } from "../components/page/PageHeader"
import { Panel } from "../components/page/Panel"
import { StatCard, StatGrid } from "../components/page/StatCard"
import { StatusBadge } from "../components/page/StatusBadge"
import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { useDismissableLayer } from "../hooks/useDismissableLayer"
import { adminCall } from "../lib/adminApi"

type Risk = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
type Threat = { threat_id: string; title: string; status: string; severity: Risk; asset: string; threat_actor: string; attack_path: string; existing_controls: string[]; residual_risk: Risk; test_evidence: string[]; incident_response: string; owner: string; review_date: string | null; overdue: boolean }
type Summary = { total: number; needs_review: number; critical: number; high_residual_risk: number; overdue: number }

export const riskRank = (risk: Risk) => ({ LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 })[risk]

const STATUSES = ["NEEDS_REVIEW", "OPEN", "MONITORED", "MITIGATED", "ACCEPTED"]
const RISKS: Risk[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

export default function ThreatRegisterPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const canEdit = administrator?.role === "PLATFORM_ADMIN"
  const register = useQuery({ queryKey: ["threat-register"], queryFn: () => adminCall<{ threats: Threat[]; summary: Summary }>("/threat-register", sessionToken), enabled: Boolean(sessionToken) })
  const [selected, setSelected] = useState<Threat | null>(null)
  const [filter, setFilter] = useState("ALL")
  const [search, setSearch] = useState("")
  const [busy, setBusy] = useState(false)
  const closeRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useDismissableLayer<HTMLDivElement>({ open: Boolean(selected), onClose: () => setSelected(null), trapFocus: true, initialFocusRef: closeRef, lockBodyScroll: true })

  const items = useMemo(() => register.data?.threats ?? [], [register.data])
  const summary = register.data?.summary
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return items.filter((item) => (filter === "ALL" || item.status === filter)
      && (!needle || `${item.title} ${item.asset} ${item.owner} ${item.threat_actor}`.toLowerCase().includes(needle)))
  }, [items, filter, search])

  const save = async () => {
    if (!selected) return
    setBusy(true)
    try {
      await adminCall(`/threat-register/${selected.threat_id}`, sessionToken, { method: "PUT", body: selected })
      pushToast({ tone: "success", title: "Threat review saved", message: "Risk ownership and evidence history were updated." })
      setSelected(null)
      await register.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Review rejected", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  const columns: Column<Threat>[] = [
    { key: "title", header: "Threat", sortValue: (item) => item.title, render: (item) => <div className="gg-cell-stack"><strong>{item.title}</strong><small>{item.asset}</small></div> },
    { key: "severity", header: "Severity", sortValue: (item) => riskRank(item.severity), render: (item) => <StatusBadge value={item.severity} /> },
    { key: "residual", header: "Residual", sortValue: (item) => riskRank(item.residual_risk), render: (item) => <StatusBadge value={item.residual_risk} /> },
    { key: "status", header: "Status", sortValue: (item) => item.status, render: (item) => <StatusBadge value={item.status} /> },
    { key: "owner", header: "Owner", secondary: true, sortValue: (item) => item.owner, render: (item) => item.owner },
    { key: "review", header: "Review by", secondary: true, sortValue: (item) => item.review_date, render: (item) => item.review_date ? <span>{item.review_date}{item.overdue && <> <StatusBadge value="OVERDUE" tone="danger" /></>}</span> : <span className="gg-muted">Not scheduled</span> },
    { key: "actions", header: canEdit ? "Review" : "", align: "end", render: (item) => canEdit
      ? <button type="button" className="gg-button" onClick={() => setSelected({ ...item })} aria-label={`Review ${item.title}`}>Review</button>
      : null },
  ]

  return (
    <section className="gg-page">
      <PageHeader
        title="Threat register"
        icon={<ShieldCheck size={22} />}
        description="Each threat's attack path, controls, test evidence, owner, residual risk and next review date, kept as reviewed security governance."
        actions={<button type="button" className="gg-button" onClick={() => void register.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <Guidance id="threat-register" title="How a threat is reviewed">
        <ol>
          <li>Review threats marked <strong>needs review</strong> or overdue first.</li>
          <li>Record the controls in place and the evidence that tests them, then set the residual risk and the next review date.</li>
          <li>A threat can be marked mitigated or accepted only with controls, test evidence and a review date.</li>
        </ol>
        {!canEdit && <p>Your role has read-only access to the register.</p>}
      </Guidance>

      {register.isLoading && <LoadingState label="Loading the threat register" rows={3} />}
      {register.isError && <ErrorState message={register.error.message} onRetry={() => void register.refetch()} />}
      {register.data && (
        <>
          <StatGrid label="Threat register summary">
            <StatCard label="Registered threats" value={summary?.total ?? 0} hint={`${summary?.critical ?? 0} critical`} tone="info" />
            <StatCard label="Need review" value={summary?.needs_review ?? 0} hint="Awaiting a reviewer" tone={summary?.needs_review ? "warning" : "success"} />
            <StatCard label="High residual risk" value={summary?.high_residual_risk ?? 0} hint="After current controls" tone={summary?.high_residual_risk ? "danger" : "success"} />
            <StatCard label="Overdue reviews" value={summary?.overdue ?? 0} hint="Past their review date" tone={summary?.overdue ? "danger" : "success"} />
          </StatGrid>

          <Panel id="threat-list" eyebrow="Register" title="Threats">
            <FilterBar
              search={{ value: search, onChange: setSearch, placeholder: "Search threat, asset, owner or actor" }}
              options={{ label: "Status", value: filter, onChange: setFilter, items: [
                { value: "ALL", label: "All", count: items.length },
                ...STATUSES.map((value) => ({ value, label: value.replaceAll("_", " ").toLowerCase().replace(/^./, (c) => c.toUpperCase()), count: items.filter((item) => item.status === value).length })),
              ] }}
              summary={`${visible.length} of ${items.length} shown`}
            />
            <DataTable label="Threats" columns={columns} rows={visible} rowKey={(item) => item.threat_id}
              initialSort={{ key: "residual", direction: "desc" }}
              rowTone={(item) => (item.overdue ? "danger" : item.status === "NEEDS_REVIEW" ? "warning" : undefined)}
              empty={<EmptyState icon={<ShieldCheck size={28} />} title={items.length ? "No matching threats" : "No threats registered"} description={items.length ? "Change the search or status filter." : "Registered threats appear here for review."} />} />
          </Panel>
        </>
      )}

      {selected && (
        <div ref={dialogRef} className="gg-dialog" role="dialog" aria-modal="true" aria-label="Threat review">
          <form className="gg-dialog__panel gg-form" onSubmit={(event) => { event.preventDefault(); void save() }}>
            <header className="gg-dialog__header">
              <div><p className="gg-panel__eyebrow">{selected.threat_id}</p><h2>{selected.title}</h2></div>
              <button ref={closeRef} type="button" className="gg-button" onClick={() => setSelected(null)} aria-label="Close review"><X size={16} aria-hidden="true" />Close</button>
            </header>
            <div className="gg-form__row">
              <label className="gg-field">Status<select value={selected.status} onChange={(event) => setSelected({ ...selected, status: event.target.value })}>{STATUSES.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label>
              <label className="gg-field">Severity<select value={selected.severity} onChange={(event) => setSelected({ ...selected, severity: event.target.value as Risk })}>{RISKS.map((value) => <option key={value}>{value}</option>)}</select></label>
              <label className="gg-field">Residual risk<select value={selected.residual_risk} onChange={(event) => setSelected({ ...selected, residual_risk: event.target.value as Risk })}>{RISKS.map((value) => <option key={value}>{value}</option>)}</select></label>
              <label className="gg-field">Review date<input type="date" value={selected.review_date ?? ""} onChange={(event) => setSelected({ ...selected, review_date: event.target.value || null })} /></label>
            </div>
            <div className="gg-form__row">
              <label className="gg-field">Asset<input value={selected.asset} onChange={(event) => setSelected({ ...selected, asset: event.target.value })} /></label>
              <label className="gg-field">Threat actor<input value={selected.threat_actor} onChange={(event) => setSelected({ ...selected, threat_actor: event.target.value })} /></label>
              <label className="gg-field">Owner<input value={selected.owner} onChange={(event) => setSelected({ ...selected, owner: event.target.value })} /></label>
            </div>
            <label className="gg-field">Attack path<textarea value={selected.attack_path} onChange={(event) => setSelected({ ...selected, attack_path: event.target.value })} /></label>
            <label className="gg-field">Existing controls<small>One per line.</small><textarea value={selected.existing_controls.join("\n")} onChange={(event) => setSelected({ ...selected, existing_controls: event.target.value.split("\n").filter(Boolean) })} /></label>
            <label className="gg-field">Test evidence<small>One reference per line.</small><textarea value={selected.test_evidence.join("\n")} onChange={(event) => setSelected({ ...selected, test_evidence: event.target.value.split("\n").filter(Boolean) })} /></label>
            <label className="gg-field">Incident response<textarea value={selected.incident_response} onChange={(event) => setSelected({ ...selected, incident_response: event.target.value })} /></label>
            <p className="gg-note gg-note--warning"><AlertTriangle size={16} aria-hidden="true" />Mitigated or accepted risks require controls, test evidence and a review date.</p>
            <div className="gg-form__actions">
              {selected.overdue && <span className="gg-muted" style={{ marginRight: "auto", fontSize: "0.74rem" }}><CalendarClock size={13} aria-hidden="true" /> Review overdue</span>}
              <button type="button" className="gg-button" onClick={() => setSelected(null)}>Cancel</button>
              <button type="submit" className="gg-button gg-button--primary" disabled={busy}>Save reviewed threat</button>
            </div>
          </form>
        </div>
      )}
    </section>
  )
}
