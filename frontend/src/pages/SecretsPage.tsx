import { useQuery } from "@tanstack/react-query"
import { Info, KeyRound, Plus, RefreshCw, ShieldOff } from "lucide-react"
import { useMemo, useState } from "react"

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

type Secret = { secret_id: string; name: string; provider: string; reference: string; status: string; created_at: string; last_accessed_at: string | null; access_count: number; rotation_interval_days: number | null; next_rotation_at: string | null }
type Provider = { provider: string; available: boolean; credentials_stored: boolean; detail: string }
type SecretsResponse = { secrets: Secret[]; providers?: Provider[] }

const ROTATION_WARNING_DAYS = 14

export function rotationDue(secret: Pick<Secret, "status" | "next_rotation_at">, now: number = Date.now()): boolean {
  if (secret.status !== "ACTIVE" || !secret.next_rotation_at) return false
  return Date.parse(secret.next_rotation_at) - now < ROTATION_WARNING_DAYS * 86_400_000
}

export default function SecretsPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const canManage = administrator?.role === "PLATFORM_ADMIN"
  const secrets = useQuery({ queryKey: ["secrets"], queryFn: () => adminCall<SecretsResponse>("/secrets", sessionToken), enabled: Boolean(sessionToken) })

  const [name, setName] = useState("")
  const [reference, setReference] = useState("")
  const [provider, setProvider] = useState("ENVIRONMENT")
  const [rotationDays, setRotationDays] = useState(90)
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("ALL")
  const [revoking, setRevoking] = useState<Secret | null>(null)
  const [rotating, setRotating] = useState<Secret | null>(null)
  const [nextReference, setNextReference] = useState("")
  const [revokeAll, setRevokeAll] = useState(false)
  const [busy, setBusy] = useState(false)

  const items = useMemo(() => secrets.data?.secrets ?? [], [secrets.data])
  const providers = secrets.data?.providers ?? []
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return items.filter((item) => (status === "ALL" || item.status === status)
      && (!needle || `${item.name} ${item.reference} ${item.provider}`.toLowerCase().includes(needle)))
  }, [items, search, status])
  const active = items.filter((item) => item.status === "ACTIVE").length
  const due = items.filter((item) => rotationDue(item)).length

  const call = async (path: string, body: unknown, success: string) => {
    setBusy(true)
    try {
      await adminCall(path, sessionToken, { method: "POST", body })
      pushToast({ tone: "success", title: success, message: "No secret value was exposed or persisted." })
      setRevoking(null); setRotating(null); setRevokeAll(false)
      await secrets.refetch()
      return true
    } catch (error) {
      pushToast({ tone: "error", title: "Secret operation failed", message: error instanceof Error ? error.message : "Request failed." })
      return false
    } finally {
      setBusy(false)
    }
  }

  const register = async () => {
    if (await call("/secrets", { name, reference, provider, rotation_interval_days: rotationDays }, "Reference registered")) {
      setName(""); setReference("")
    }
  }

  const columns: Column<Secret>[] = [
    { key: "name", header: "Reference", sortValue: (item) => item.name, render: (item) => <div className="gg-cell-stack"><strong>{item.name}</strong><code className="gg-code">{item.reference}</code></div> },
    { key: "provider", header: "Provider", sortValue: (item) => item.provider, render: (item) => item.provider },
    { key: "status", header: "Status", sortValue: (item) => item.status, render: (item) => <StatusBadge value={item.status} /> },
    { key: "uses", header: "Accesses", align: "end", secondary: true, sortValue: (item) => item.access_count, render: (item) => item.access_count },
    { key: "last", header: "Last accessed", secondary: true, sortValue: (item) => item.last_accessed_at, render: (item) => <span title={item.last_accessed_at ?? undefined}>{relativeTime(item.last_accessed_at)}</span> },
    { key: "rotation", header: "Next rotation", sortValue: (item) => item.next_rotation_at, render: (item) => item.next_rotation_at ? <span title={item.next_rotation_at}>{new Date(item.next_rotation_at).toLocaleDateString()}{rotationDue(item) && <> <StatusBadge value="DUE" tone="warning" /></>}</span> : <span className="gg-muted">Not scheduled</span> },
    ...(canManage ? [{
      key: "actions", header: "Actions", align: "end" as const,
      render: (item: Secret) => item.status === "ACTIVE" ? (
        <div className="gg-row-actions">
          <button type="button" className="gg-button" onClick={() => { setRotating(item); setNextReference(item.reference) }} aria-label={`Rotate ${item.name}`}><RefreshCw size={14} aria-hidden="true" />Rotate</button>
          <button type="button" className="gg-button gg-button--danger" onClick={() => setRevoking(item)} aria-label={`Revoke ${item.name}`}><ShieldOff size={14} aria-hidden="true" />Revoke</button>
        </div>
      ) : <span className="gg-muted">No actions</span>,
    }] : []),
  ]

  return (
    <section className="gg-page">
      <PageHeader
        eyebrow="Policies & Controls"
        title="Secret references"
        icon={<KeyRound size={22} />}
        description="GreyGuard stores references to secrets held in your providers, plus the audit evidence of their use. Secret values are fetched just in time for a controlled integration and are never displayed or stored."
        actions={
          <>
            <button type="button" className="gg-button" onClick={() => void secrets.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>
            {canManage && <button type="button" className="gg-button gg-button--danger" onClick={() => setRevokeAll(true)} disabled={!active}><ShieldOff size={16} aria-hidden="true" />Revoke all</button>}
          </>
        }
      />

      <Guidance id="secrets" title="How secret references work">
        <ol>
          <li><strong>Register</strong> a reference: an environment variable name or a provider path. The value stays in the provider.</li>
          <li><strong>Rotate</strong> on schedule by pointing the reference at the new secret. References due within {ROTATION_WARNING_DAYS} days are flagged.</li>
          <li><strong>Revoke</strong> a single reference, or every active one at once in an emergency. Integrations using a revoked reference stop immediately.</li>
        </ol>
      </Guidance>

      {secrets.isLoading && <LoadingState label="Loading secret references" rows={4} />}
      {secrets.isError && <ErrorState message={secrets.error.message} onRetry={() => void secrets.refetch()} />}
      {secrets.data && (
        <>
          <StatGrid label="Secret reference summary">
            <StatCard label="References" value={items.length} hint="Registered in this organization" tone="info" />
            <StatCard label="Active" value={active} hint="Usable by controlled integrations" tone="success" />
            <StatCard label="Rotation due" value={due} hint={`Within ${ROTATION_WARNING_DAYS} days or overdue`} tone={due ? "warning" : "success"} />
            <StatCard label="Providers available" value={`${providers.filter((item) => item.available).length} of ${providers.length}`} hint="Provider SDKs installed on this server" />
          </StatGrid>

          {canManage ? (
            <Panel id="secret-register" eyebrow="New reference" title="Register a secret reference">
              <form className="gg-form" onSubmit={(event) => { event.preventDefault(); void register() }}>
                <div className="gg-form__row">
                  <label className="gg-field">Display name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Ticketing API token" required /></label>
                  <label className="gg-field">Provider
                    <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                      {providers.map((item) => <option key={item.provider} value={item.provider}>{item.provider}{item.available ? "" : " (SDK unavailable)"}</option>)}
                    </select>
                  </label>
                  <label className="gg-field">Reference
                    <input value={reference} onChange={(event) => setReference(provider === "ENVIRONMENT" ? event.target.value.toUpperCase() : event.target.value)} placeholder={provider === "ENVIRONMENT" ? "ENVIRONMENT_VARIABLE" : "Provider secret reference"} required />
                    <small>A name or path, never the secret itself.</small>
                  </label>
                  <label className="gg-field">Rotate every (days)<input type="number" min="1" max="365" value={rotationDays} onChange={(event) => setRotationDays(Number(event.target.value))} /></label>
                </div>
                <div className="gg-form__actions"><button type="submit" className="gg-button gg-button--primary" disabled={busy || !name.trim() || !reference.trim()}><Plus size={16} aria-hidden="true" />Register reference</button></div>
              </form>
            </Panel>
          ) : (
            <p className="gg-note"><Info size={16} aria-hidden="true" />Your role has read-only access to secret references. Platform administrators register, rotate and revoke them.</p>
          )}

          <Panel id="secret-list" eyebrow="Inventory" title="References">
            <FilterBar
              search={{ value: search, onChange: setSearch, placeholder: "Search by name, reference or provider" }}
              options={{ label: "Status", value: status, onChange: setStatus, items: [
                { value: "ALL", label: "All", count: items.length },
                { value: "ACTIVE", label: "Active", count: active },
                { value: "REVOKED", label: "Revoked", count: items.filter((item) => item.status === "REVOKED").length },
              ] }}
              summary={`${visible.length} of ${items.length} shown`}
            />
            <DataTable
              label="Secret references"
              columns={columns}
              rows={visible}
              rowKey={(item) => item.secret_id}
              rowTone={(item) => (rotationDue(item) ? "warning" : undefined)}
              empty={items.length
                ? <EmptyState icon={<KeyRound size={28} />} title="No matching references" description="Change the search or status filter." />
                : <EmptyState icon={<KeyRound size={28} />} title="No secret references" description="Register a provider reference without storing its value." />}
            />
          </Panel>

          {providers.length > 0 && (
            <Panel id="secret-providers" eyebrow="Providers" title="Provider availability">
              <ul className="gg-list">
                {providers.map((item) => (
                  <li key={item.provider}>
                    <div className="gg-list__main"><strong>{item.provider}</strong><small>{item.detail}</small></div>
                    <StatusBadge value={item.available ? "AVAILABLE" : "UNAVAILABLE"} tone={item.available ? "success" : "neutral"} />
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </>
      )}

      <ConfirmDialog
        open={Boolean(revoking)}
        title="Revoke secret reference?"
        description={`${revoking?.name ?? "This reference"} will become unavailable to controlled integrations immediately. No secret value will be displayed.`}
        confirmLabel="Revoke reference"
        busy={busy}
        onCancel={() => setRevoking(null)}
        onConfirm={() => revoking && void call(`/secrets/${revoking.secret_id}/revoke`, undefined, "Reference revoked")}
      />
      <ConfirmDialog
        open={Boolean(rotating)}
        title={`Rotate ${rotating?.name ?? "reference"}`}
        description="Point this reference at the new secret in your provider. The old value is not shown or kept."
        confirmLabel="Rotate reference"
        tone="warning"
        busy={busy}
        confirmDisabled={!nextReference.trim()}
        onCancel={() => setRotating(null)}
        onConfirm={() => rotating && void call(`/secrets/${rotating.secret_id}/rotate`, { reference: nextReference }, "Reference rotated")}
      >
        <label className="gg-field">New provider reference<input value={nextReference} onChange={(event) => setNextReference(event.target.value)} /></label>
      </ConfirmDialog>
      <ConfirmDialog
        open={revokeAll}
        title="Revoke every active secret reference?"
        description={`All ${active} active references across every provider are revoked at once. Integrations that depend on them stop until new references are registered.`}
        confirmLabel="Revoke all references"
        busy={busy}
        onCancel={() => setRevokeAll(false)}
        onConfirm={() => void call("/secrets/emergency-revoke", {}, "Every active reference revoked")}
      />
    </section>
  )
}
