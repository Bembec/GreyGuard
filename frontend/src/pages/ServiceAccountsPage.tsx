import {
  Bot,
  Check,
  Copy,
  KeyRound,
  Plus,
  RefreshCw,
  ShieldOff,
  X,
} from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"

import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { FilterBar } from "../components/page/FilterBar"
import { Guidance } from "../components/page/Guidance"
import { PageHeader } from "../components/page/PageHeader"
import { StatCard, StatGrid } from "../components/page/StatCard"
import { useDismissableLayer } from "../hooks/useDismissableLayer"
import { usePermission } from "../hooks/usePermission"
import "../styles/service-accounts.css"

type ServiceKey = {
  key_id: string
  key_prefix: string
  status: string
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  use_count: number
}
type ServiceAccount = {
  account_id: string
  name: string
  description: string
  status: string
  scopes: string[]
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  use_count: number
  keys: ServiceKey[]
  issued_key?: { api_key: string; key_prefix: string }
}
type ListResponse = {
  service_accounts: ServiceAccount[]
  available_scopes: string[]
  plaintext_keys_stored: boolean
}

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"

export function serviceKeyDisplay(prefix: string) {
  return `${prefix}_••••••••••••`
}

const EXPIRY_WARNING_DAYS = 30

export function expiresSoon(account: Pick<ServiceAccount, "status" | "expires_at">, now: number = Date.now()) {
  return account.status === "ACTIVE" && Boolean(account.expires_at) && Date.parse(account.expires_at!) - now < EXPIRY_WARNING_DAYS * 86_400_000
}

