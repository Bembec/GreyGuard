import { useQuery } from "@tanstack/react-query"

import "../styles/status-page.css"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api"

type ComponentState = "OPERATIONAL" | "DEGRADED" | "MAJOR_OUTAGE" | "MAINTENANCE" | "NOT_RUNNING" | "NOT_CONFIGURED"

type ServiceStatus = {
  status: ComponentState
  components: Record<string, ComponentState>
  incidents: { incident_id: string; title: string; severity: string; state: string; started_at: string; updates: { timestamp: string; state: string; message: string }[] }[]
  maintenance: { maintenance_id: string; title: string; starts_at: string; ends_at: string; in_progress: boolean }[]
  generated_at: string
  note: string
}

const COMPONENT_LABELS: Record<string, string> = {
  api: "Control-plane API",
  database: "Database",
  delivery_worker: "Evidence and alert delivery",
  policy_distribution: "Gateway policy distribution",
}

const STATE_LABELS: Record<ComponentState, string> = {
  OPERATIONAL: "Operational",
  DEGRADED: "Degraded",
  MAJOR_OUTAGE: "Major outage",
  MAINTENANCE: "Maintenance",
  NOT_RUNNING: "Not running on this install",
  NOT_CONFIGURED: "Not configured on this install",
}

export function stateLabel(state: string): string {
  return STATE_LABELS[state as ComponentState] ?? state.replaceAll("_", " ").toLowerCase()
}

/** Public, tenant-free status of the operated service. Needs no sign-in. */
export function StatusPage() {
  const status = useQuery({
    queryKey: ["public-status"],
    refetchInterval: 60_000,
    queryFn: async (): Promise<ServiceStatus> => {
      const response = await fetch(`${API_BASE_URL}/status`)
      if (!response.ok) throw new Error(`Status could not be loaded (${response.status}).`)
      return response.json()
    },
  })
  const data = status.data

  return (
    <main className="status-page">
      <h1>GreyGuard service status</h1>
      {status.isLoading && <p>Checking service status…</p>}
      {status.isError && (
        <p role="alert" className="status-banner state-major_outage">
          The status service itself could not be reached. {status.error.message}
        </p>
      )}
      {data && (
        <>
          <p role="status" className={`status-banner state-${data.status.toLowerCase()}`}>
            {data.status === "OPERATIONAL" ? "All systems operational" : stateLabel(data.status)}
          </p>
          <ul className="status-components">
            {Object.entries(data.components).map(([component, state]) => (
              <li key={component}>
                <span>{COMPONENT_LABELS[component] ?? component}</span>
                <span className={`state-${state.toLowerCase()}`}>{stateLabel(state)}</span>
              </li>
            ))}
          </ul>
          {data.incidents.map((incident) => (
            <section key={incident.incident_id} className="status-incident">
              <h2>
                {incident.severity} · {incident.title}
              </h2>
              {incident.updates.map((update) => (
                <p key={update.timestamp}>
                  <strong>{stateLabel(update.state)}</strong> · {new Date(update.timestamp).toLocaleString()} — {update.message}
                </p>
              ))}
            </section>
          ))}
          {data.maintenance.map((window) => (
            <section key={window.maintenance_id} className="status-incident">
              <h2>
                {window.in_progress ? "Maintenance in progress" : "Scheduled maintenance"} · {window.title}
              </h2>
              <p>
                {new Date(window.starts_at).toLocaleString()} – {new Date(window.ends_at).toLocaleString()}
              </p>
            </section>
          ))}
          <p className="status-note">{data.note}</p>
          <p className="status-note">Updated {new Date(data.generated_at).toLocaleString()}</p>
        </>
      )}
    </main>
  )
}
