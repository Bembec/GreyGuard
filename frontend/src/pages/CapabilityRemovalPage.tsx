import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, CheckCircle2, RefreshCw, ShieldOff } from "lucide-react"
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
import { relativeTime } from "../components/page/timeFormat"
import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { adminCall } from "../lib/adminApi"
import "../styles/capability-removal.css"

type Step = { step_order: number; step_name: string; status: string; evidence: string | null }
type Removal = { removal_id: string; capability: string; reason: string; status: string; emergency: boolean; created_at: string; steps: Step[] }

export const removalProgress = (steps: Pick<Step, "status">[]) => ({ completed: steps.filter((item) => item.status === "COMPLETED").length, total: steps.length })

const isOpen = (item: Removal) => item.steps.some((step) => step.status === "PENDING")

export default function CapabilityRemovalPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const removals = useQuery({ queryKey: ["capability-removals"], queryFn: () => adminCall<{ removals: Removal[] }>("/capability-removals", sessionToken), enabled: Boolean(sessionToken) && administrator?.role === "PLATFORM_ADMIN" })
  const [reason, setReason] = useState("")
  const [evidence, setEvidence] = useState<Record<string, string>>({})
  const [filter, setFilter] = useState("OPEN")
  const [confirmShutdown, setConfirmShutdown] = useState(false)
  const [busy, setBusy] = useState(false)

  const items = useMemo(() => removals.data?.removals ?? [], [removals.data])
  const openItems = items.filter(isOpen)
  const visible = items.filter((item) => filter === "ALL" || (filter === "OPEN" ? isOpen(item) : !isOpen(item)))

  if (administrator?.role !== "PLATFORM_ADMIN") return <Navigate to="/dashboard" replace />

  const emergency = async () => {
    setBusy(true)
    try {
      const result = await adminCall<{ capabilities_fail_closed: number }>("/capability-removals/actions/emergency-shutdown", sessionToken, { method: "POST", body: { reason } })
      pushToast({ tone: "success", title: "Emergency shutdown initiated", message: `${result.capabilities_fail_closed} capabilities were fail-closed.` })
      setReason(""); setConfirmShutdown(false)
      await removals.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Shutdown rejected", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  const complete = async (item: Removal, step: Step) => {
    setBusy(true)
    try {
      await adminCall(`/capability-removals/${item.removal_id}/steps`, sessionToken, { method: "POST", body: { step_name: step.step_name, evidence: evidence[item.removal_id] ?? "" } })
      pushToast({ tone: "success", title: "Evidence recorded", message: "The ordered removal workflow advanced." })
      setEvidence({ ...evidence, [item.removal_id]: "" })
      await removals.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Step rejected", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="gg-page">
      <PageHeader
        title="Capability removal"
        icon={<ShieldOff size={22} />}
        description="Retire a high-risk capability safely: fail it closed first, keep the evidence, then complete each recovery step in order with proof."
        actions={<button type="button" className="gg-button" onClick={() => void removals.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <Guidance id="capability-removal" title="How a removal workflow runs">
        <ol>
          <li>A removal opens with the capability already fail-closed, so nothing can use it while work continues.</li>
          <li>Each step must be completed in order, and each needs evidence: a command, ticket, checksum or validation result.</li>
          <li>Audit evidence is never deleted automatically. An emergency shutdown opens a workflow for every registered high-risk capability at once.</li>
        </ol>
      </Guidance>

      <Panel id="removal-emergency" eyebrow="Emergency" title="Fail-close every high-risk capability" className="removal-emergency">
        <div className="gg-form">
          <p className="gg-note gg-note--danger"><AlertTriangle size={16} aria-hidden="true" />Every registered high-risk capability is disabled at once, and an audited removal workflow opens for each one. Use this only when a capability may be compromised.</p>
          <label className="gg-field">Emergency reason<input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="State the reason (at least 8 characters)" /></label>
          <div className="gg-form__actions"><button type="button" className="gg-button gg-button--danger" disabled={reason.trim().length < 8} onClick={() => setConfirmShutdown(true)}><ShieldOff size={16} aria-hidden="true" />Fail-close all</button></div>
        </div>
      </Panel>

      {removals.isLoading && <LoadingState label="Loading capability removals" rows={3} />}
      {removals.isError && <ErrorState message={removals.error.message} onRetry={() => void removals.refetch()} />}
      {removals.data && (
        <>
          <StatGrid label="Removal summary">
            <StatCard label="Open workflows" value={openItems.length} hint="Steps still pending" tone={openItems.length ? "warning" : "success"} />
            <StatCard label="Completed" value={items.length - openItems.length} hint="Every step evidenced" tone="success" />
            <StatCard label="Emergency removals" value={items.filter((item) => item.emergency).length} hint="Opened by a shutdown" tone={items.some((item) => item.emergency) ? "danger" : "neutral"} />
          </StatGrid>

          <Panel id="removal-list" eyebrow="Workflows" title="Removal workflows">
            <FilterBar options={{ label: "Status", value: filter, onChange: setFilter, items: [
              { value: "OPEN", label: "Open", count: openItems.length },
              { value: "DONE", label: "Completed", count: items.length - openItems.length },
              { value: "ALL", label: "All", count: items.length },
            ] }} summary={`${visible.length} of ${items.length} shown`} />
            {visible.length === 0
              ? <EmptyState icon={<CheckCircle2 size={28} />} title={items.length ? "Nothing in this view" : "No removal workflows"} description={items.length ? "Change the status filter to see other workflows." : "No capability removal has been opened."} />
              : (
                <div className="removal-list">
                  {visible.map((item) => {
                    const progress = removalProgress(item.steps)
                    const next = item.steps.find((step) => step.status === "PENDING")
                    return (
                      <article key={item.removal_id}>
                        <header>
                          <div>
                            <span>{item.emergency ? "Emergency" : "Planned"} · opened {relativeTime(item.created_at)}</span>
                            <h3>{item.capability.replaceAll("_", " ")}</h3>
                            <p>{item.reason}</p>
                          </div>
                          <StatusBadge value={item.status} />
                        </header>
                        <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={progress.total} aria-valuenow={progress.completed} aria-label={`${item.capability} removal progress`}><span style={{ width: `${progress.total ? (progress.completed / progress.total) * 100 : 0}%` }} /></div>
                        <small>{progress.completed} of {progress.total} controls verified</small>
                        <ol>
                          {item.steps.map((step) => (
                            <li className={step.status.toLowerCase()} key={step.step_name}>
                              {step.status === "COMPLETED" ? <CheckCircle2 size={15} aria-label="Completed" /> : <span>{step.step_order}</span>}
                              <div><strong>{step.step_name.replaceAll("_", " ")}</strong>{step.evidence && <small>{step.evidence}</small>}</div>
                            </li>
                          ))}
                        </ol>
                        {next && (
                          <div className="next-step gg-form">
                            <label className="gg-field">Evidence for {next.step_name.replaceAll("_", " ")}
                              <textarea value={evidence[item.removal_id] ?? ""} onChange={(event) => setEvidence({ ...evidence, [item.removal_id]: event.target.value })} placeholder="Record the command, ticket, checksum, validation result or other evidence" />
                            </label>
                            <div className="gg-form__actions"><button type="button" className="gg-button gg-button--primary" disabled={busy || (evidence[item.removal_id] ?? "").trim().length < 5} onClick={() => void complete(item, next)}>Complete next step</button></div>
                          </div>
                        )}
                      </article>
                    )
                  })}
                </div>
              )}
          </Panel>
        </>
      )}

      <ConfirmDialog
        open={confirmShutdown}
        title="Fail-close every high-risk capability now?"
        description="Every registered high-risk capability is disabled immediately and a removal workflow opens for each. This is audited and cannot be undone from this page."
        confirmLabel="Fail-close all"
        busy={busy}
        onCancel={() => setConfirmShutdown(false)}
        onConfirm={() => void emergency()}
      />
    </section>
  )
}
