import { Gauge } from "lucide-react"
import { useQuery } from "@tanstack/react-query"

import { ErrorState, LoadingState } from "./AsyncState"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api"

type Limit = { soft: number | null; hard: number | null }

export type Entitlements = {
  plan: string
  plan_label: string
  status: "ACTIVE" | "TRIAL" | "EXPIRED" | "SUSPENDED"
  trial_ends_at: string | null
  restricted: boolean
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

const readable = (value: string) => value.replaceAll("_", " ")

export function meterSummary(used: number, limit: Limit): string {
  const cap = limit.hard ?? limit.soft
  return cap === null ? `${used.toLocaleString()} · unlimited` : `${used.toLocaleString()} of ${cap.toLocaleString()}`
}

async function fetchEntitlements(): Promise<Entitlements> {
  const response = await fetch(`${API_BASE_URL}/entitlements`, {
    headers: { "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" },
  })
  if (!response.ok) throw new Error(`Plan details could not be loaded (${response.status}).`)
  return response.json()
}

/** Read-only view of the active org's plan, limits and usage. Plans are assigned by install
 * operators; every role can see what governs its org. */
export function PlanUsagePanel() {
  const entitlements = useQuery({ queryKey: ["entitlements"], queryFn: fetchEntitlements })
  const data = entitlements.data

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
              This plan is {data.status.toLowerCase()}. New agents and integrations are paused; evidence,
              exports and every security control remain available.
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
        </>
      )}
    </section>
  )
}
