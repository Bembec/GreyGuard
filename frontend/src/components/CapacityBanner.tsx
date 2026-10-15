import { AlertTriangle } from "lucide-react"
import { Link, useLocation } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api"

type Limit = { soft: number | null; hard: number | null }
type Capacity = {
  plan_required: boolean
  soft_limits_exceeded: string[]
  limits: Record<string, Limit>
  usage: Record<string, number>
}

const METER_NAMES: Record<string, string> = {
  agents: "active agents",
  integrations: "enabled integrations",
  controlled_requests_monthly: "controlled requests this month",
  deliveries_monthly: "deliveries this month",
}

/** What the banner should say, or null when there is nothing to warn about. Request and delivery
 * volumes are monitored only, so their message never suggests anything will be refused. */
export function capacityMessage(data: Capacity | undefined): string | null {
  if (!data) return null
  if (data.plan_required) {
    return "No plan is assigned yet: new agents and integrations need a plan or trial from your GreyGuard operator. Everything already running is unaffected."
  }
  if (!data.soft_limits_exceeded.length) return null
  const parts = data.soft_limits_exceeded.map((meter) => {
    const limit = data.limits[meter]
    const cap = limit?.hard ?? limit?.soft
    return `${(data.usage[meter] ?? 0).toLocaleString()}${cap !== null && cap !== undefined ? ` of ${cap.toLocaleString()}` : ""} ${METER_NAMES[meter] ?? meter}`
  })
  const growthMeters = data.soft_limits_exceeded.filter((meter) => meter === "agents" || meter === "integrations")
  const advice = growthMeters.length
    ? " Archive what you no longer use, or ask your GreyGuard operator. Existing agents keep being enforced."
    : " This is monitored only and never interrupts security operations."
  return `Approaching your plan limits: ${parts.join(", ")}.${advice}`
}

/** Shown across the console when the org has no plan or is past a soft limit. */
export function CapacityBanner() {
  const location = useLocation()
  const capacity = useQuery({
    queryKey: ["entitlements", "banner", location.pathname],
    refetchInterval: 30_000,
    staleTime: 10_000,
    queryFn: async (): Promise<Capacity> => {
      const response = await fetch(`${API_BASE_URL}/entitlements`, {
        headers: { "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" },
      })
      if (!response.ok) throw new Error(String(response.status))
      return response.json()
    },
  })
  const message = capacityMessage(capacity.data)
  if (!message) return null
  return (
    <div className="capacity-banner" role="status">
      <AlertTriangle size={16} aria-hidden />
      <span>{message}</span>
      <Link to="/settings">Plan &amp; usage</Link>
    </div>
  )
}
