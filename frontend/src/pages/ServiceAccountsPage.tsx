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
import { useEffect, useState } from "react"

import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
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
  const [busy, setBusy] = useState(false)
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
    finally { setBusy(false);setConfirmAccount(null) }
  }

  const copyKey = async () => {
    await navigator.clipboard.writeText(revealedKey)
    setCopied(true); window.setTimeout(() => setCopied(false), 1800)
    pushToast({tone:"success",title:"API key copied",message:"Store it in an approved secret manager."})
  }

  return <main className="service-page">
    <section className="service-hero">
      <div><p><Bot size={15} /> Machine identity governance</p><h1>API Keys &amp; Service Accounts</h1><span>Issue scoped, expiring credentials for automation without sharing administrator sessions.</span></div>
      {canManageServiceAccounts && <button type="button" onClick={() => setShowCreate(true)}><Plus size={17} /> New service account</button>}
    </section>
    {!canManageServiceAccounts && <p className="gg-readonly-note">Your role has read-only access to service accounts. Platform Administrator access is required to create, rotate or revoke them.</p>}

    <section className="service-assurance">
      <KeyRound size={20} /><div><strong>Keys are revealed once</strong><span>GreyGuard stores a one-way hash and visible prefix only. Plaintext credentials cannot be recovered.</span></div>
    </section>

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
      {accounts.map((account) => <article key={account.account_id}>
        <header><div><Bot size={21} /><span className={account.status.toLowerCase()}>{account.status}</span></div><small>{account.account_id}</small></header>
        <h2>{account.name}</h2><p>{account.description || "No description provided."}</p>
        <div className="service-scopes">{account.scopes.map((scope) => <span key={scope}>{scope}</span>)}</div>
        <dl><div><dt>Usage</dt><dd>{account.use_count}</dd></div><div><dt>Last used</dt><dd>{account.last_used_at ? new Date(account.last_used_at).toLocaleString() : "Never"}</dd></div><div><dt>Expires</dt><dd>{account.expires_at ? new Date(account.expires_at).toLocaleDateString() : "Never"}</dd></div></dl>
        <section className="service-keys"><strong>Key history</strong>{account.keys.map((key) => <div key={key.key_id}><code>{serviceKeyDisplay(key.key_prefix)}</code><span className={key.status.toLowerCase()}>{key.status}</span></div>)}</section>
        {account.status === "ACTIVE" && canManageServiceAccounts && <footer><button disabled={busy} onClick={() => void lifecycle(account, "rotate")}><RefreshCw size={15} /> Rotate key</button><button disabled={busy} className="danger" onClick={() => setConfirmAccount(account)}><ShieldOff size={15} /> Revoke</button></footer>}
      </article>)}
    </section>

    {showCreate && <div className="service-modal" role="dialog" aria-modal="true"><button className="backdrop" onClick={() => setShowCreate(false)} aria-label="Close"/><section>
      <header><div><h2>Create service account</h2><p>Use the minimum scopes required by the integration.</p></div><button onClick={() => setShowCreate(false)} aria-label="Close"><X /></button></header>
      <label>Name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Deployment Bot" /></label>
      <label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Used by the controlled CI deployment workflow" /></label>
      <label>Key lifetime<select value={days} onChange={(event) => setDays(Number(event.target.value))}><option value={30}>30 days</option><option value={60}>60 days</option><option value={90}>90 days</option><option value={180}>180 days</option><option value={365}>1 year</option></select></label>
      <fieldset><legend>Scopes</legend>{availableScopes.map((scope) => <label key={scope}><input type="checkbox" checked={scopes.includes(scope)} onChange={(event) => setScopes((current) => event.target.checked ? [...current, scope] : current.filter((item) => item !== scope))} />{scope}</label>)}</fieldset>
      <footer><button className="secondary" onClick={() => setShowCreate(false)}>Cancel</button><button disabled={busy || !name.trim() || scopes.length === 0} onClick={() => void create()}><KeyRound size={16} /> Create and issue key</button></footer>
    </section></div>}
    <ConfirmDialog open={Boolean(confirmAccount)} title="Revoke service account?" description={`This will immediately revoke ${confirmAccount?.name ?? "this account"} and every active API key. Automation using those keys will stop.`} confirmLabel="Revoke account" busy={busy} onCancel={() => setConfirmAccount(null)} onConfirm={() => confirmAccount && void lifecycle(confirmAccount,"revoke")}/>
  </main>
}
