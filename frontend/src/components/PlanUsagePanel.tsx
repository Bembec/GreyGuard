import { Gauge } from "lucide-react"
import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { ErrorState, LoadingState } from "./AsyncState"
import { useAuth } from "../context/AuthContext"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api"

type Limit = { soft: number | null; hard: number | null }

export type Entitlements = {
  plan: string
  plan_label: string
  status: "ACTIVE" | "TRIAL" | "EXPIRED" | "SUSPENDED"
  trial_ends_at: string | null
  restricted: boolean
  restriction_reasons: string[]
  features: string[]
  mandatory_protections: string[]
  limits: Record<string, Limit>
  usage: Record<string, number>
  soft_limits_exceeded: string[]
}

const METER_LABELS: Record<string, string> = {
  agents: "Agents",
  controlled_requests_monthly: "Controlled requests this month",
  deliveries_monthly: "Deliveries this month",
  integrations: "Integrations",
}

export type Billing = {
  enabled: boolean
  linked: boolean
  billing_state?: "ACTIVE" | "PAST_DUE" | "CANCELED"
  grace_ends_at?: string | null
}

const RESTRICTION_LABELS: Record<string, string> = {
  PLAN_EXPIRED: "the plan has expired",
  PLAN_SUSPENDED: "the plan is suspended",
  PAYMENT_OVERDUE: "payment is overdue",
  SUBSCRIPTION_CANCELED: "the subscription is cancelled",
  LICENSE_LAPSED: "this install's licence has lapsed",
  LICENSE_MISSING: "this install has no valid licence",
}

const readable = (value: string) => value.replaceAll("_", " ")

export function restrictionSummary(reasons: string[]): string {
  return reasons.map((reason) => RESTRICTION_LABELS[reason] ?? readable(reason).toLowerCase()).join(" and ")
}

export function billingSummary(billing: Billing): string | null {
  if (!billing.linked) return null
  if (billing.billing_state === "PAST_DUE") {
    return billing.grace_ends_at
      ? `Payment overdue · grace until ${new Date(billing.grace_ends_at).toLocaleDateString()}`
      : "Payment overdue"
  }
  return billing.billing_state === "CANCELED" ? "Subscription cancelled" : "Active"
}

export function meterSummary(used: number, limit: Limit): string {
  const cap = limit.hard ?? limit.soft
  return cap === null ? `${used.toLocaleString()} · unlimited` : `${used.toLocaleString()} of ${cap.toLocaleString()}`
}

// Assignable plans only: TRANSITIONAL exists solely for orgs carried over by the D6 migration.
export const ASSIGNABLE_PLANS = ["UNASSIGNED", "FOUNDATION", "ENTERPRISE", "DEDICATED"] as const
export const PLAN_STATUSES = ["ACTIVE", "TRIAL", "EXPIRED", "SUSPENDED"] as const
const MAX_TRIAL_DAYS = 90 // entitlements.MAX_TRIAL_DAYS

export type PlanForm = {
  plan: (typeof ASSIGNABLE_PLANS)[number]
  status: (typeof PLAN_STATUSES)[number]
  trialDays: string
  agentsSoft: string
  agentsHard: string
  integrationsSoft: string
  integrationsHard: string
}

const wholeNumber = (value: string) => (/^\d+$/.test(value.trim()) ? Number(value) : null)

/** The PUT /entitlements/{org_id} body for the form, or the reason it cannot be sent yet. The
 * server re-validates all of this; checking here only avoids a round trip for an obvious gap. */
export function planAssignmentPayload(form: PlanForm): { body: Record<string, unknown> } | { error: string } {
  const body: Record<string, unknown> = { plan: form.plan, status: form.status }
  if (form.status === "TRIAL") {
    const days = wholeNumber(form.trialDays)
    if (days === null || days < 1 || days > MAX_TRIAL_DAYS) return { error: `A trial needs a length of 1 to ${MAX_TRIAL_DAYS} days.` }
    body.trial_days = days
  }
  if (form.plan === "DEDICATED") {
    const limits = {
      agents: { soft: wholeNumber(form.agentsSoft), hard: wholeNumber(form.agentsHard) },
      integrations: { soft: wholeNumber(form.integrationsSoft), hard: wholeNumber(form.integrationsHard) },
    }
    for (const [meter, { soft, hard }] of Object.entries(limits)) {
      if (soft === null || hard === null) return { error: `Enter the contract's ${meter} limits as whole numbers.` }
      if (soft > hard) return { error: `The contract's soft ${meter} limit cannot exceed its hard limit.` }
    }
    body.contract_limits = limits
  }
  return { body }
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" },
  })
  if (!response.ok) throw new Error(`Plan details could not be loaded (${response.status}).`)
  return response.json()
}

