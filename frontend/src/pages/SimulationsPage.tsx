import { useQuery } from "@tanstack/react-query"
import { FlaskConical, Play, Power, RefreshCw, ShieldAlert } from "lucide-react"
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
import { relativeTime } from "../components/page/timeFormat"
import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { adminCall } from "../lib/adminApi"

type Scenario = { scenario_id: string; title: string; attempt: string; decision: string; severity: string; risk_added: number; fictional_target: string; operational: boolean }
type Run = Scenario & { run_id: string; simulated: boolean; real_action_executed: boolean; environment_reset: boolean; created_at: string }
type Data = { enabled: boolean; simulation_only: boolean; network_access: boolean; scenarios: Scenario[]; runs: Run[] }

export const simulationBanner = (simulated: boolean) => (simulated ? "SIMULATION ONLY — NO REAL ACTION" : "INVALID RECORD")

export default function SimulationsPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const lab = useQuery({ queryKey: ["simulations"], queryFn: () => adminCall<Data>("/simulations", sessionToken), enabled: Boolean(sessionToken) && administrator?.role === "PLATFORM_ADMIN" })
  const [severity, setSeverity] = useState("ALL")
  const [confirmToggle, setConfirmToggle] = useState(false)
  const [busy, setBusy] = useState("")

  const scenarios = useMemo(() => lab.data?.scenarios ?? [], [lab.data])
  const runs = useMemo(() => lab.data?.runs ?? [], [lab.data])
  const severities = [...new Set(scenarios.map((item) => item.severity))]
  const visible = scenarios.filter((item) => severity === "ALL" || item.severity === severity)

  if (administrator?.role !== "PLATFORM_ADMIN") return <Navigate to="/dashboard" replace />

  const toggleLab = async () => {
    setBusy("lab")
    try {
      await adminCall("/simulations", sessionToken, { method: "PUT", body: { enabled: !lab.data?.enabled } })
      pushToast({ tone: "success", title: lab.data?.enabled ? "Simulation lab disabled" : "Simulation lab enabled", message: "The change was recorded." })
      setConfirmToggle(false)
      await lab.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Change blocked", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy("")
    }
  }

  const run = async (id: string) => {
    setBusy(id)
    try {
      await adminCall("/simulations/run", sessionToken, { method: "POST", body: { scenario_id: id } })
      pushToast({ tone: "success", title: "Safe simulation completed", message: "No real action executed; defensive evidence was preserved." })
      await lab.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Simulation blocked", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy("")
    }
  }

  const scenarioColumns: Column<Scenario>[] = [
    { key: "title", header: "Scenario", sortValue: (item) => item.title, render: (item) => <div className="gg-cell-stack"><strong>{item.title}</strong><small>{item.attempt} · fictional target {item.fictional_target}</small></div> },
    { key: "severity", header: "Severity", sortValue: (item) => item.severity, render: (item) => <StatusBadge value={item.severity} /> },
    { key: "decision", header: "Expected decision", sortValue: (item) => item.decision, render: (item) => <StatusBadge value={item.decision} /> },
    { key: "risk", header: "Risk added", align: "end", secondary: true, sortValue: (item) => item.risk_added, render: (item) => `+${item.risk_added}` },
    { key: "run", header: "Run", align: "end", render: (item) => <button type="button" className="gg-button" disabled={!lab.data?.enabled || busy === item.scenario_id} onClick={() => void run(item.scenario_id)} aria-label={`Run ${item.title}`}><Play size={14} aria-hidden="true" />Run</button> },
  ]
  const runColumns: Column<Run>[] = [
    { key: "title", header: "Scenario", sortValue: (item) => item.title, render: (item) => <strong>{item.title}</strong> },
    { key: "decision", header: "Decision", sortValue: (item) => item.decision, render: (item) => <StatusBadge value={item.decision} /> },
    { key: "label", header: "Record", render: (item) => <StatusBadge value={simulationBanner(item.simulated)} tone={item.simulated ? "info" : "danger"} /> },
    { key: "real", header: "Real action", secondary: true, render: (item) => (item.real_action_executed ? <StatusBadge value="EXECUTED" tone="danger" /> : "None") },
    { key: "when", header: "When", sortValue: (item) => item.created_at, render: (item) => <span title={item.created_at}>{relativeTime(item.created_at)}</span> },
  ]

  return (
    <section className="gg-page">
      <PageHeader
        title="Simulation lab"
        icon={<FlaskConical size={22} />}
        description="Check that GreyGuard detects, refuses, alerts on and records prohibited agent behaviour, using predefined scenarios against fictional targets."
        actions={
          <>
            <button type="button" className="gg-button" onClick={() => void lab.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>
            {lab.data && <button type="button" className={lab.data.enabled ? "gg-button gg-button--danger" : "gg-button gg-button--primary"} onClick={() => setConfirmToggle(true)}><Power size={16} aria-hidden="true" />{lab.data.enabled ? "Disable lab" : "Enable lab"}</button>}
          </>
        }
      />

      <p className="gg-note"><FlaskConical size={16} aria-hidden="true" /><span><strong>Simulation only. No real action is taken.</strong> Fictional targets and predefined outputs, with no filesystem, process or network side effects.</span></p>

      <Guidance id="simulations" title="How to validate a control">
        <ol>
          <li>Enable the lab, then run a scenario. Each one plays a prohibited attempt through the real decision path.</li>
          <li>Check that the decision matches the expected one, and that the alert and risk appear under Live Monitoring and Risk Center.</li>
          <li>Every run is recorded below and labelled as a simulation. Disable the lab when you are done.</li>
        </ol>
      </Guidance>

      {lab.isLoading && <LoadingState label="Loading the simulation lab" rows={3} />}
      {lab.isError && <ErrorState message={lab.error.message} onRetry={() => void lab.refetch()} />}
      {lab.data && (
        <>
          <StatGrid label="Simulation lab summary">
            <StatCard label="Lab" value={lab.data.enabled ? "Enabled" : "Disabled"} hint="Scenarios run only while enabled" tone={lab.data.enabled ? "warning" : "neutral"} />
            <StatCard label="Scenarios" value={scenarios.length} hint="Predefined and non-operational" tone="info" />
            <StatCard label="Runs recorded" value={runs.length} hint={runs[0] ? `Last ${relativeTime(runs[0].created_at)}` : "None yet"} />
            <StatCard label="Network access" value={lab.data.network_access ? "Allowed" : "None"} hint="During simulations" tone={lab.data.network_access ? "danger" : "success"} />
          </StatGrid>

          <Panel id="simulation-scenarios" eyebrow="Scenarios" title="Prohibited-capability scenarios">
            <FilterBar options={{ label: "Severity", value: severity, onChange: setSeverity, items: [{ value: "ALL", label: "All", count: scenarios.length }, ...severities.map((value) => ({ value, label: value, count: scenarios.filter((item) => item.severity === value).length }))] }} summary={lab.data.enabled ? `${visible.length} of ${scenarios.length} shown` : "Enable the lab to run scenarios"} />
            <DataTable label="Simulation scenarios" columns={scenarioColumns} rows={visible} rowKey={(item) => item.scenario_id}
              empty={<EmptyState icon={<ShieldAlert size={28} />} title="No scenarios" description="No predefined scenarios are registered." />} />
          </Panel>

          <Panel id="simulation-runs" eyebrow="Evidence" title="Simulation runs">
            <DataTable label="Simulation runs" columns={runColumns} rows={runs} rowKey={(item) => item.run_id} initialSort={{ key: "when", direction: "desc" }}
              empty={<EmptyState icon={<FlaskConical size={28} />} title="No runs yet" description="Run a scenario to record its evidence here." />} />
          </Panel>
        </>
      )}

      <ConfirmDialog
        open={confirmToggle}
        title={lab.data?.enabled ? "Disable the simulation lab?" : "Enable the simulation lab?"}
        description={lab.data?.enabled ? "No scenario can run until the lab is enabled again." : "Administrators can then run predefined, non-operational scenarios. Each run is recorded as a simulation."}
        confirmLabel={lab.data?.enabled ? "Disable lab" : "Enable lab"}
        tone="warning"
        busy={busy === "lab"}
        onCancel={() => setConfirmToggle(false)}
        onConfirm={() => void toggleLab()}
      />
    </section>
  )
}
