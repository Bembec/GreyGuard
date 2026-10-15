import { useQuery } from "@tanstack/react-query"
import { CalendarClock, ShieldCheck, Trash2 } from "lucide-react"
import { useState } from "react"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { DataTable, type Column } from "../components/page/DataTable"
import { Panel } from "../components/page/Panel"
import { StatusBadge } from "../components/page/StatusBadge"
import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { adminCall } from "../lib/adminApi"

type Schedule = { schedule_id: string; title: string; frequency: string; enabled: boolean; next_run_at: string }
type Mapping = { framework: string; control: string; evidence: string }
type Overview = { schedules: Schedule[]; control_mapping: Mapping[]; retention: { data_sets: Array<{ data_set: string; records: number }> } }

export const scheduleState = (enabled: boolean) => (enabled ? "ACTIVE" : "DISABLED")

export default function ReportGovernancePanel() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const isPlatformAdmin = administrator?.role === "PLATFORM_ADMIN"
  const governance = useQuery({ queryKey: ["report-governance"], queryFn: () => adminCall<Overview>("/report-governance", sessionToken), enabled: Boolean(sessionToken) })
  const [title, setTitle] = useState("Weekly security evidence")
  const [nextRun, setNextRun] = useState("")
  const [disabling, setDisabling] = useState<Schedule | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async (action: () => Promise<unknown>, success: string, failure: string) => {
    setBusy(true)
    try {
      await action()
      pushToast({ tone: "success", title: success, message: "The change was recorded." })
      setDisabling(null)
      await governance.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: failure, message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  const scheduleColumns: Column<Schedule>[] = [
    { key: "title", header: "Report", sortValue: (item) => item.title, render: (item) => <div className="gg-cell-stack"><strong>{item.title}</strong><small>{item.frequency.toLowerCase()}</small></div> },
    { key: "next", header: "Next run", sortValue: (item) => item.next_run_at, render: (item) => new Date(item.next_run_at).toLocaleString() },
    { key: "state", header: "State", sortValue: (item) => String(item.enabled), render: (item) => <StatusBadge value={scheduleState(item.enabled)} tone={item.enabled ? "success" : "neutral"} /> },
    { key: "actions", header: "", align: "end", render: (item) => item.enabled && isPlatformAdmin
      ? <button type="button" className="gg-button" onClick={() => setDisabling(item)} aria-label={`Disable ${item.title} schedule`}><Trash2 size={14} aria-hidden="true" />Disable</button>
      : null },
  ]
  const mappingColumns: Column<Mapping>[] = [
    { key: "control", header: "Framework control", sortValue: (item) => `${item.framework} ${item.control}`, render: (item) => <strong>{item.framework} · {item.control}</strong> },
    { key: "evidence", header: "GreyGuard evidence", render: (item) => item.evidence },
  ]

  return (
    <Panel id="report-governance" eyebrow="Governance" title="Scheduled reports and control mappings">
      <div className="gg-form">
        {isPlatformAdmin && (
          <form className="gg-form__row" onSubmit={(event) => { event.preventDefault(); void run(() => adminCall("/report-governance/schedules", sessionToken, { method: "POST", body: { title, frequency: "WEEKLY", next_run_at: new Date(nextRun).toISOString() } }), "Report scheduled", "Schedule rejected") }}>
            <label className="gg-field">Schedule title<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
            <label className="gg-field">First run<input type="datetime-local" value={nextRun} onChange={(event) => setNextRun(event.target.value)} /></label>
            <div className="gg-form__actions" style={{ alignItems: "flex-end" }}><button type="submit" className="gg-button gg-button--primary" disabled={busy || !nextRun}><CalendarClock size={16} aria-hidden="true" />Schedule weekly</button></div>
          </form>
        )}
        {governance.isLoading && <LoadingState label="Loading report governance" rows={3} />}
        {governance.isError && <ErrorState message={governance.error.message} onRetry={() => void governance.refetch()} />}
        {governance.data && (
          <div className="gg-layout gg-layout--even">
            <div>
              <h3 className="identity-subheading">Scheduled reports</h3>
              <DataTable label="Scheduled reports" columns={scheduleColumns} rows={governance.data.schedules} rowKey={(item) => item.schedule_id}
                empty={<EmptyState icon={<CalendarClock size={28} />} title="No scheduled reports" description="Schedule a weekly evidence report to have it generated automatically." />} />
            </div>
            <div>
              <h3 className="identity-subheading"><ShieldCheck size={14} aria-hidden="true" /> Compliance mappings</h3>
              <DataTable label="Compliance mappings" columns={mappingColumns} rows={governance.data.control_mapping} rowKey={(item) => `${item.framework}-${item.control}`}
                empty={<p className="gg-muted">No control mappings.</p>} />
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={Boolean(disabling)}
        title={`Disable ${disabling?.title ?? "this schedule"}?`}
        description="No further reports are generated on this schedule. Reports already produced are kept."
        confirmLabel="Disable schedule"
        tone="warning"
        busy={busy}
        onCancel={() => setDisabling(null)}
        onConfirm={() => disabling && void run(() => adminCall(`/report-governance/schedules/${disabling.schedule_id}`, sessionToken, { method: "DELETE" }), "Schedule disabled", "Change rejected")}
      />
    </Panel>
  )
}
