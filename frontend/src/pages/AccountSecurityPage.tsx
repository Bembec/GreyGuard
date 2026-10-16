import { useQuery } from "@tanstack/react-query"
import { Fingerprint, KeyRound, Laptop, RefreshCw, ShieldCheck, Trash2 } from "lucide-react"
import { useState } from "react"

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

type Session = { session_id: string; created_at: string; expires_at: string; revoked_at: string | null; device_name: string | null; ip_address: string | null; last_seen_at: string | null }

export const sessionState = (session: Session) => (session.revoked_at ? "Revoked" : new Date(session.expires_at) <= new Date() ? "Expired" : "Active")

const SESSION_TONE = { Active: "success", Expired: "neutral", Revoked: "neutral" } as const

export default function AccountSecurityPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const sessions = useQuery({ queryKey: ["auth-sessions"], queryFn: () => adminCall<{ sessions: Session[] }>("/auth/sessions", sessionToken), enabled: Boolean(sessionToken) })
  const [secret, setSecret] = useState("")
  const [code, setCode] = useState("")
  const [mfaJustEnabled, setMfaJustEnabled] = useState(false)
  const [filter, setFilter] = useState("Active")
  const [revoking, setRevoking] = useState<Session | null>(null)
  const [busy, setBusy] = useState(false)

  const all = sessions.data?.sessions ?? []
  const visible = all.filter((item) => filter === "ALL" || sessionState(item) === filter)
  const mfaEnabled = Boolean(administrator?.mfa_enabled) || mfaJustEnabled
  const passwordExpires = administrator?.password_expires_at ? new Date(administrator.password_expires_at) : null
  const passwordDaysLeft = passwordExpires ? Math.ceil((passwordExpires.getTime() - Date.now()) / 86_400_000) : null

  const enroll = async () => {
    try {
      const body = await adminCall<{ secret: string }>("/auth/mfa/enroll", sessionToken, { method: "POST" })
      setSecret(body.secret)
    } catch (error) {
      pushToast({ tone: "error", title: "MFA enrollment failed", message: error instanceof Error ? error.message : "Request failed." })
    }
  }
  const confirmMfa = async () => {
    try {
      await adminCall("/auth/mfa/confirm", sessionToken, { method: "POST", body: { code } })
      setSecret(""); setCode(""); setMfaJustEnabled(true)
      pushToast({ tone: "success", title: "Multi-factor authentication enabled", message: "Your next sign-in will ask for a six-digit code." })
    } catch (error) {
      pushToast({ tone: "error", title: "Code not accepted", message: error instanceof Error ? error.message : "Request failed." })
    }
  }
  const revoke = async () => {
    if (!revoking) return
    setBusy(true)
    try {
      await adminCall(`/auth/sessions/${revoking.session_id}`, sessionToken, { method: "DELETE" })
      pushToast({ tone: "success", title: "Device session revoked", message: "That device must sign in again." })
      setRevoking(null)
      await sessions.refetch()
    } catch (error) {
      pushToast({ tone: "error", title: "Revocation failed", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  const columns: Column<Session>[] = [
    { key: "device", header: "Device", sortValue: (item) => item.device_name, render: (item) => <div className="gg-cell-stack"><strong>{item.device_name || "Unknown device"}</strong><small>{item.ip_address || "Unknown address"}</small></div> },
    { key: "state", header: "State", sortValue: (item) => sessionState(item), render: (item) => <StatusBadge value={sessionState(item)} tone={SESSION_TONE[sessionState(item)]} /> },
    { key: "seen", header: "Last seen", sortValue: (item) => item.last_seen_at ?? item.created_at, render: (item) => <span title={item.last_seen_at ?? item.created_at}>{relativeTime(item.last_seen_at ?? item.created_at)}</span> },
    { key: "created", header: "Signed in", secondary: true, sortValue: (item) => item.created_at, render: (item) => new Date(item.created_at).toLocaleString() },
    { key: "actions", header: "Actions", align: "end", render: (item) => item.revoked_at ? null : <button type="button" className="gg-button" onClick={() => setRevoking(item)} aria-label={`Revoke ${item.device_name || "this"} session`}><Trash2 size={14} aria-hidden="true" />Revoke</button> },
  ]

  return (
    <section className="gg-page">
      <PageHeader
        title="Account security"
        icon={<ShieldCheck size={22} />}
        description={<>Protect <strong>{administrator?.email}</strong> with multi-factor authentication, and review every device signed in to your account.</>}
        actions={<button type="button" className="gg-button" onClick={() => void sessions.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <Guidance id="account-security" title="Keeping your account safe">
        <ul>
          <li>Turn on <strong>MFA</strong>: a stolen password alone then cannot open your account.</li>
          <li>Revoke any session you don't recognise. Revoking the device you are using now signs you out.</li>
          <li>Passwords expire automatically. A password reset by an install operator ends every active session.</li>
        </ul>
      </Guidance>

      <StatGrid label="Account security summary">
        <StatCard label="Multi-factor authentication" value={mfaEnabled ? "On" : "Off"} hint={mfaEnabled ? "Code required at sign-in" : "Recommended for every administrator"} tone={mfaEnabled ? "success" : "warning"} />
        <StatCard label="Password expires" value={passwordDaysLeft === null ? "—" : passwordDaysLeft <= 0 ? "Expired" : `${passwordDaysLeft} days`} hint={passwordExpires ? passwordExpires.toLocaleDateString() : "Not recorded"} tone={passwordDaysLeft !== null && passwordDaysLeft <= 14 ? "warning" : "neutral"} />
        <StatCard label="Active sessions" value={sessions.data ? all.filter((item) => sessionState(item) === "Active").length : "—"} hint="Signed-in devices" tone="info" />
      </StatGrid>

      <Panel id="account-mfa" eyebrow="Authentication" title="Authenticator app">
        {!secret ? (
          <div className="gg-form">
            <p className="gg-note"><Fingerprint size={16} aria-hidden="true" />After your password, GreyGuard asks for a six-digit code from an authenticator app.</p>
            <div className="gg-form__actions"><button type="button" className="gg-button gg-button--primary" onClick={() => void enroll()}><KeyRound size={16} aria-hidden="true" />{mfaEnabled ? "Replace authenticator" : "Set up MFA"}</button></div>
          </div>
        ) : (
          <form className="gg-form" onSubmit={(event) => { event.preventDefault(); void confirmMfa() }}>
            <p className="gg-note">Add this secret to your authenticator app, then enter the six-digit code it shows.</p>
            <label className="gg-field">One-time setup secret<code className="gg-code">{secret}</code></label>
            <label className="gg-field">Six-digit code<input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} /></label>
            <div className="gg-form__actions">
              <button type="button" className="gg-button" onClick={() => { setSecret(""); setCode("") }}>Cancel</button>
              <button type="submit" className="gg-button gg-button--primary" disabled={code.length !== 6}>Confirm MFA</button>
            </div>
          </form>
        )}
      </Panel>

      <Panel id="account-sessions" eyebrow="Devices" title="Device and session inventory">
        {sessions.isLoading && <LoadingState label="Loading session inventory" rows={3} />}
        {sessions.isError && <ErrorState message={sessions.error.message} onRetry={() => void sessions.refetch()} />}
        {sessions.data && (
          <>
            <FilterBar options={{ label: "State", value: filter, onChange: setFilter, items: [
              { value: "Active", label: "Active", count: all.filter((item) => sessionState(item) === "Active").length },
              { value: "Expired", label: "Expired", count: all.filter((item) => sessionState(item) === "Expired").length },
              { value: "Revoked", label: "Revoked", count: all.filter((item) => sessionState(item) === "Revoked").length },
              { value: "ALL", label: "All", count: all.length },
            ] }} summary={`${visible.length} of ${all.length} shown`} />
            <DataTable label="Sessions" columns={columns} rows={visible} rowKey={(item) => item.session_id} initialSort={{ key: "seen", direction: "desc" }}
              empty={<EmptyState icon={<Laptop size={28} />} title="No sessions in this view" description="Change the state filter to see other sessions." />} />
          </>
        )}
      </Panel>

      <ConfirmDialog
        open={Boolean(revoking)}
        title={`Revoke ${revoking?.device_name || "this"} session?`}
        description="That device is signed out and must sign in again. If it is the device you are using now, you will be signed out."
        confirmLabel="Revoke session"
        busy={busy}
        onCancel={() => setRevoking(null)}
        onConfirm={() => void revoke()}
      />
    </section>
  )
}
