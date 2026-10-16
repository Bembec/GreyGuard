import { useQuery } from "@tanstack/react-query"
import { Box, Power, RefreshCw, ShieldCheck, Square } from "lucide-react"
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

type Config = { enabled: boolean; image: string; cpu_limit: number; memory_mb: number; pids_limit: number; timeout_seconds: number; network_mode: string; read_only: boolean; non_root: boolean; capabilities_dropped: string; arbitrary_commands_allowed: boolean }
type Execution = { execution_id: string; job_type: string; status: string; created_at: string; result: string | null }
type Data = { config: Config; history: Execution[] }

export const isolationState = (enabled: boolean) => (enabled ? "ENABLED" : "DISABLED")

const yesNo = (value: boolean) => (value ? "Yes" : "No")

export default function ExecutionIsolationPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const isolation = useQuery({ queryKey: ["execution-isolation"], queryFn: () => adminCall<Data>("/execution-isolation", sessionToken), enabled: Boolean(sessionToken) && administrator?.role === "PLATFORM_ADMIN" })
  const [pending, setPending] = useState<"enable" | "terminate" | null>(null)
  const [busy, setBusy] = useState(false)

  if (administrator?.role !== "PLATFORM_ADMIN") return <Navigate to="/dashboard" replace />

  const config = isolation.data?.config
  const history = isolation.data?.history ?? []

  const confirm = async () => {
    if (!pending || !config) return
    setBusy(true)
    try {
      if (pending === "enable") await adminCall("/execution-isolation", sessionToken, { method: "PUT", body: { ...config, enabled: true } })
      else await adminCall("/execution-isolation/emergency-terminate", sessionToken, { method: "POST" })
      pushToast({ tone: "success", title: "Isolation control updated", message: "Execution evidence has been recorded." })
      setPending(null)
    } catch (error) {
      pushToast({ tone: "error", title: "Operation blocked", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
      await isolation.refetch()
    }
  }

  const columns: Column<Execution>[] = [
    { key: "id", header: "Execution", sortValue: (item) => item.execution_id, render: (item) => <code className="gg-code">{item.execution_id}</code> },
    { key: "job", header: "Job", sortValue: (item) => item.job_type, render: (item) => item.job_type },
    { key: "status", header: "Status", sortValue: (item) => item.status, render: (item) => <StatusBadge value={item.status} /> },
    { key: "result", header: "Result", secondary: true, render: (item) => item.result ?? <span className="gg-muted">None</span> },
    { key: "when", header: "When", sortValue: (item) => item.created_at, render: (item) => <span title={item.created_at}>{relativeTime(item.created_at)}</span> },
  ]

  return (
    <section className="gg-page">
      <PageHeader
        title="Execution isolation"
        icon={<Box size={22} />}
        description="Predefined jobs run in hardened Docker containers with no network by default, no host Docker socket and no extra privileges."
        actions={
          <>
            <button type="button" className="gg-button" onClick={() => void isolation.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>
            {config && <button type="button" className="gg-button gg-button--danger" onClick={() => setPending("terminate")}><Square size={16} aria-hidden="true" />Emergency terminate</button>}
          </>
        }
      />

      <p className="gg-note"><ShieldCheck size={16} aria-hidden="true" /><span><strong>No arbitrary commands.</strong> Only predefined jobs may run. The container receives no host Docker socket, privileges or network access.</span></p>

      <Guidance id="execution-isolation" title="Before enabling isolated execution">
        <ol>
          <li>Check that the image and the security profile below match what your organization has approved.</li>
          <li>Enable the sandbox. Jobs then run only inside these limits, and each one is recorded below.</li>
          <li><strong>Emergency terminate</strong> stops every active isolated job at once.</li>
        </ol>
      </Guidance>

      {isolation.isLoading && <LoadingState label="Loading execution isolation controls" rows={3} />}
      {isolation.isError && <ErrorState message={isolation.error.message} onRetry={() => void isolation.refetch()} />}
      {config && (
        <>
          <StatGrid label="Execution isolation summary">
            <StatCard label="Sandbox execution" value={isolationState(config.enabled)} hint="Disabled until verified" tone={config.enabled ? "warning" : "neutral"} />
            <StatCard label="Network mode" value={config.network_mode.toUpperCase()} hint="For every job" tone={config.network_mode === "none" ? "success" : "warning"} />
            <StatCard label="Resource ceiling" value={`${config.memory_mb} MB`} hint={`${config.cpu_limit} CPU · ${config.pids_limit} processes`} />
            <StatCard label="Executions" value={history.length} hint="Recorded below" tone="info" />
          </StatGrid>

          <Panel id="isolation-boundary" eyebrow="Profile" title="Enforced boundary" actions={!config.enabled && <button type="button" className="gg-button gg-button--primary" onClick={() => setPending("enable")}><Power size={16} aria-hidden="true" />Enable sandbox</button>}>
            <dl className="gg-facts">
              <div><dt>Image</dt><dd>{config.image}</dd></div>
              <div><dt>Non-root user</dt><dd>{yesNo(config.non_root)}</dd></div>
              <div><dt>Read-only root</dt><dd>{yesNo(config.read_only)}</dd></div>
              <div><dt>Capabilities dropped</dt><dd>{config.capabilities_dropped}</dd></div>
              <div><dt>Process limit</dt><dd>{config.pids_limit}</dd></div>
              <div><dt>Timeout</dt><dd>{config.timeout_seconds} s</dd></div>
              <div><dt>Arbitrary commands</dt><dd>{config.arbitrary_commands_allowed ? "Allowed" : "Refused"}</dd></div>
            </dl>
          </Panel>

          <Panel id="isolation-history" eyebrow="Evidence" title="Execution history">
            <DataTable label="Execution history" columns={columns} rows={history} rowKey={(item) => item.execution_id} initialSort={{ key: "when", direction: "desc" }}
              empty={<EmptyState icon={<Box size={28} />} title="No executions yet" description="Each isolated job is recorded here with its result." />} />
          </Panel>
        </>
      )}

      <ConfirmDialog
        open={pending !== null}
        title={pending === "enable" ? "Enable predefined Docker sandbox jobs?" : "Terminate all active isolated jobs?"}
        description={pending === "enable"
          ? "Predefined jobs can then run inside the boundary shown. Each run is recorded."
          : "Every active isolated job is stopped immediately. Their evidence is kept."}
        confirmLabel={pending === "enable" ? "Enable sandbox" : "Terminate all jobs"}
        tone={pending === "enable" ? "warning" : "danger"}
        busy={busy}
        onCancel={() => setPending(null)}
        onConfirm={() => void confirm()}
      />
    </section>
  )
}
