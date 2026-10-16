import { useQuery } from "@tanstack/react-query"
import { GlobeLock, Power, RefreshCw, ShieldCheck } from "lucide-react"
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

type Connector = { connector_id: string; name: string; owner: string; enabled: boolean; visible_indicator: boolean; domains: string[]; purpose: string }
type ResponsePlan = { response_id: string; action: string; target: string; reason: string; status: string; expires_at: string; evidence_preserved: boolean }
type Data = { browser_connectors: Connector[]; responses: ResponsePlan[]; hack_back: boolean }

export const responseTone = (status: string) => (status === "APPROVED" ? "approved" : status === "PENDING_APPROVAL" ? "pending" : "closed")

const BADGE_TONE = { approved: "success", pending: "warning", closed: "neutral" } as const

type Pending = { kind: "connector"; item: Connector } | { kind: "response"; item: ResponsePlan }

export default function DefensiveIntegrationsPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const overview = useQuery({ queryKey: ["defensive-integrations"], queryFn: () => adminCall<Data>("/defensive-integrations", sessionToken), enabled: Boolean(sessionToken) && administrator?.role === "PLATFORM_ADMIN" })
  const [filter, setFilter] = useState("PENDING_APPROVAL")
  const [pending, setPending] = useState<Pending | null>(null)
  const [busy, setBusy] = useState(false)

  const responses = useMemo(() => overview.data?.responses ?? [], [overview.data])
  const connectors = overview.data?.browser_connectors ?? []
  const visibleResponses = responses.filter((item) => filter === "ALL" || item.status === filter)

  if (administrator?.role !== "PLATFORM_ADMIN") return <Navigate to="/dashboard" replace />

  const confirm = async () => {
    if (!pending) return
    setBusy(true)
    try {
      if (pending.kind === "connector") {
        await adminCall(`/defensive-integrations/browser-connectors/${pending.item.connector_id}`, sessionToken, { method: "PUT", body: { enabled: !pending.item.enabled } })
        pushToast({ tone: "success", title: "Connector updated", message: "The connector state was recorded." })
      } else {
        await adminCall(`/defensive-integrations/responses/${pending.item.response_id}/approve`, sessionToken, { method: "POST" })
        pushToast({ tone: "success", title: "Response approved", message: "Controlled-adapter execution may now proceed." })
      }
      setPending(null)
      await overview.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: pending.kind === "connector" ? "Change blocked" : "Approval blocked", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  const responseColumns: Column<ResponsePlan>[] = [
    { key: "action", header: "Response", sortValue: (item) => item.action, render: (item) => <div className="gg-cell-stack"><strong>{item.action.replaceAll("_", " ")}</strong><small>{item.reason}</small></div> },
    { key: "target", header: "Target", sortValue: (item) => item.target, render: (item) => <code className="gg-code">{item.target}</code> },
    { key: "status", header: "Status", sortValue: (item) => item.status, render: (item) => <StatusBadge value={item.status} tone={BADGE_TONE[responseTone(item.status)]} /> },
    { key: "expires", header: "Expires", secondary: true, sortValue: (item) => item.expires_at, render: (item) => new Date(item.expires_at).toLocaleString() },
    { key: "evidence", header: "Evidence", secondary: true, render: (item) => (item.evidence_preserved ? "Preserved" : <StatusBadge value="NOT PRESERVED" tone="danger" />) },
    { key: "actions", header: "Decision", align: "end", render: (item) => item.status === "PENDING_APPROVAL"
      ? <button type="button" className="gg-button gg-button--primary" onClick={() => setPending({ kind: "response", item })}>Approve</button>
      : <span className="gg-muted">No action</span> },
  ]
  const connectorColumns: Column<Connector>[] = [
    { key: "name", header: "Connector", sortValue: (item) => item.name, render: (item) => <div className="gg-cell-stack"><strong>{item.name}</strong><small>{item.purpose}</small></div> },
    { key: "domains", header: "Domains", render: (item) => item.domains.join(", ") },
    { key: "owner", header: "Owner", secondary: true, sortValue: (item) => item.owner, render: (item) => item.owner },
    { key: "state", header: "State", sortValue: (item) => String(item.enabled), render: (item) => <StatusBadge value={item.enabled ? "CONNECTED" : "DISCONNECTED"} tone={item.enabled ? "warning" : "neutral"} /> },
    { key: "actions", header: "Actions", align: "end", render: (item) => <button type="button" className="gg-button" onClick={() => setPending({ kind: "connector", item })} aria-label={`${item.enabled ? "Disconnect" : "Connect"} ${item.name}`}><Power size={14} aria-hidden="true" />{item.enabled ? "Disconnect" : "Connect"}</button> },
  ]

  return (
    <section className="gg-page">
      <PageHeader
        title="Defensive integrations"
        icon={<ShieldCheck size={22} />}
        description="Permissioned browser connectors, and defensive response plans that need a human's approval, expire on their own and can always be reversed."
        actions={<button type="button" className="gg-button" onClick={() => void overview.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <p className="gg-note gg-note--warning"><ShieldCheck size={16} aria-hidden="true" /><span><strong>Hack-back and irreversible retaliation are unavailable.</strong> Every response preserves evidence, expires automatically and requires recovery.</span></p>

      <Guidance id="defensive-integrations" title="How a defensive response is approved">
        <ol>
          <li>A response plan arrives as <strong>pending approval</strong>, with its target, reason and expiry.</li>
          <li>Approve it only if the target and action are right. Execution then runs through a controlled adapter.</li>
          <li>The response ends at its expiry time, and its evidence is kept.</li>
        </ol>
      </Guidance>

      {overview.isLoading && <LoadingState label="Loading defensive integrations" rows={3} />}
      {overview.isError && <ErrorState message={overview.error.message} onRetry={() => void overview.refetch()} />}
      {overview.data && (
        <>
          <StatGrid label="Defensive integrations summary">
            <StatCard label="Awaiting approval" value={responses.filter((item) => item.status === "PENDING_APPROVAL").length} hint="Response plans" tone={responses.some((item) => item.status === "PENDING_APPROVAL") ? "warning" : "success"} />
            <StatCard label="Approved responses" value={responses.filter((item) => item.status === "APPROVED").length} hint="Running until expiry" tone="info" />
            <StatCard label="Connected browsers" value={connectors.filter((item) => item.enabled).length} hint={`of ${connectors.length} connectors`} />
            <StatCard label="Hack-back" value={overview.data.hack_back ? "Available" : "Unavailable"} hint="By design" tone={overview.data.hack_back ? "danger" : "success"} />
          </StatGrid>

          <Panel id="defensive-responses" eyebrow="Needs a decision" title="Defensive response plans">
            <FilterBar options={{ label: "Status", value: filter, onChange: setFilter, items: [
              { value: "PENDING_APPROVAL", label: "Pending", count: responses.filter((item) => item.status === "PENDING_APPROVAL").length },
              { value: "APPROVED", label: "Approved", count: responses.filter((item) => item.status === "APPROVED").length },
              { value: "ALL", label: "All", count: responses.length },
            ] }} summary={`${visibleResponses.length} of ${responses.length} shown`} />
            <DataTable label="Defensive response plans" columns={responseColumns} rows={visibleResponses} rowKey={(item) => item.response_id}
              rowTone={(item) => (item.status === "PENDING_APPROVAL" ? "warning" : undefined)}
              empty={<EmptyState icon={<ShieldCheck size={28} />} title={responses.length ? "Nothing in this view" : "No response plans"} description={responses.length ? "Change the status filter." : "Response plans proposed by integrations appear here for approval."} />} />
          </Panel>

          <Panel id="defensive-connectors" eyebrow="Connectors" title="Browser connectors">
            <DataTable label="Browser connectors" columns={connectorColumns} rows={connectors} rowKey={(item) => item.connector_id}
              empty={<EmptyState icon={<GlobeLock size={28} />} title="No browser connectors" description="Registered browser connectors appear here." />} />
          </Panel>
        </>
      )}

      <ConfirmDialog
        open={Boolean(pending)}
        title={pending?.kind === "response" ? "Approve this defensive response?" : `${pending?.item && "enabled" in pending.item && pending.item.enabled ? "Disconnect" : "Connect"} this browser connector?`}
        description={pending?.kind === "response"
          ? `${pending.item.action.replaceAll("_", " ")} against ${pending.item.target}. It runs through a controlled adapter and expires ${new Date(pending.item.expires_at).toLocaleString()}.`
          : "The connector's state changes at once and the change is recorded."}
        confirmLabel={pending?.kind === "response" ? "Approve response" : "Confirm"}
        tone="warning"
        busy={busy}
        onCancel={() => setPending(null)}
        onConfirm={() => void confirm()}
      />
    </section>
  )
}