function OperatorPlanAssignment({ orgId, current }: { orgId: string; current: Entitlements }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<PlanForm>({
    plan: (ASSIGNABLE_PLANS as readonly string[]).includes(current.plan) ? (current.plan as PlanForm["plan"]) : "FOUNDATION",
    status: current.status,
    trialDays: "30",
    agentsSoft: "",
    agentsHard: "",
    integrationsSoft: "",
    integrationsHard: "",
  })
  const [message, setMessage] = useState<{ tone: "alert" | "status"; text: string } | null>(null)
  const prepared = planAssignmentPayload(form)
  const assign = useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      const response = await fetch(`${API_BASE_URL}/entitlements/${encodeURIComponent(orgId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" },
        body: JSON.stringify(body),
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : `Plan could not be assigned (${response.status}).`)
      return result as Entitlements
    },
    onSuccess: (result) => {
      setMessage({ tone: "status", text: `Assigned ${result.plan_label} (${result.status}). The change is recorded in the entitlement history.` })
      void queryClient.invalidateQueries({ queryKey: ["entitlements"] })
    },
    onError: (error: Error) => setMessage({ tone: "alert", text: error.message }),
  })
  const update = (key: keyof PlanForm) => (event: { target: { value: string } }) => setForm({ ...form, [key]: event.target.value })
  const limitInput = (key: keyof PlanForm, label: string) => (
    <label>
      {label}
      <input inputMode="numeric" value={form[key]} onChange={update(key)} />
    </label>
  )

  return (
    <form
      className="plan-assignment"
      onSubmit={(event) => {
        event.preventDefault()
        if ("body" in prepared) assign.mutate(prepared.body)
      }}
    >
      <h3>Install operator · assign plan</h3>
      <p>Applies to this organization only. Hard limits block new growth; they never interrupt existing controls.</p>
      <div className="plan-assignment__row">
        <label>
          Plan
          <select value={form.plan} onChange={update("plan")}>
            {ASSIGNABLE_PLANS.map((plan) => <option key={plan} value={plan}>{readable(plan)}</option>)}
          </select>
        </label>
        <label>
          Status
          <select value={form.status} onChange={update("status")}>
            {PLAN_STATUSES.map((status) => <option key={status} value={status}>{readable(status)}</option>)}
          </select>
        </label>
        {form.status === "TRIAL" && (
          <label>
            Trial length (days)
            <input inputMode="numeric" value={form.trialDays} onChange={update("trialDays")} />
          </label>
        )}
      </div>
      {form.plan === "DEDICATED" && (
        <fieldset className="plan-assignment__row">
          <legend>Contract limits</legend>
          {limitInput("agentsSoft", "Agents · soft")}
          {limitInput("agentsHard", "Agents · hard")}
          {limitInput("integrationsSoft", "Integrations · soft")}
          {limitInput("integrationsHard", "Integrations · hard")}
        </fieldset>
      )}
      {"error" in prepared && <p className="plan-assignment__hint">{prepared.error}</p>}
      <button type="submit" disabled={"error" in prepared || assign.isPending}>
        {assign.isPending ? "Assigning…" : "Assign plan"}
      </button>
      {message && <p role={message.tone}>{message.text}</p>}
    </form>
  )
}

/** The active org's plan, limits and usage - read-only for every role, so each can see what
 * governs its org. Plans are assigned by install operators, who also get the assignment form. */
export function PlanUsagePanel() {
  const { administrator } = useAuth()
  const orgId = administrator?.active_org_id ?? null
  const entitlements = useQuery({ queryKey: ["entitlements"], queryFn: () => fetchJson<Entitlements>("/entitlements") })
  const billing = useQuery({ queryKey: ["billing"], queryFn: () => fetchJson<Billing>("/billing") })
  const data = entitlements.data
  const billingLine = billing.data ? billingSummary(billing.data) : null

  return (
    <section className="settings-panel">
      <div className="settings-panel-heading">
        <div className="settings-heading-icon">
          <Gauge size={20} />
        </div>
        <div>
          <span>Organization plan</span>
          <h2>Plan &amp; usage</h2>
        </div>
      </div>

      {entitlements.isLoading && <LoadingState label="Loading plan details" rows={2} />}
      {entitlements.isError && (
        <ErrorState message={entitlements.error.message} onRetry={() => void entitlements.refetch()} />
      )}
      {data && (
        <>
          {data.restricted && (
            <p className="plan-notice" role="status">
              Restricted because {restrictionSummary(data.restriction_reasons)}. New agents and integrations are
              paused; evidence, exports and every security control remain available.
            </p>
          )}
          <div className="environment-list">
            <div>
              <span>Plan</span>
              <code>{data.plan_label}</code>
            </div>
            <div>
              <span>Status</span>
              <code>
                {data.status}
                {data.status === "TRIAL" && data.trial_ends_at
                  ? ` · ends ${new Date(data.trial_ends_at).toLocaleDateString()}`
                  : ""}
              </code>
            </div>
            {billingLine && (
              <div>
                <span>Billing</span>
                <code>{billingLine}</code>
              </div>
            )}
            {Object.entries(data.limits).map(([meter, limit]) => (
              <div key={meter}>
                <span>
                  {METER_LABELS[meter] ?? readable(meter)}
                  {data.soft_limits_exceeded.includes(meter) ? " · approaching limit" : ""}
                </span>
                <code>{meterSummary(data.usage[meter] ?? 0, limit)}</code>
              </div>
            ))}
            <div>
              <span>Included features</span>
              <code>{data.features.length ? data.features.map(readable).join(", ") : "Core controls only"}</code>
            </div>
            <div>
              <span>Always included</span>
              <code>{data.mandatory_protections.map(readable).join(", ")}</code>
            </div>
          </div>
          {administrator?.install_operator && orgId && <OperatorPlanAssignment key={`${orgId}:${data.plan}:${data.status}`} orgId={orgId} current={data} />}
        </>
      )}
    </section>
  )
}