export default function ServiceAccountsPage() {
  const { sessionToken } = useAuth()
  // Every /service-accounts mutation requires admin:manage server-side (admin_auth.py's
  // required_permission) - only PLATFORM_ADMIN holds it. This page previously had no
  // permission check of any kind - administrator was never even destructured from useAuth().
  const canManageServiceAccounts = usePermission({ permission: "admin:manage" })
  const { pushToast } = useToast()
  const [accounts, setAccounts] = useState<ServiceAccount[]>([])
  const [availableScopes, setAvailableScopes] = useState<string[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [scopes, setScopes] = useState<string[]>(["audit:read"])
  const [days, setDays] = useState(90)
  const [revealedKey, setRevealedKey] = useState("")
  const [copied, setCopied] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState("")
  const [confirmAccount, setConfirmAccount] = useState<ServiceAccount | null>(null)
  const [rotateAccount, setRotateAccount] = useState<ServiceAccount | null>(null)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState("ACTIVE")
  const [busy, setBusy] = useState(false)
  const createCloseRef = useRef<HTMLButtonElement>(null)
  const createDialogRef = useDismissableLayer<HTMLDivElement>({ open: showCreate, onClose: () => setShowCreate(false), trapFocus: true, initialFocusRef: createCloseRef, lockBodyScroll: true })
  const headers = { "Content-Type": "application/json", "X-Admin-Pin": sessionToken ?? "" }

  const load = async () => {
    setLoading(true); setLoadError("")
    try { const response = await fetch(`${API}/service-accounts`, { headers }); const body = await response.json(); if (!response.ok) throw new Error(body.detail ?? "Unable to load service accounts."); const data = body as ListResponse; setAccounts(data.service_accounts); setAvailableScopes(data.available_scopes) }
    catch (error) { const detail=error instanceof Error?error.message:"Unable to load service accounts.";setLoadError(detail);throw error }
    finally { setLoading(false) }
  }

  useEffect(() => { void load().catch(() => undefined) }, [sessionToken])

  const create = async () => {
    setBusy(true)
    try {
      const response = await fetch(`${API}/service-accounts`, {
        method: "POST", headers,
        body: JSON.stringify({ name, description, scopes, expires_in_days: days }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail ?? "Service account could not be created.")
      setRevealedKey((body as ServiceAccount).issued_key?.api_key ?? "")
      setShowCreate(false); setName(""); setDescription(""); setScopes(["audit:read"])
      pushToast({tone:"success",title:"Service account created",message:"Copy the API key now. It will not be shown again."})
      await load()
    } catch (error) { pushToast({tone:"error",title:"Creation failed",message:error instanceof Error ? error.message : "Request failed."}) }
    finally { setBusy(false) }
  }

  const lifecycle = async (account: ServiceAccount, action: "rotate" | "revoke") => {
    setBusy(true)
    try {
      const response = await fetch(`${API}/service-accounts/${account.account_id}/${action}`, {
        method: "POST", headers,
        body: action === "rotate" ? JSON.stringify({ expires_in_days: days }) : undefined,
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail ?? `Unable to ${action} service account.`)
      if (action === "rotate") {
        setRevealedKey((body as ServiceAccount).issued_key?.api_key ?? "")
        pushToast({tone:"warning",title:"API key rotated",message:"Copy the replacement now. The previous key is revoked."})
      } else pushToast({tone:"success",title:"Service account revoked",message:"Every associated API key is now inactive."})
      await load()
    } catch (error) { pushToast({tone:"error",title:`Unable to ${action}`,message:error instanceof Error ? error.message : "Request failed."}) }
    finally { setBusy(false);setConfirmAccount(null);setRotateAccount(null) }
  }

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return accounts.filter((account) => (statusFilter === "ALL" || account.status === statusFilter)
      && (!needle || `${account.name} ${account.description} ${account.scopes.join(" ")}`.toLowerCase().includes(needle)))
  }, [accounts, search, statusFilter])
  const activeCount = accounts.filter((account) => account.status === "ACTIVE").length

  const copyKey = async () => {
    await navigator.clipboard.writeText(revealedKey)
    setCopied(true); window.setTimeout(() => setCopied(false), 1800)
    pushToast({tone:"success",title:"API key copied",message:"Store it in an approved secret manager."})
  }

  return <section className="gg-page">
    <PageHeader
      title="API keys & service accounts"
      icon={<Bot size={22} />}
      description="Issue scoped, expiring credentials for automation and CI, so no integration ever shares an administrator's session."
      actions={<>
        <button type="button" className="gg-button" onClick={() => void load().catch(() => undefined)}><RefreshCw size={16} aria-hidden="true" />Refresh</button>
        {canManageServiceAccounts && <button type="button" className="gg-button gg-button--primary" onClick={() => setShowCreate(true)}><Plus size={16} aria-hidden="true" />New service account</button>}
      </>}
    />
    {!canManageServiceAccounts && <p className="gg-readonly-note">Your role has read-only access to service accounts. Platform Administrator access is required to create, rotate or revoke them.</p>}

    <p className="gg-note"><KeyRound size={16} aria-hidden="true" /><span><strong>Keys are revealed once.</strong> GreyGuard stores a one-way hash and a visible prefix only. A plaintext key cannot be recovered.</span></p>

    <Guidance id="service-accounts" title="How machine identities are governed">
      <ol>
        <li><strong>Create</strong> an account with the fewest scopes the integration needs and a key lifetime. The key is shown once.</li>
        <li><strong>Rotate</strong> before expiry: a replacement key is issued and the previous key stops working at once.</li>
        <li><strong>Revoke</strong> the account to stop every key it holds. Accounts expiring within {EXPIRY_WARNING_DAYS} days are flagged.</li>
      </ol>
    </Guidance>

    {!loading && !loadError && <StatGrid label="Service account summary">
      <StatCard label="Active accounts" value={activeCount} hint={`${accounts.length - activeCount} revoked or expired`} tone="info" />
      <StatCard label="Expiring soon" value={accounts.filter((account) => expiresSoon(account)).length} hint={`Within ${EXPIRY_WARNING_DAYS} days`} tone={accounts.some((account) => expiresSoon(account)) ? "warning" : "success"} />
      <StatCard label="Never used" value={accounts.filter((account) => account.status === "ACTIVE" && !account.last_used_at).length} hint="Active but no recorded use" />
      <StatCard label="Total uses" value={accounts.reduce((total, account) => total + account.use_count, 0)} hint="Across every account" />
    </StatGrid>}

    {!loading && !loadError && accounts.length > 0 && <FilterBar
      search={{ value: search, onChange: setSearch, placeholder: "Search name, description or scope" }}
      options={{ label: "Status", value: statusFilter, onChange: setStatusFilter, items: [
        { value: "ACTIVE", label: "Active", count: activeCount },
        { value: "REVOKED", label: "Revoked", count: accounts.filter((account) => account.status === "REVOKED").length },
        { value: "ALL", label: "All", count: accounts.length },
      ] }}
      summary={`${visible.length} of ${accounts.length} shown`}
    />}

    {revealedKey && <section className="service-reveal">
      <div><strong>Copy this API key now</strong><span>It will disappear when this panel is closed or the page is refreshed.</span></div>
      <code>{revealedKey}</code>
      <button type="button" onClick={() => void copyKey()}>{copied ? <Check size={17} /> : <Copy size={17} />}{copied ? "Copied" : "Copy key"}</button>
      <button type="button" className="close" onClick={() => setRevealedKey("")} aria-label="Close key"><X size={17} /></button>
    </section>}

    <section className="service-grid">
      {loading && <LoadingState label="Loading service accounts" rows={3}/>}
      {!loading && loadError && <ErrorState message={loadError} onRetry={() => void load()}/>}
      {!loading && !loadError && accounts.length === 0 && <EmptyState icon={<Bot size={30}/>} title="No machine identities" description="Create a scoped service account for CI, automation, or controlled integrations."/>}
      {!loading && !loadError && accounts.length > 0 && visible.length === 0 && <EmptyState icon={<Bot size={30}/>} title="No matching service accounts" description="Change the search or status filter."/>}
      {visible.map((account) => <article key={account.account_id}>
        <header><div><Bot size={21} /><span className={account.status.toLowerCase()}>{account.status}</span></div><small>{account.account_id}</small></header>
        <h2>{account.name}</h2><p>{account.description || "No description provided."}</p>
        <div className="service-scopes">{account.scopes.map((scope) => <span key={scope}>{scope}</span>)}</div>
        <dl><div><dt>Usage</dt><dd>{account.use_count}</dd></div><div><dt>Last used</dt><dd>{account.last_used_at ? new Date(account.last_used_at).toLocaleString() : "Never"}</dd></div><div><dt>Expires</dt><dd>{account.expires_at ? new Date(account.expires_at).toLocaleDateString() : "Never"}{expiresSoon(account) ? " · soon" : ""}</dd></div></dl>
        <section className="service-keys"><strong>Key history</strong>{account.keys.map((key) => <div key={key.key_id}><code>{serviceKeyDisplay(key.key_prefix)}</code><span className={key.status.toLowerCase()}>{key.status}</span></div>)}</section>
        {account.status === "ACTIVE" && canManageServiceAccounts && <footer><button disabled={busy} onClick={() => setRotateAccount(account)}><RefreshCw size={15} /> Rotate key</button><button disabled={busy} className="danger" onClick={() => setConfirmAccount(account)}><ShieldOff size={15} /> Revoke</button></footer>}
      </article>)}
    </section>

    {showCreate && <div ref={createDialogRef} className="service-modal" role="dialog" aria-modal="true"><button className="backdrop" onClick={() => setShowCreate(false)} aria-label="Close"/><section>
      <header><div><h2>Create service account</h2><p>Use the minimum scopes required by the integration.</p></div><button ref={createCloseRef} onClick={() => setShowCreate(false)} aria-label="Close"><X /></button></header>
      <label>Name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Deployment Bot" /></label>
      <label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Used by the controlled CI deployment workflow" /></label>
      <label>Key lifetime<select value={days} onChange={(event) => setDays(Number(event.target.value))}><option value={30}>30 days</option><option value={60}>60 days</option><option value={90}>90 days</option><option value={180}>180 days</option><option value={365}>1 year</option></select></label>
      <fieldset><legend>Scopes</legend>{availableScopes.map((scope) => <label key={scope}><input type="checkbox" checked={scopes.includes(scope)} onChange={(event) => setScopes((current) => event.target.checked ? [...current, scope] : current.filter((item) => item !== scope))} />{scope}</label>)}</fieldset>
      <footer><button className="secondary" onClick={() => setShowCreate(false)}>Cancel</button><button disabled={busy || !name.trim() || scopes.length === 0} onClick={() => void create()}><KeyRound size={16} /> Create and issue key</button></footer>
    </section></div>}
    <ConfirmDialog open={Boolean(rotateAccount)} title="Rotate this API key?" description={`A new key is issued for ${rotateAccount?.name ?? "this account"} and shown once. The current key stops working immediately, so update the integration straight away.`} confirmLabel="Rotate key" tone="warning" busy={busy} onCancel={() => setRotateAccount(null)} onConfirm={() => rotateAccount && void lifecycle(rotateAccount, "rotate")}>
      <label className="gg-field">New key lifetime<select value={days} onChange={(event) => setDays(Number(event.target.value))}><option value={30}>30 days</option><option value={60}>60 days</option><option value={90}>90 days</option><option value={180}>180 days</option><option value={365}>1 year</option></select></label>
    </ConfirmDialog>
    <ConfirmDialog open={Boolean(confirmAccount)} title="Revoke service account?" description={`This will immediately revoke ${confirmAccount?.name ?? "this account"} and every active API key. Automation using those keys will stop.`} confirmLabel="Revoke account" busy={busy} onCancel={() => setConfirmAccount(null)} onConfirm={() => confirmAccount && void lifecycle(confirmAccount,"revoke")}/>
  </section>
}
