import { useQuery } from "@tanstack/react-query"
import { Building2, Check, KeyRound, Plus, RefreshCw, ShieldAlert, X } from "lucide-react"
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

type Provider = { provider_id: string; name: string; issuer: string; enabled: boolean; allowed_domains: string[] }
type Mapping = { mapping_id: string; claim_name: string; claim_value: string; greyguard_role: string }
type Workload = { workload_id: string; name: string; subject: string; status: string; expires_at: string; agent_name: string | null; last_authenticated_at: string | null }
type Elevation = { elevation_id: string; requested_role: string; reason: string; status: string; expires_at: string }
type Overview = { summary: { providers: number; workload_identities: number; pending_elevations: number; active_break_glass: number }; providers: Provider[]; mappings: Mapping[]; workloads: Workload[]; elevations: Elevation[] }

export const enterprisePosture = (summary: Overview["summary"]) =>
  summary.active_break_glass > 0 ? "Emergency access active" : summary.pending_elevations > 0 ? "Approval required" : "Controlled"

const EMPTY_PROVIDER = { name: "Microsoft Entra ID", issuer: "https://login.microsoftonline.com/tenant/v2.0", client_id: "", allowed_domains: "", allow_any_domain: false }

export default function EnterpriseIdentityPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const overview = useQuery({ queryKey: ["enterprise-identity"], queryFn: () => adminCall<Overview>("/enterprise-identity", sessionToken), enabled: Boolean(sessionToken) && Boolean(administrator?.install_operator) })
  const [provider, setProvider] = useState(EMPTY_PROVIDER)
  const [revoking, setRevoking] = useState<Workload | null>(null)
  const [revokeReason, setRevokeReason] = useState("")
  const [workloadFilter, setWorkloadFilter] = useState("ACTIVE")
  const [workloadSearch, setWorkloadSearch] = useState("")
  const [busy, setBusy] = useState(false)

  const workloads = useMemo(() => overview.data?.workloads ?? [], [overview.data])
  const visibleWorkloads = useMemo(() => {
    const needle = workloadSearch.trim().toLowerCase()
    return workloads.filter((item) => (workloadFilter === "ALL" || item.status === workloadFilter)
      && (!needle || `${item.name} ${item.subject} ${item.agent_name ?? ""}`.toLowerCase().includes(needle)))
  }, [workloads, workloadFilter, workloadSearch])

  if (!administrator?.install_operator) return <Navigate to="/dashboard" replace />

  const run = async (action: () => Promise<unknown>, success: string, failure: string) => {
    setBusy(true)
    try {
      await action()
      pushToast({ tone: "success", title: success, message: "The change was recorded in the security evidence." })
      await overview.refetch()
      return true
    } catch (error) {
      pushToast({ tone: "error", title: failure, message: error instanceof Error ? error.message : "Request failed." })
      return false
    } finally {
      setBusy(false)
    }
  }

  const saveProvider = async () => {
    const body = { ...provider, allowed_domains: provider.allowed_domains.split(",").map((item) => item.trim()).filter(Boolean), enabled: true }
    if (await run(() => adminCall("/enterprise-identity/providers", sessionToken, { method: "POST", body }), "Identity provider saved", "Provider rejected")) setProvider(EMPTY_PROVIDER)
  }
  const decide = (item: Elevation, approved: boolean) =>
    void run(() => adminCall(`/enterprise-identity/elevations/${item.elevation_id}/decision`, sessionToken, { method: "POST", body: { approved } }), approved ? "Elevation approved" : "Elevation rejected", "Decision rejected")
  const revoke = async () => {
    if (!revoking) return
    if (await run(() => adminCall(`/enterprise-identity/workloads/${revoking.workload_id}/revoke`, sessionToken, { method: "POST", body: { reason: revokeReason } }), "Workload certificate revoked", "Revocation rejected")) {
      setRevoking(null); setRevokeReason("")
    }
  }

  const elevationColumns: Column<Elevation>[] = [
    { key: "role", header: "Requested role", sortValue: (item) => item.requested_role, render: (item) => <strong>{item.requested_role.replaceAll("_", " ")}</strong> },
    { key: "reason", header: "Reason", render: (item) => item.reason },
    { key: "status", header: "Status", sortValue: (item) => item.status, render: (item) => <StatusBadge value={item.status} /> },
    { key: "expires", header: "Expires", secondary: true, sortValue: (item) => item.expires_at, render: (item) => new Date(item.expires_at).toLocaleString() },
    { key: "actions", header: "Decision", align: "end", render: (item) => item.status === "PENDING" ? (
      <div className="gg-row-actions">
        <button type="button" className="gg-button" disabled={busy} onClick={() => decide(item, true)}><Check size={14} aria-hidden="true" />Approve</button>
        <button type="button" className="gg-button gg-button--danger" disabled={busy} onClick={() => decide(item, false)}><X size={14} aria-hidden="true" />Reject</button>
      </div>
    ) : <span className="gg-muted">Decided</span> },
  ]
  const workloadColumns: Column<Workload>[] = [
    { key: "name", header: "Workload", sortValue: (item) => item.name, render: (item) => <div className="gg-cell-stack"><strong>{item.name}</strong><code className="gg-code">{item.subject}</code></div> },
    { key: "agent", header: "Bound agent", sortValue: (item) => item.agent_name, render: (item) => item.agent_name ?? <span className="gg-muted">Not bound</span> },
    { key: "status", header: "Status", sortValue: (item) => item.status, render: (item) => <StatusBadge value={item.status} /> },
    { key: "expires", header: "Expires", secondary: true, sortValue: (item) => item.expires_at, render: (item) => new Date(item.expires_at).toLocaleDateString() },
    { key: "used", header: "Last used", secondary: true, sortValue: (item) => item.last_authenticated_at, render: (item) => <span title={item.last_authenticated_at ?? undefined}>{relativeTime(item.last_authenticated_at)}</span> },
    { key: "actions", header: "Actions", align: "end", render: (item) => item.status === "ACTIVE"
      ? <button type="button" className="gg-button gg-button--danger" onClick={() => { setRevoking(item); setRevokeReason("") }} aria-label={`Revoke ${item.name}`}>Revoke</button>
      : <span className="gg-muted">No actions</span> },
  ]
  const providerColumns: Column<Provider>[] = [
    { key: "name", header: "Provider", sortValue: (item) => item.name, render: (item) => <div className="gg-cell-stack"><strong>{item.name}</strong><small>{item.issuer}</small></div> },
    { key: "domains", header: "Allowed domains", render: (item) => item.allowed_domains.length ? item.allowed_domains.join(", ") : <StatusBadge value="ANY DOMAIN" tone="warning" /> },
    { key: "state", header: "State", sortValue: (item) => String(item.enabled), render: (item) => <StatusBadge value={item.enabled ? "ENABLED" : "DISABLED"} tone={item.enabled ? "success" : "neutral"} /> },
  ]
  const mappingColumns: Column<Mapping>[] = [
    { key: "claim", header: "Claim", sortValue: (item) => item.claim_name, render: (item) => <code className="gg-code">{item.claim_name} = {item.claim_value}</code> },
    { key: "role", header: "GreyGuard role", sortValue: (item) => item.greyguard_role, render: (item) => item.greyguard_role.replaceAll("_", " ") },
  ]

  const data = overview.data
  return (
    <section className="gg-page">
      <PageHeader
        title="Enterprise identity"
        icon={<Building2 size={22} />}
        description="Install-wide trust: single sign-on federation, the claims that map to GreyGuard roles, agent workload certificates and time-bound privilege elevation."
        actions={<button type="button" className="gg-button" onClick={() => void overview.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <Guidance id="enterprise-identity" title="What this page controls">
        <ul>
          <li><strong>Identity providers</strong> let administrators sign in with your OIDC issuer. Client secrets stay outside GreyGuard.</li>
          <li><strong>Workload certificates</strong> bind an agent to an mTLS identity. Register them with <code>POST /enterprise-identity/workloads</code>, as described in docs/agent-certificate-authentication.md.</li>
          <li><strong>Elevations</strong> grant a higher role for a limited time and need a different administrator's approval.</li>
        </ul>
      </Guidance>

      {overview.isLoading && <LoadingState label="Loading enterprise identity controls" rows={4} />}
      {overview.isError && <ErrorState message={overview.error.message} onRetry={() => void overview.refetch()} />}
      {data && (
        <>
          <StatGrid label="Identity posture">
            <StatCard label="Posture" value={enterprisePosture(data.summary)} tone={data.summary.active_break_glass ? "danger" : data.summary.pending_elevations ? "warning" : "success"} hint={`${data.summary.active_break_glass} break-glass session${data.summary.active_break_glass === 1 ? "" : "s"} active`} />
            <StatCard label="Pending elevations" value={data.summary.pending_elevations} hint="Waiting for a second administrator" tone={data.summary.pending_elevations ? "warning" : "success"} />
            <StatCard label="Enabled providers" value={data.summary.providers} hint="OIDC federation" tone="info" />
            <StatCard label="Workload identities" value={data.summary.workload_identities} hint="Agent mTLS bindings" />
          </StatGrid>

          <Panel id="identity-elevations" eyebrow="Needs a decision" title="Privilege elevation requests">
            <DataTable label="Elevation requests" columns={elevationColumns} rows={data.elevations} rowKey={(item) => item.elevation_id}
              initialSort={{ key: "status", direction: "desc" }}
              rowTone={(item) => (item.status === "PENDING" ? "warning" : undefined)}
              empty={<EmptyState icon={<ShieldAlert size={28} />} title="No elevation requests" description="Requests for a temporary higher role appear here for approval." />} />
          </Panel>

          <Panel id="identity-workloads" eyebrow="Agents" title="Workload certificates">
            <FilterBar
              search={{ value: workloadSearch, onChange: setWorkloadSearch, placeholder: "Search workload, subject or agent" }}
              options={{ label: "Status", value: workloadFilter, onChange: setWorkloadFilter, items: [
                { value: "ACTIVE", label: "Active", count: workloads.filter((item) => item.status === "ACTIVE").length },
                { value: "REVOKED", label: "Revoked", count: workloads.filter((item) => item.status === "REVOKED").length },
                { value: "ALL", label: "All", count: workloads.length },
              ] }}
              summary={`${visibleWorkloads.length} of ${workloads.length} shown`}
            />
            <DataTable label="Workload certificates" columns={workloadColumns} rows={visibleWorkloads} rowKey={(item) => item.workload_id}
              empty={<EmptyState icon={<KeyRound size={28} />} title={workloads.length ? "No matching certificates" : "No workload certificates"} description={workloads.length ? "Change the search or status filter." : "Register a workload certificate to bind an agent to an mTLS identity."} />} />
          </Panel>

          <div className="gg-layout gg-layout--even">
            <Panel id="identity-providers" eyebrow="Federation" title="Identity providers">
              <DataTable label="Identity providers" columns={providerColumns} rows={data.providers} rowKey={(item) => item.provider_id}
                empty={<EmptyState icon={<Building2 size={28} />} title="No identity providers" description="Add an OIDC provider so administrators can use single sign-on." />} />
              <h3 className="identity-subheading">Claim mappings</h3>
              <DataTable label="Claim mappings" columns={mappingColumns} rows={data.mappings} rowKey={(item) => item.mapping_id}
                empty={<p className="gg-muted">No claim mappings configured.</p>} />
            </Panel>

            <Panel id="identity-add-provider" eyebrow="Federation" title="Add an OIDC provider">
              <form className="gg-form" onSubmit={(event) => { event.preventDefault(); void saveProvider() }}>
                <label className="gg-field">Name<input value={provider.name} onChange={(event) => setProvider({ ...provider, name: event.target.value })} /></label>
                <label className="gg-field">HTTPS issuer<input value={provider.issuer} onChange={(event) => setProvider({ ...provider, issuer: event.target.value })} /></label>
                <label className="gg-field">Client ID<input value={provider.client_id} onChange={(event) => setProvider({ ...provider, client_id: event.target.value })} /></label>
                <label className="gg-field">Allowed domains<input placeholder="example.com, subsidiary.com" value={provider.allowed_domains} onChange={(event) => setProvider({ ...provider, allowed_domains: event.target.value })} /><small>Only these email domains can sign in through this provider.</small></label>
                <label className="gg-check">
                  <input type="checkbox" checked={provider.allow_any_domain} onChange={(event) => setProvider({ ...provider, allow_any_domain: event.target.checked })} />
                  <span>Allow any email this provider vouches for (no domain restriction). This is required if you leave allowed domains blank. An existing administrator account with a matching email can be taken over on next sign-in.</span>
                </label>
                <div className="gg-form__actions">
                  <button type="submit" className="gg-button gg-button--primary" disabled={busy || !provider.client_id || (!provider.allowed_domains.trim() && !provider.allow_any_domain)}><Plus size={16} aria-hidden="true" />Save provider</button>
                </div>
              </form>
            </Panel>
          </div>
        </>
      )}

      <ConfirmDialog
        open={Boolean(revoking)}
        title={`Revoke ${revoking?.name ?? "workload certificate"}?`}
        description="The certificate binding stops authenticating immediately. The agent needs a new workload certificate to connect over mTLS."
        confirmLabel="Revoke certificate"
        busy={busy}
        confirmDisabled={revokeReason.trim().length < 3}
        onCancel={() => setRevoking(null)}
        onConfirm={() => void revoke()}
      >
        <label className="gg-field">Reason (recorded in the evidence)<input value={revokeReason} onChange={(event) => setRevokeReason(event.target.value)} placeholder="At least 3 characters" /></label>
      </ConfirmDialog>
    </section>
  )
}
