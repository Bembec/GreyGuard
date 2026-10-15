import { CheckCircle2, Circle, Flag, Rocket } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { ErrorState, LoadingState } from "../components/AsyncState"
import { progressLabel, stepFor } from "../config/onboardingSteps"
import { useAuth } from "../context/AuthContext"
import "../styles/getting-started.css"

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"

type ChecklistItem = { key: string; label: string; done: boolean }
type Lifecycle = { status: string; checklist: ChecklistItem[]; checklist_complete: number }
type Criterion = { key: string; label: string; met: boolean; manual: boolean; evidence: string; confirmation?: { by: string; at: string; note: string } }
export type Pilot = {
  status: string; days_remaining: number; decision_due: boolean; decision_due_at: string; ends_at: string
  extended: number; criteria: Criterion[]; criteria_met: number; criteria_total: number; decision?: string | null
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail ?? `Request failed (${response.status}).`)
  return body as T
}

export function pilotHeadline(pilot: Pilot): string {
  if (pilot.status !== "ACTIVE") return `Pilot ${pilot.status.toLowerCase()}`
  if (pilot.decision_due) return "Conversion decision due"
  return `${pilot.days_remaining} days left in your pilot`
}

function OperatorPilotControls({ orgId, pilot }: { orgId: string; pilot: Pilot }) {
  const queryClient = useQueryClient()
  const [note, setNote] = useState("")
  const [reason, setReason] = useState("")
  const [error, setError] = useState<string | null>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["pilot", orgId] })
  const confirm = useMutation({
    mutationFn: (criterion: string) => call(`/organizations/${orgId}/pilot/confirmations`, { method: "POST", body: JSON.stringify({ criterion, note }) }),
    onSuccess: () => { setNote(""); setError(null); void refresh() },
    onError: (e: Error) => setError(e.message),
  })
  const decide = useMutation({
    mutationFn: (outcome: string) => call(`/organizations/${orgId}/pilot/decision`, {
      method: "POST", body: JSON.stringify({ outcome, reason, ...(outcome === "EXTEND" ? { extend_days: 30 } : {}) }),
    }),
    onSuccess: () => { setReason(""); setError(null); void refresh() },
    onError: (e: Error) => setError(e.message),
  })
  if (pilot.status !== "ACTIVE") return null
  const unconfirmed = pilot.criteria.filter((c) => c.manual && !c.confirmation)
  return (
    <div className="pilot-operator">
      <h3>Install operator</h3>
      {unconfirmed.length > 0 && (
        <label>
          Confirmation note (who confirmed what)
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Head of Internal Audit accepted the export" />
          <span className="pilot-buttons">
            {unconfirmed.map((c) => (
              <button key={c.key} type="button" disabled={note.trim().length < 10 || confirm.isPending} onClick={() => confirm.mutate(c.key)}>
                Confirm: {c.label}
              </button>
            ))}
          </span>
        </label>
      )}
      <label>
        Decision reason
        <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why this outcome" />
        <span className="pilot-buttons">
          <button type="button" disabled={reason.trim().length < 10 || decide.isPending} onClick={() => decide.mutate("CONVERT")}>Convert</button>
          {!pilot.extended && <button type="button" disabled={reason.trim().length < 10 || decide.isPending} onClick={() => decide.mutate("EXTEND")}>Extend 30 days</button>}
          <button type="button" className="danger" disabled={reason.trim().length < 10 || decide.isPending} onClick={() => decide.mutate("OFFBOARD")}>Offboard</button>
        </span>
      </label>
      {error && <p role="alert">{error}</p>}
    </div>
  )
}

/** Guided onboarding: the readiness checklist as steps, and the pilot's measured success criteria. */
export default function GettingStartedPage() {
  const { administrator } = useAuth()
  const orgId = administrator?.active_org_id ?? null
  const lifecycle = useQuery({ queryKey: ["organization-lifecycle", orgId], enabled: Boolean(orgId),
    queryFn: () => call<Lifecycle>(`/organizations/${orgId}/lifecycle`) })
  const pilot = useQuery({ queryKey: ["pilot", orgId], enabled: Boolean(orgId),
    queryFn: async () => (await call<{ pilot: Pilot | null }>(`/organizations/${orgId}/pilot`)).pilot })

  const items = lifecycle.data?.checklist ?? []
  const done = items.filter((item) => item.done).length

  return (
    <main className="getting-started">
      <section className="getting-started-hero">
        <p><Rocket size={15} /> Onboarding</p>
        <h1>Getting started</h1>
        <span>{lifecycle.data ? progressLabel(done, items.length) : "Your path from first agent to governed production."}</span>
        {items.length > 0 && (
          <div className="getting-started-progress" role="progressbar" aria-valuemin={0} aria-valuemax={items.length} aria-valuenow={done}>
            <div style={{ width: `${(done / items.length) * 100}%` }} />
          </div>
        )}
      </section>

      {!orgId && <p>Choose an organization to see its onboarding.</p>}
      {lifecycle.isLoading && <LoadingState label="Loading your onboarding steps" rows={3} />}
      {lifecycle.isError && <ErrorState message={lifecycle.error.message} onRetry={() => void lifecycle.refetch()} />}

      {pilot.data && (
        <section className="pilot-panel" aria-labelledby="pilot-heading">
          <h2 id="pilot-heading"><Flag size={18} /> {pilotHeadline(pilot.data)}</h2>
          <p>
            {pilot.data.criteria_met} of {pilot.data.criteria_total} success criteria met · decision due{" "}
            {new Date(pilot.data.decision_due_at).toLocaleDateString()} · ends {new Date(pilot.data.ends_at).toLocaleDateString()}
          </p>
          <ul className="getting-started-steps">
            {pilot.data.criteria.map((criterion) => (
              <li key={criterion.key} className={criterion.met ? "is-done" : undefined}>
                {criterion.met ? <CheckCircle2 size={18} aria-hidden /> : <Circle size={18} aria-hidden />}
                <div>
                  <strong>{criterion.label}</strong>
                  <span>{criterion.evidence}{criterion.manual && !criterion.confirmation ? " · confirmed by your GreyGuard operator" : ""}</span>
                  {criterion.confirmation && <span>Confirmed: {criterion.confirmation.note}</span>}
                </div>
              </li>
            ))}
          </ul>
          {administrator?.install_operator && orgId && <OperatorPilotControls orgId={orgId} pilot={pilot.data} />}
        </section>
      )}

      {items.length > 0 && (
        <section aria-labelledby="steps-heading">
          <h2 id="steps-heading">Readiness steps</h2>
          <ol className="getting-started-steps">
            {items.map((item) => {
              const step = stepFor(item.key)
              return (
                <li key={item.key} className={item.done ? "is-done" : undefined}>
                  {item.done ? <CheckCircle2 size={18} aria-hidden /> : <Circle size={18} aria-hidden />}
                  <div>
                    <strong>{item.label}</strong>
                    {step.why && <span>{step.why}</span>}
                    {step.who && <span className="step-who">Who: {step.who}</span>}
                  </div>
                  {!item.done && (step.href ? <Link to={step.href}>{step.action}</Link> : <em>{step.action}</em>)}
                </li>
              )
            })}
          </ol>
        </section>
      )}
    </main>
  )
}
