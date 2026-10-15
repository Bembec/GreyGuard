import { FilePlus2, GitBranch, Plug, Save, Send, ShieldOff } from "lucide-react"
import { useEffect, useState } from "react"

import { ConfirmDialog } from "../components/ConfirmDialog"
import { Panel } from "../components/page/Panel"
import { StatusBadge } from "../components/page/StatusBadge"
import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { adminCall } from "../lib/adminApi"
import "../styles/policy-governance.css"

type Decision = "ALLOW" | "ASK" | "BLOCK"
type Policy = { policy_id: string; version_number: number; status: string; permissions: Record<string, Decision>; risk_weights: Record<string, number>; max_blocked_attempts: number; max_risk_score: number; change_summary: string }
type EmergencyControls = { global_deny: boolean; disabled_agents: string[]; disabled_tools: string[]; disabled_integrations: string[] }
type PolicyAdapter = { adapter_type: string; enabled: boolean; endpoint: string | null; owner: string; purpose: string; credentials_stored: boolean }
type PolicyRollout = { rollout_id: string; policy_id: string; percentage: number; status: string; agent_allowlist: string[] }
type Conflict = { action: string; severity: string; detail: string }

export default function PolicyGovernancePanel() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const [versions, setVersions] = useState<Policy[]>([])
  const [draft, setDraft] = useState<Policy | null>(null)
  const [simulation, setSimulation] = useState<Record<string, unknown> | null>(null)
  const [conflicts, setConflicts] = useState<Conflict[]>([])
  const [emergency, setEmergency] = useState<EmergencyControls>({ global_deny: false, disabled_agents: [], disabled_tools: [], disabled_integrations: [] })
  const [adapters, setAdapters] = useState<PolicyAdapter[]>([])
  const [rollouts, setRollouts] = useState<PolicyRollout[]>([])
  const [configuring, setConfiguring] = useState<PolicyAdapter | null>(null)
  const [endpoint, setEndpoint] = useState("")
  const [loadError, setLoadError] = useState("")
  const [busy, setBusy] = useState(false)

  const load = async () => {
    if (!sessionToken) return
    const [policies, controls, adapterData, rolloutData] = await Promise.all([
      adminCall<{ versions: Policy[] }>("/policy-versions", sessionToken),
      adminCall<EmergencyControls>("/policy-emergency-controls", sessionToken),
      adminCall<{ adapters?: PolicyAdapter[] }>("/policy-adapters", sessionToken).catch(() => ({ adapters: [] })),
      adminCall<{ rollouts?: PolicyRollout[] }>("/policy-rollouts", sessionToken).catch(() => ({ rollouts: [] })),
    ])
    setVersions(policies.versions)
    setDraft(policies.versions.find((policy) => policy.status === "DRAFT") ?? null)
    setEmergency(controls)
    setAdapters(adapterData.adapters ?? [])
    setRollouts(rolloutData.rollouts ?? [])
    setLoadError("")
  }
  useEffect(() => { load().catch((error: Error) => setLoadError(error.message)) }, [sessionToken])

  // Every change goes through here, so a rejected change is always reported, never silent.
  const call = async <T,>(path: string, method = "POST", body?: unknown, success = "Change completed"): Promise<T | undefined> => {
    setBusy(true)
    try {
      const result = await adminCall<T>(path, sessionToken, { method, body })
      pushToast({ tone: "success", title: success, message: "The policy change was recorded." })
      await load()
      return result
    } catch (error) {
      pushToast({ tone: "error", title: "Policy change rejected", message: error instanceof Error ? error.message : "Request failed." })
      return undefined
    } finally {
      setBusy(false)
    }
  }

  const published = versions.find((policy) => policy.status === "PUBLISHED")
  const create = () => published && call("/policy-versions/drafts", "POST", { permissions: published.permissions, risk_weights: published.risk_weights, max_blocked_attempts: published.max_blocked_attempts, max_risk_score: published.max_risk_score, change_summary: "New controlled policy revision" }, "Draft created")
  const save = () => draft && call(`/policy-versions/${draft.policy_id}/draft`, "PUT", draft, "Draft saved")
  const updateDecision = (action: string, value: Decision) => setDraft((current) => (current ? { ...current, permissions: { ...current.permissions, [action]: value } } : current))
  const review = async (policy: Policy) => {
    const result = await call<Record<string, unknown>>(`/policy-versions/${policy.policy_id}/simulate`, "POST", { action: Object.keys(policy.permissions)[0], has_scope: true, suspended: false, current_risk: 0 }, "Simulation complete")
    if (!result) return
    setSimulation(result)
    const found = await adminCall<{ conflicts?: Conflict[] }>(`/policy-versions/${policy.policy_id}/conflicts`, sessionToken).catch(() => ({ conflicts: [] }))
    setConflicts(found.conflicts ?? [])
  }
  const saveEmergency = () => call("/policy-emergency-controls", "PUT", emergency, "Emergency controls saved")
  const setAdapter = (adapter: PolicyAdapter, enabled: boolean, adapterEndpoint: string | null) =>
    call(`/policy-adapters/${adapter.adapter_type}`, "PUT", { enabled, endpoint: adapterEndpoint, owner: adapter.owner || "Platform Security", purpose: adapter.purpose || "External policy decision integration" }, enabled ? "Adapter enabled" : "Adapter disabled")
  const startRollout = (policy: Policy) => call("/policy-rollouts", "POST", { policy_id: policy.policy_id, percentage: 0, agent_allowlist: [] }, "Rollout staged")

  if (!sessionToken) return null
  // POST /policy-versions/drafts, PUT .../draft and POST .../submit all call require_policy_editor()
  // server-side (backend/app/api.py) - PLATFORM_ADMIN and SECURITY_ANALYST only, not AUDITOR.
  const canEditPolicy = administrator?.role !== "AUDITOR"
  const isPlatformAdmin = administrator?.role === "PLATFORM_ADMIN"

  return (
    <Panel
      id="policy-governance"
      className="policy-governance"
      eyebrow="Change control"
      title="Policy versions and approvals"
      actions={!draft && canEditPolicy && <button type="button" className="gg-button gg-button--primary" disabled={busy || !published} onClick={() => void create()}><FilePlus2 size={16} aria-hidden="true" />Create draft</button>}
    >
      <div className="gg-form">
        {loadError && <p className="gg-note gg-note--danger">{loadError}</p>}

        <section className={`gg-note ${emergency.global_deny ? "gg-note--danger" : ""} policy-emergency`} aria-label="Emergency policy controls">
          <ShieldOff size={16} aria-hidden="true" />
          <div>
            <strong>Emergency policy controls</strong>
            <span>Fail closed for every agent at once with global deny.</span>
          </div>
          <label className="gg-check"><input type="checkbox" checked={emergency.global_deny} disabled={!isPlatformAdmin} onChange={(event) => setEmergency({ ...emergency, global_deny: event.target.checked })} /> Global deny</label>
          {isPlatformAdmin && <button type="button" className={emergency.global_deny ? "gg-button gg-button--danger" : "gg-button"} disabled={busy} onClick={() => void saveEmergency()}>Save emergency controls</button>}
        </section>

        {draft && (
          <section className="gg-card" aria-label={`Draft version ${draft.version_number}`}>
            <header className="gg-card__header"><div><h3>Draft · version {draft.version_number}</h3><small>Edit, save, then submit for a second administrator's approval.</small></div><StatusBadge value="DRAFT" tone="info" /></header>
            {!canEditPolicy && <p className="gg-readonly-note">Your role has read-only access to policy drafts. Platform Administrator or Security Analyst access is required to edit or submit them.</p>}
            <div className="gg-form__row">
              <label className="gg-field">Change summary<input value={draft.change_summary} disabled={!canEditPolicy} onChange={(event) => setDraft({ ...draft, change_summary: event.target.value })} /></label>
              <label className="gg-field">Risk threshold<input type="number" value={draft.max_risk_score} disabled={!canEditPolicy} onChange={(event) => setDraft({ ...draft, max_risk_score: Number(event.target.value) })} /></label>
              <label className="gg-field">Blocked attempts<input type="number" value={draft.max_blocked_attempts} disabled={!canEditPolicy} onChange={(event) => setDraft({ ...draft, max_blocked_attempts: Number(event.target.value) })} /></label>
            </div>
            <div className="gg-table__scroll">
              <table className="policy-draft-rules" aria-label="Draft rules">
                <thead><tr><th scope="col">Action</th><th scope="col">Decision</th><th scope="col">Risk weight</th></tr></thead>
                <tbody>
                  {Object.keys(draft.permissions).sort().map((action) => (
                    <tr key={action}>
                      <td><code className="gg-code">{action}</code></td>
                      <td><select aria-label={`Decision for ${action}`} value={draft.permissions[action]} disabled={!canEditPolicy} onChange={(event) => updateDecision(action, event.target.value as Decision)}><option>ALLOW</option><option>ASK</option><option>BLOCK</option></select></td>
                      <td><input aria-label={`Risk weight for ${action}`} type="number" min="0" max="100" value={draft.risk_weights[action]} disabled={!canEditPolicy} onChange={(event) => setDraft({ ...draft, risk_weights: { ...draft.risk_weights, [action]: Number(event.target.value) } })} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {canEditPolicy && (
              <div className="gg-form__actions">
                <button type="button" className="gg-button" disabled={busy} onClick={() => void save()}><Save size={15} aria-hidden="true" />Save draft</button>
                <button type="button" className="gg-button gg-button--primary" disabled={busy} onClick={() => void call(`/policy-versions/${draft.policy_id}/submit`, "POST", undefined, "Submitted for approval")}><Send size={15} aria-hidden="true" />Submit for approval</button>
              </div>
            )}
          </section>
        )}

        <ul className="gg-list" aria-label="Policy versions">
          {versions.map((policy) => (
            <li key={policy.policy_id}>
              <div className="gg-list__main"><strong>Version {policy.version_number}</strong><small>{policy.change_summary}</small></div>
              <StatusBadge value={policy.status} tone={policy.status === "PUBLISHED" ? "success" : policy.status === "PENDING_APPROVAL" ? "warning" : policy.status === "REJECTED" ? "danger" : "neutral"} />
              <div className="gg-row-actions">
                <button type="button" className="gg-button" disabled={busy} onClick={() => void review(policy)}>Simulate & review</button>
                {policy.status === "PENDING_APPROVAL" && isPlatformAdmin && <>
                  <button type="button" className="gg-button gg-button--primary" disabled={busy} onClick={() => void call(`/policy-versions/${policy.policy_id}/approve`, "POST", undefined, "Version approved")}>Approve</button>
                  <button type="button" className="gg-button gg-button--danger" disabled={busy} onClick={() => void call(`/policy-versions/${policy.policy_id}/reject?note=Rejected%20by%20reviewer`, "POST", undefined, "Version rejected")}>Reject</button>
                </>}
                {policy.status === "ARCHIVED" && isPlatformAdmin && <button type="button" className="gg-button" disabled={busy} onClick={() => void call(`/policy-versions/${policy.policy_id}/rollback`, "POST", undefined, "Rollback draft created")}>Rollback draft</button>}
                {policy.status === "PENDING_APPROVAL" && isPlatformAdmin && <button type="button" className="gg-button" disabled={busy} onClick={() => void startRollout(policy)}><GitBranch size={14} aria-hidden="true" />Stage at 0%</button>}
              </div>
            </li>
          ))}
        </ul>

        {simulation && (
          <section className="gg-card" aria-label="Simulation result">
            <header className="gg-card__header"><div><h3>Simulation result</h3><small>{conflicts.length} conflict finding{conflicts.length === 1 ? "" : "s"}</small></div></header>
            <pre className="observability-metrics">{JSON.stringify(simulation, null, 2)}</pre>
            {conflicts.map((item) => <p key={`${item.action}-${item.detail}`} className="gg-note gg-note--warning"><strong>{item.severity}</strong> {item.action}: {item.detail}</p>)}
          </section>
        )}

        <h3 className="identity-subheading">Policy adapters</h3>
        <p className="gg-muted" style={{ margin: 0, fontSize: "0.78rem" }}>External policy engines stay disabled until a Platform Administrator assigns an HTTPS endpoint.</p>
        <div className="gg-card-grid">
          {adapters.map((adapter) => (
            <article className="gg-card" key={adapter.adapter_type}>
              <header className="gg-card__header"><span className="gg-card__icon"><Plug size={18} aria-hidden="true" /></span><div><h3>{adapter.adapter_type}</h3><small>{adapter.endpoint ?? "No endpoint"} · credentials stored: {adapter.credentials_stored ? "yes" : "no"}</small></div><StatusBadge value={adapter.enabled ? "ENABLED" : "DISABLED"} tone={adapter.enabled ? "success" : "neutral"} /></header>
              {isPlatformAdmin && <div className="gg-form__actions">{adapter.enabled
                ? <button type="button" className="gg-button" disabled={busy} onClick={() => void setAdapter(adapter, false, adapter.endpoint)}>Disable</button>
                : <button type="button" className="gg-button" disabled={busy} onClick={() => { setConfiguring(adapter); setEndpoint(adapter.endpoint ?? "") }}>Configure & enable</button>}</div>}
            </article>
          ))}
        </div>

        <h3 className="identity-subheading">Staged rollouts</h3>
        {rollouts.length === 0
          ? <p className="gg-muted" style={{ margin: 0, fontSize: "0.78rem" }}>No active or historical rollout.</p>
          : <ul className="gg-list">{rollouts.map((rollout) => <li key={rollout.rollout_id}><div className="gg-list__main"><strong>Policy {rollout.policy_id.slice(0, 8)}</strong><small>{rollout.percentage}% of agents</small></div><StatusBadge value={rollout.status} /></li>)}</ul>}
      </div>

      <ConfirmDialog
        open={Boolean(configuring)}
        title={`Enable the ${configuring?.adapter_type ?? ""} policy adapter?`}
        description="Policy decisions are then also sent to this external engine. The endpoint must use HTTPS."
        confirmLabel="Enable adapter"
        tone="warning"
        busy={busy}
        confirmDisabled={!endpoint.trim()}
        onCancel={() => setConfiguring(null)}
        onConfirm={() => { if (configuring) void setAdapter(configuring, true, endpoint).then(() => setConfiguring(null)) }}
      >
        <label className="gg-field">HTTPS endpoint<input value={endpoint} onChange={(event) => setEndpoint(event.target.value)} placeholder="https://policy.example.com/v1/decide" /></label>
      </ConfirmDialog>
    </Panel>
  )
}
