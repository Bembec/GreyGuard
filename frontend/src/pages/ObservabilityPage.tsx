import { useQuery } from "@tanstack/react-query"
import { Activity, Braces, Download, RefreshCw, Save, ShieldCheck, Waypoints } from "lucide-react"
import { useState } from "react"
import { Navigate } from "react-router-dom"

import { ErrorState, LoadingState } from "../components/AsyncState"
import { Guidance } from "../components/page/Guidance"
import { PageHeader } from "../components/page/PageHeader"
import { Panel } from "../components/page/Panel"
import { StatCard, StatGrid } from "../components/page/StatCard"
import { relativeTime } from "../components/page/timeFormat"
import { useAuth } from "../context/AuthContext"
import { useToast } from "../context/ToastContext"
import { adminCall } from "../lib/adminApi"

export type ObservabilityConfig = { tracing_enabled: boolean; metrics_enabled: boolean; structured_logs_enabled: boolean; sample_rate: number; retention_limit: number; updated_at: string; updated_by: string }

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"

export const samplingPercent = (rate: number) => `${Math.round(rate * 100)}%`

const TOGGLES = [["tracing_enabled", "OpenTelemetry traces"], ["metrics_enabled", "Prometheus metrics"], ["structured_logs_enabled", "Structured JSON logs"]] as const

async function loadMetrics(token: string | null): Promise<string> {
  const response = await fetch(`${API}/observability/metrics`, { headers: { "X-Admin-Pin": token ?? "" } })
  return response.ok ? await response.text() : "Metrics unavailable."
}

export default function ObservabilityPage() {
  const { sessionToken, administrator } = useAuth()
  const { pushToast } = useToast()
  const allowed = Boolean(sessionToken) && Boolean(administrator?.install_operator)
  const config = useQuery({ queryKey: ["observability-config"], queryFn: () => adminCall<ObservabilityConfig>("/observability/config", sessionToken), enabled: allowed })
  const metrics = useQuery({ queryKey: ["observability-metrics"], queryFn: () => loadMetrics(sessionToken), enabled: allowed })
  const [draft, setDraft] = useState<Partial<ObservabilityConfig>>({})
  const [busy, setBusy] = useState(false)

  if (!administrator?.install_operator) return <Navigate to="/dashboard" replace />

  const current = config.data ? { ...config.data, ...draft } : null
  const dirty = Object.keys(draft).length > 0

  const save = async () => {
    if (!current) return
    setBusy(true)
    try {
      await adminCall("/observability/config", sessionToken, { method: "PUT", body: current })
      pushToast({ tone: "success", title: "Observability controls updated", message: "Changes apply to new requests." })
      await config.refetch()
      setDraft({})
    } catch (error) {
      pushToast({ tone: "error", title: "Observability update failed", message: error instanceof Error ? error.message : "Request failed." })
    } finally {
      setBusy(false)
    }
  }

  const exportTraces = async () => {
    try {
      const body = await adminCall<unknown>("/observability/traces", sessionToken)
      const url = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }))
      const link = document.createElement("a")
      link.href = url
      link.download = "greyguard-otlp-traces.json"
      link.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      pushToast({ tone: "error", title: "Trace export failed", message: error instanceof Error ? error.message : "Request failed." })
    }
  }

  const metricLines = (metrics.data ?? "").split("\n").filter((line) => line && !line.startsWith("#")).length

  return (
    <section className="gg-page">
      <PageHeader
        title="Observability"
        icon={<Waypoints size={22} />}
        description="Install-wide telemetry: trace sampling, Prometheus metrics, structured logs and redacted OTLP trace export."
        actions={<button type="button" className="gg-button" onClick={() => { void config.refetch(); void metrics.refetch() }}><RefreshCw size={16} aria-hidden="true" />Refresh</button>}
      />

      <p className="gg-note"><ShieldCheck size={16} aria-hidden="true" /><span><strong>Redaction before export.</strong> Credentials, tokens, secrets, passwords, authorization values and PINs are removed before telemetry is stored or exported.</span></p>

      <Guidance id="observability" title="Choosing telemetry settings">
        <ul>
          <li>Lower <strong>sampling</strong> reduces trace volume; 100% records every request. Changes apply to new requests only.</li>
          <li><strong>Retained spans</strong> caps how many traces are kept for export.</li>
          <li>Scrape the metrics endpoint from Prometheus, or export traces here as OTLP JSON for your tracing tool.</li>
        </ul>
      </Guidance>

      {config.isLoading && <LoadingState label="Loading observability controls" rows={3} />}
      {config.isError && <ErrorState message={config.error.message} onRetry={() => void config.refetch()} />}
      {current && config.data && (
        <>
          <StatGrid label="Telemetry summary">
            <StatCard label="Traces" value={config.data.tracing_enabled ? "On" : "Off"} hint={`Sampling ${samplingPercent(config.data.sample_rate)}`} tone={config.data.tracing_enabled ? "success" : "neutral"} />
            <StatCard label="Metrics" value={config.data.metrics_enabled ? "On" : "Off"} hint={`${metricLines} series in the preview`} tone={config.data.metrics_enabled ? "success" : "neutral"} />
            <StatCard label="Structured logs" value={config.data.structured_logs_enabled ? "On" : "Off"} hint="JSON log output" tone={config.data.structured_logs_enabled ? "success" : "neutral"} />
            <StatCard label="Last changed" value={relativeTime(config.data.updated_at)} hint={`by ${config.data.updated_by}`} />
          </StatGrid>

          <div className="gg-layout gg-layout--even">
            <Panel id="observability-controls" eyebrow="Collection" title="Collection controls">
              <form className="gg-form" onSubmit={(event) => { event.preventDefault(); void save() }}>
                {TOGGLES.map(([key, label]) => (
                  <label className="gg-check" key={key}>
                    <input type="checkbox" checked={current[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.checked })} />
                    <span>{label}</span>
                  </label>
                ))}
                <label className="gg-field">Trace sampling: {samplingPercent(current.sample_rate)}
                  <input type="range" min="0" max="1" step="0.05" value={current.sample_rate} onChange={(event) => setDraft({ ...draft, sample_rate: Number(event.target.value) })} />
                </label>
                <label className="gg-field">Retained spans<input type="number" min="100" max="100000" value={current.retention_limit} onChange={(event) => setDraft({ ...draft, retention_limit: Number(event.target.value) })} /></label>
                <div className="gg-form__actions">
                  {dirty && <button type="button" className="gg-button" onClick={() => setDraft({})}>Discard changes</button>}
                  <button type="submit" className="gg-button gg-button--primary" disabled={busy || !dirty}><Save size={16} aria-hidden="true" />Save controls</button>
                </div>
              </form>
            </Panel>

            <Panel id="observability-metrics" eyebrow="Preview" title="Prometheus metrics" actions={<button type="button" className="gg-button" onClick={() => void exportTraces()}><Download size={15} aria-hidden="true" />Export OTLP traces</button>}>
              {metrics.isLoading
                ? <LoadingState label="Loading metrics" rows={2} />
                : <pre className="observability-metrics" tabIndex={0} aria-label="Prometheus metrics preview"><Braces size={14} aria-hidden="true" /> {metrics.data || "No request metrics recorded yet."}</pre>}
              <p className="gg-muted" style={{ fontSize: "0.74rem", margin: "0.5rem 0 0" }}><Activity size={13} aria-hidden="true" /> Credential-free scrape format.</p>
            </Panel>
          </div>
        </>
      )}
    </section>
  )
}
