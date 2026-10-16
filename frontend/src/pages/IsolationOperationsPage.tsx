import { useQuery } from "@tanstack/react-query"
import { Boxes, Plus, RefreshCw, ScanSearch, ShieldOff, Trash2, Upload } from "lucide-react"
import { useRef, useState, type ChangeEvent } from "react"
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

type Workspace = { workspace_id: string; agent_name: string; status: string; created_at: string; destroyed_at: string | null }
type Artifact = { artifact_id: string; original_name: string; status: string; sha256: string; scan_engine: string | null; scan_result: string | null }
type Data = { config: { global_kill_switch: boolean; network_enabled: boolean; destination_allowlist: string[]; dns_allowlist: string[] }; workspaces: Workspace[]; artifacts: Artifact[] }

export const workspaceState = (status: string) => (status === "ACTIVE" ? "ACTIVE" : "DESTROYED")

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => { const result = String(reader.result); resolve(result.slice(result.indexOf(",") + 1)) }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

type Pending = { kind: "kill-switch" } | { kind: "destroy"; workspace: Workspace }

export default function IsolationOperationsPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const operations = useQuery({ queryKey: ["isolation-operations"], queryFn: () => adminCall<Data>("/isolation-operations", sessionToken), enabled: Boolean(sessionToken) && administrator?.role === "PLATFORM_ADMIN" })
  const [agent, setAgent] = useState("")
  const [uploadTarget, setUploadTarget] = useState<string | null>(null)
  const [workspaceFilter, setWorkspaceFilter] = useState("ACTIVE")
  const [pending, setPending] = useState<Pending | null>(null)
  const [busy, setBusy] = useState(false)
  const fileInput = useRef<HTMLInputElement | null>(null)

  if (administrator?.role !== "PLATFORM_ADMIN") return <Navigate to="/dashboard" replace />

  const data = operations.data
  const workspaces = data?.workspaces ?? []
  const artifacts = data?.artifacts ?? []
  const visibleWorkspaces = workspaces.filter((item) => workspaceFilter === "ALL" || workspaceState(item.status) === workspaceFilter)

  const call = async (path: string, method = "POST", body?: unknown) => {
    setBusy(true)
    try {
      await adminCall(path, sessionToken, { method, body })
      pushToast({ tone: "success", title: "Isolation operation completed", message: "The operation and evidence were recorded." })
      setAgent(""); setPending(null)
      await operations.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Operation blocked", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  const startUpload = (workspaceId: string) => { setUploadTarget(workspaceId); fileInput.current?.click() }
  const handleFileChosen = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    const workspaceId = uploadTarget
    event.target.value = ""
    setUploadTarget(null)
    if (!file || !workspaceId) return
    const content_base64 = await readFileAsBase64(file)
    await call(`/isolation-operations/workspaces/${workspaceId}/artifacts`, "POST", { filename: file.name, content_base64 })
  }

  const workspaceColumns: Column<Workspace>[] = [
    { key: "agent", header: "Agent", sortValue: (item) => item.agent_name, render: (item) => <div className="gg-cell-stack"><strong>{item.agent_name}</strong><small>{item.workspace_id}</small></div> },
    { key: "state", header: "State", sortValue: (item) => workspaceState(item.status), render: (item) => <StatusBadge value={workspaceState(item.status)} tone={item.status === "ACTIVE" ? "warning" : "neutral"} /> },
    { key: "created", header: "Created", secondary: true, sortValue: (item) => item.created_at, render: (item) => <span title={item.created_at}>{relativeTime(item.created_at)}</span> },
    { key: "actions", header: "Actions", align: "end", render: (item) => item.status === "ACTIVE" ? (
      <div className="gg-row-actions">
        <button type="button" className="gg-button" disabled={busy} onClick={() => startUpload(item.workspace_id)} title="Quarantine an artifact for scanning"><Upload size={14} aria-hidden="true" />Quarantine file</button>
        <button type="button" className="gg-button gg-button--danger" disabled={busy} onClick={() => setPending({ kind: "destroy", workspace: item })} aria-label={`Destroy ${item.agent_name}'s workspace`}><Trash2 size={14} aria-hidden="true" />Destroy</button>
      </div>
    ) : <span className="gg-muted">Destroyed</span> },
  ]
  const artifactColumns: Column<Artifact>[] = [
    { key: "name", header: "Artifact", sortValue: (item) => item.original_name, render: (item) => <div className="gg-cell-stack"><strong>{item.original_name}</strong><small className="gg-code">{item.sha256.slice(0, 16)}…</small></div> },
    { key: "status", header: "Status", sortValue: (item) => item.status, render: (item) => <StatusBadge value={item.status} tone={item.status === "QUARANTINED" ? "warning" : undefined} /> },
    { key: "scan", header: "Scan result", secondary: true, render: (item) => item.scan_result ? `${item.scan_result}${item.scan_engine ? ` (${item.scan_engine})` : ""}` : <span className="gg-muted">Not scanned</span> },
    { key: "actions", header: "Actions", align: "end", render: (item) => item.status === "QUARANTINED"
      ? <button type="button" className="gg-button" disabled={busy} onClick={() => void call(`/isolation-operations/artifacts/${item.artifact_id}/scan`, "POST")}><ScanSearch size={14} aria-hidden="true" />Scan</button>
      : null },
  ]

  return (
    <section className="gg-page">
      <input ref={fileInput} type="file" hidden onChange={(event) => void handleFileChosen(event)} />
      <PageHeader
        title="Isolation operations"
        icon={<Boxes size={22} />}
        description="Per-agent isolated workspaces, artifact quarantine, network boundaries and the global execution kill switch."
        actions={
          <>
            <button type="button" className="gg-button" onClick={() => void operations.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>
            {data && <button type="button" className={data.config.global_kill_switch ? "gg-button" : "gg-button gg-button--danger"} onClick={() => setPending({ kind: "kill-switch" })}><ShieldOff size={16} aria-hidden="true" />{data.config.global_kill_switch ? "Restore admission" : "Activate kill switch"}</button>}
          </>
        }
      />

      {data?.config.global_kill_switch && <p className="gg-note gg-note--danger"><ShieldOff size={16} aria-hidden="true" /><span><strong>Global execution kill switch is active.</strong> No new workspace or isolated job can start.</span></p>}

      <Guidance id="isolation-operations" title="Working with isolated workspaces">
        <ol>
          <li>Create a workspace for a registered agent. It is destroyed after controlled execution, or by you.</li>
          <li>Files brought into a workspace are <strong>quarantined</strong> and never released before scanning. Scanning must be enabled on the server (GREYGUARD_MALWARE_SCANNING_ENABLED).</li>
          <li>The global kill switch blocks every new workspace and job until admission is restored.</li>
        </ol>
      </Guidance>

      {operations.isLoading && <LoadingState label="Loading isolation operations" rows={3} />}
      {operations.isError && <ErrorState message={operations.error.message} onRetry={() => void operations.refetch()} />}
      {data && (
        <>
          <StatGrid label="Isolation operations summary">
            <StatCard label="Execution admission" value={data.config.global_kill_switch ? "Blocked" : "Open"} hint="Global kill switch" tone={data.config.global_kill_switch ? "danger" : "success"} />
            <StatCard label="Active workspaces" value={workspaces.filter((item) => item.status === "ACTIVE").length} hint={`${workspaces.length} in total`} tone="info" />
            <StatCard label="Quarantined files" value={artifacts.filter((item) => item.status === "QUARANTINED").length} hint="Awaiting a scan" tone={artifacts.some((item) => item.status === "QUARANTINED") ? "warning" : "neutral"} />
            <StatCard label="Workspace network" value={data.config.network_enabled ? "Allowlisted" : "None"} hint={`${data.config.destination_allowlist.length} destinations · ${data.config.dns_allowlist.length} DNS names`} tone={data.config.network_enabled ? "warning" : "success"} />
          </StatGrid>

          <Panel id="isolation-workspaces" eyebrow="Workspaces" title="Agent workspaces">
            <form className="gg-form" onSubmit={(event) => { event.preventDefault(); void call("/isolation-operations/workspaces", "POST", { agent_name: agent }) }} style={{ marginBottom: "0.85rem" }}>
              <div className="gg-form__row">
                <label className="gg-field">Registered agent name<input value={agent} onChange={(event) => setAgent(event.target.value)} placeholder="build-agent" /></label>
              </div>
              <div className="gg-form__actions"><button type="submit" className="gg-button gg-button--primary" disabled={busy || !agent.trim() || data.config.global_kill_switch}><Plus size={16} aria-hidden="true" />Create isolated workspace</button></div>
            </form>
            <FilterBar options={{ label: "State", value: workspaceFilter, onChange: setWorkspaceFilter, items: [
              { value: "ACTIVE", label: "Active", count: workspaces.filter((item) => item.status === "ACTIVE").length },
              { value: "DESTROYED", label: "Destroyed", count: workspaces.filter((item) => item.status !== "ACTIVE").length },
              { value: "ALL", label: "All", count: workspaces.length },
            ] }} />
            <DataTable label="Agent workspaces" columns={workspaceColumns} rows={visibleWorkspaces} rowKey={(item) => item.workspace_id} initialSort={{ key: "created", direction: "desc" }}
              empty={<EmptyState icon={<Boxes size={28} />} title={workspaces.length ? "Nothing in this view" : "No workspaces"} description={workspaces.length ? "Change the state filter." : "Create an isolated workspace for a registered agent."} />} />
          </Panel>

          <Panel id="isolation-artifacts" eyebrow="Quarantine" title="Quarantined artifacts">
            <DataTable label="Quarantined artifacts" columns={artifactColumns} rows={artifacts} rowKey={(item) => item.artifact_id}
              rowTone={(item) => (item.status === "QUARANTINED" ? "warning" : undefined)}
              empty={<EmptyState icon={<Upload size={28} />} title="No artifacts" description="Files brought into a workspace are held here until they are scanned." />} />
          </Panel>
        </>
      )}

      <ConfirmDialog
        open={Boolean(pending)}
        title={pending?.kind === "destroy" ? `Destroy ${pending.workspace.agent_name}'s workspace?` : data?.config.global_kill_switch ? "Restore execution admission?" : "Activate the global execution kill switch?"}
        description={pending?.kind === "destroy"
          ? "The workspace and its files are destroyed. The evidence of what ran in it is kept."
          : data?.config.global_kill_switch ? "New workspaces and isolated jobs can start again under the configured controls." : "Every new workspace and isolated job is blocked until admission is restored."}
        confirmLabel={pending?.kind === "destroy" ? "Destroy workspace" : data?.config.global_kill_switch ? "Restore admission" : "Activate kill switch"}
        tone={pending?.kind === "kill-switch" && data?.config.global_kill_switch ? "warning" : "danger"}
        busy={busy}
        onCancel={() => setPending(null)}
        onConfirm={() => {
          if (pending?.kind === "destroy") void call(`/isolation-operations/workspaces/${pending.workspace.workspace_id}`, "DELETE")
          else if (data) void call("/isolation-operations", "PUT", { ...data.config, global_kill_switch: !data.config.global_kill_switch })
        }}
      />
    </section>
  )
}
