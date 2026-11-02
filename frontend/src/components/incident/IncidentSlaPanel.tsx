import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Clock3 } from "lucide-react"
import { useState } from "react"

import { ErrorState, LoadingState } from "../AsyncState"
import { ConfirmDialog } from "../ConfirmDialog"
import { useAuth } from "../../context/AuthContext"
import { useToast } from "../../context/ToastContext"
import { formatMinutes, formFrom, PHASES, readForm, type Field, type Form, type Phase, type SlaSettings, type SlaSeverity, type SlaTarget, type Unit } from "../../lib/incidentSla"

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"
async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "", ...init.headers },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error((body as { detail?: string }).detail ?? `Request failed with status ${response.status}.`)
  return body as T
}

export function IncidentSlaPanel() {
  const { administrator } = useAuth()
  const orgId = administrator?.active_org_id ?? null
  const queryClient = useQueryClient()
  const { pushToast } = useToast()
  // Edits are a draft over the saved targets; a save (a new updated_at) starts again from what was saved.
  const [draft, setDraft] = useState<{ version: string; form: Form } | null>(null)
  const [clearing, setClearing] = useState(false)

  const settings = useQuery({
    queryKey: ["incident-sla", orgId],
    enabled: Boolean(orgId),
    queryFn: () => call<SlaSettings>(`/organizations/${encodeURIComponent(orgId!)}/incident-sla`),
  })

  const save = useMutation({
    mutationFn: (targets: Partial<Record<SlaSeverity, SlaTarget>>) =>
      call<SlaSettings>(`/organizations/${encodeURIComponent(orgId!)}/incident-sla`, { method: "PUT", body: JSON.stringify({ targets }) }),
    onSuccess: (result) => {
      setClearing(false)
      queryClient.setQueryData(["incident-sla", orgId], result)
      void queryClient.invalidateQueries({ queryKey: ["alerts"] })
      void queryClient.invalidateQueries({ queryKey: ["incident-workspace"] })
      pushToast({ tone: "success", title: result.configured ? "Response targets saved" : "Response targets cleared",
        message: result.configured ? "Every incident is now measured against them." : "Incidents show No SLA set again." })
    },
    onError: (error: Error) => pushToast({ tone: "error", title: "Not saved", message: error.message }),
  })

  if (!orgId) return null
  if (settings.isLoading) return <section className="incident-sla" aria-label="Response targets"><LoadingState label="Loading response targets" rows={2} /></section>
  if (settings.isError) return <section className="incident-sla" aria-label="Response targets"><ErrorState message={settings.error.message} onRetry={() => void settings.refetch()} /></section>
  const data = settings.data!
  const version = data.updated_at ?? "none"
  const form = draft?.version === version ? draft.form : formFrom(data.targets, data.severities)
  const setForm = (next: Form) => setDraft({ version, form: next })
  const parsed = readForm(form)
  const set = (severity: SlaSeverity, phase: Phase, field: Partial<Field>) =>
    setForm({ ...form, [severity]: { ...form[severity], [phase]: { ...form[severity][phase], ...field } } })

  return (
    <section className="incident-sla" aria-labelledby="incident-sla-heading" id="response-targets">
      <header>
        <h2 id="incident-sla-heading"><Clock3 size={16} aria-hidden="true" /> Response targets</h2>
        <p>{data.configured
          ? <>Set by {data.updated_by}. {data.basis}</>
          : <>No SLA set. Incidents show no deadlines until your organization sets targets; GreyGuard never assumes one.</>}</p>
      </header>

      {!data.can_edit ? (
        <dl className="incident-sla__read">
          {data.severities.map((severity) => (
            <div key={severity}><dt>{severity}</dt><dd>
              {data.targets[severity] ? `Acknowledge: ${formatMinutes(data.targets[severity]!.acknowledge_minutes)} · Resolve: ${formatMinutes(data.targets[severity]!.resolve_minutes)}` : "No target"}
            </dd></div>
          ))}
          <p className="incident-sla__hint">Only a Platform Administrator can change response targets.</p>
        </dl>
      ) : (
        <form onSubmit={(event) => { event.preventDefault(); if ("targets" in parsed) save.mutate(parsed.targets) }}>
          {data.suggestions && (
            <p className="incident-sla__hint">
              Suggested starting points: Critical, acknowledge in 15 minutes and resolve in 4 hours; High, 1 hour and 24 hours.{" "}
              <button type="button" className="gg-button" onClick={() => setForm(formFrom(data.suggestions!, data.severities))}>Fill in the suggestions</button>
              {" "}Nothing is saved until you choose Save.
            </p>
          )}
          <div className="incident-sla__grid">
            {data.severities.map((severity) => (
              <fieldset key={severity}>
                <legend>{severity}</legend>
                {PHASES.map(([phase, label]) => {
                  const id = `sla-${severity}-${phase}`
                  return (
                    <div key={phase} className="incident-sla__field">
                      <label htmlFor={id}>{label}</label>
                      <input id={id} inputMode="numeric" value={form[severity][phase].value} placeholder="No target"
                        onChange={(event) => set(severity, phase, { value: event.target.value })} />
                      <select aria-label={`${label}: unit for ${severity.toLowerCase()}`} value={form[severity][phase].unit}
                        onChange={(event) => set(severity, phase, { unit: event.target.value as Unit })}>
                        <option value="minutes">minutes</option><option value="hours">hours</option><option value="days">days</option>
                      </select>
                    </div>
                  )
                })}
              </fieldset>
            ))}
          </div>
          {"error" in parsed && parsed.error && <p className="incident-sla__error" role="alert">{parsed.error}</p>}
          <footer>
            <button type="submit" className="gg-button gg-button--primary" disabled={"error" in parsed || save.isPending}>Save targets</button>
            {data.configured && <button type="button" className="gg-button" disabled={save.isPending} onClick={() => setClearing(true)}>Remove all targets</button>}
          </footer>
        </form>
      )}

      <ConfirmDialog open={clearing} title="Remove all response targets?" tone="warning"
        description="Every incident will show No SLA set, and breaches will no longer be reported. You can set targets again at any time."
        confirmLabel="Remove targets" busy={save.isPending} onCancel={() => setClearing(false)} onConfirm={() => save.mutate({})} />
    </section>
  )
}
