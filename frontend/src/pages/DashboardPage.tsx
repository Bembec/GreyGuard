import { useQuery } from "@tanstack/react-query"
import {
  Activity,
  Bell,
  Bot,
  CheckSquare,
  ClipboardList,
  FileCheck2,
  FileSearch,
  Gauge,
  LayoutGrid,
  LockKeyhole,
  RefreshCw,
  ShieldAlert,
  X,
} from "lucide-react"
import { useRef, useState, type ReactNode } from "react"
import { Link } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { DataTable, type Column } from "../components/page/DataTable"
import { PageHeader } from "../components/page/PageHeader"
import { Panel } from "../components/page/Panel"
import { StatCard, StatGrid } from "../components/page/StatCard"
import { StatusBadge } from "../components/page/StatusBadge"
import { greetingFor, relativeTime } from "../components/page/timeFormat"
import {
  PANELS,
  PANEL_ORDER,
  parseCustomization,
  resolveLayout,
  storageKeyFor,
  togglePanel,
  type Customization,
  type KpiId,
  type PanelId,
} from "../config/commandCenter"
import { useAuth } from "../context/AuthContext"
import { useDismissableLayer } from "../hooks/useDismissableLayer"
import type { Agent } from "../types/api"
import "../styles/pages.css"

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"

type ToolRequest = { request_id: string; agent_name: string; timestamp: string; action: string; target: string; policy_decision: string; approval_status: string; risk_score: number }
type AlertSummary = { total: number; open: number; in_progress: number; closed: number; active_critical: number }
type NotificationSummary = { total: number; unread: number; unread_critical: number; unread_high: number }
type Alert = { alert_id: string; severity: string; status: string; title: string; agent_name: string | null; created_at: string }
type AuditEvent = { event_id: string; event_type: string; timestamp: string; agent_name: string | null; action: string | null; outcome: string; summary: string; request_id: string | null }
type Lifecycle = { status: string; checklist: { key: string; label: string; done: boolean }[]; checklist_complete: number }
type ServiceStatus = { status: string; components: Record<string, string>; generated_at: string }
type Entitlements = { plan: string; plan_label: string; status: string; restricted: boolean; limits: Record<string, { soft: number | null; hard: number | null }>; usage: Record<string, number> }
type ComplianceReport = { report_id: string; title: string; created_at: string; integrity_verified?: boolean }

const METERS: [string, string][] = [["agents", "Agents"], ["integrations", "Integrations"], ["controlled_requests_monthly", "Requests this month"]]

async function call<T>(path: string, token: string | null): Promise<T> {
  const response = await fetch(`${API}${path}`, { headers: { "X-Admin-Pin": token ?? "" } })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error((body as { detail?: string }).detail ?? "GreyGuard could not load this panel.")
  return body as T
}

const RISK_ORDER: Record<Agent["risk_level"], number> = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 }

const riskColumns: Column<Agent>[] = [
  {
    key: "agent",
    header: "Agent",
    sortValue: (agent) => agent.agent_name,
    render: (agent) => <Link className="gg-link" to={`/agents/${encodeURIComponent(agent.agent_name)}`}>{agent.agent_name}</Link>,
  },
  { key: "status", header: "Status", sortValue: (agent) => agent.agent_status, render: (agent) => <StatusBadge value={agent.agent_status} /> },
  { key: "level", header: "Risk", sortValue: (agent) => RISK_ORDER[agent.risk_level], render: (agent) => <StatusBadge value={agent.risk_level} /> },
  {
    key: "score",
    header: "Score",
    align: "end",
    sortValue: (agent) => agent.risk_score,
    render: (agent) => (
      <span className="risk-score">
        <span style={{ width: `${Math.min(agent.risk_score, 100)}%` }} />
        {agent.risk_score}
      </span>
    ),
  },
  { key: "blocked", header: "Blocked attempts", align: "end", secondary: true, sortValue: (agent) => agent.blocked_attempts, render: (agent) => agent.blocked_attempts },
]

/** One panel's loading, error and empty handling, so a failing source never blanks the dashboard. */
function PanelState<T>({ query, label, children }: { query: { isLoading: boolean; isError: boolean; error: Error | null; data: T | undefined; refetch: () => unknown }; label: string; children: (data: T) => ReactNode }) {
  if (query.isLoading) return <LoadingState label={label} rows={3} />
  if (query.isError) return <ErrorState message={query.error?.message ?? "Unable to load."} onRetry={() => void query.refetch()} />
  if (query.data === undefined) return null
  return <>{children(query.data)}</>
}

/** One person's Command Center choices, kept on this device under their own account id. */
function useCustomization(adminId: string | undefined): [Customization, (next: Customization) => void] {
  const key = adminId ? storageKeyFor(adminId) : null
  const read = () => {
    try {
      return parseCustomization(key ? localStorage.getItem(key) : null)
    } catch {
      return parseCustomization(null)
    }
  }
  // The account cannot change while this page is open (switching organization keeps it).
  const [customization, setCustomization] = useState<Customization>(read)
  const save = (next: Customization) => {
    setCustomization(next)
    try {
      if (key) localStorage.setItem(key, JSON.stringify(next))
    } catch {
      // A convenience only: blocked storage means the choice lasts for this visit.
    }
  }
  return [customization, save]
}

export function DashboardPage() {
  const { sessionToken, administrator } = useAuth()
  const orgId = administrator?.active_org_id ?? null
  const [customization, saveCustomization] = useCustomization(administrator?.admin_id)
  const layout = resolveLayout(administrator, customization)
  const [customizing, setCustomizing] = useState(false)
  const closeRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useDismissableLayer<HTMLDivElement>({ open: customizing, onClose: () => setCustomizing(false), trapFocus: true, initialFocusRef: closeRef, lockBodyScroll: true })

  // Fetch only what the visible KPIs and panels show: fewer requests, and nothing loaded for
  // a view nobody chose.
  const showsKpi = (...ids: KpiId[]) => ids.some((id) => layout.kpis.includes(id))
  const showsPanel = (...ids: PanelId[]) => ids.some((id) => layout.panels.includes(id))
  const enabled = Boolean(sessionToken)
  const get = <T,>(path: string) => () => call<T>(path, sessionToken)
  // One minute keeps an open Command Center well inside the API's per-client request limits.
  const refetchInterval = 60_000
  const live = (needed: boolean) => ({ enabled: enabled && needed, refetchInterval })

  const agents = useQuery({ queryKey: ["dashboard", "agents"], queryFn: get<Agent[]>("/agents"), ...live(showsKpi("agents", "highRisk", "blocked") || showsPanel("risk")) })
  const pending = useQuery({ queryKey: ["dashboard", "pending"], queryFn: get<{ requests: ToolRequest[]; count: number }>("/tool-requests?approval_status=PENDING&limit=200"), ...live(showsKpi("pending") || showsPanel("approvals")) })
  const alertSummary = useQuery({ queryKey: ["dashboard", "alert-summary"], queryFn: get<AlertSummary>("/alerts/summary"), ...live(showsKpi("incidents")) })
  const openAlerts = useQuery({ queryKey: ["dashboard", "open-alerts"], queryFn: get<{ alerts: Alert[] }>("/alerts?status=OPEN&limit=5"), ...live(showsPanel("incidents")) })
  const notifications = useQuery({ queryKey: ["dashboard", "notifications"], queryFn: get<NotificationSummary>("/notifications/summary"), ...live(showsKpi("signals")) })
  const audit = useQuery({ queryKey: ["dashboard", "audit"], queryFn: get<{ events: AuditEvent[] }>("/audit-events?limit=8"), ...live(showsPanel("evidence")) })
  const lifecycle = useQuery({ queryKey: ["organization-lifecycle", orgId], queryFn: get<Lifecycle>(`/organizations/${orgId}/lifecycle`), enabled: enabled && Boolean(orgId) && showsPanel("readiness") })
  const status = useQuery({ queryKey: ["dashboard", "status"], queryFn: get<ServiceStatus>("/status"), enabled, refetchInterval })
  const plan = useQuery({ queryKey: ["entitlements"], queryFn: get<Entitlements>("/entitlements"), enabled: enabled && showsPanel("plan") })
  const reports = useQuery({ queryKey: ["dashboard", "reports"], queryFn: get<{ reports: ComplianceReport[] }>("/compliance-reports"), enabled: enabled && showsPanel("reports") })

  const refreshAll = () => {
    for (const query of [agents, pending, alertSummary, openAlerts, notifications, audit, lifecycle, status, plan, reports]) {
      if (query.isFetched) void query.refetch()
    }
  }

  const agentList = agents.data ?? []
  const suspended = agentList.filter((agent) => agent.agent_status === "SUSPENDED").length
  const highRisk = agentList.filter((agent) => agent.risk_level === "HIGH" || agent.risk_level === "CRITICAL").length
  const blocked = agentList.reduce((total, agent) => total + agent.blocked_attempts, 0)
  const pendingRequests = [...(pending.data?.requests ?? [])].sort((a, b) => a.timestamp.localeCompare(b.timestamp))
  const activeIncidents = alertSummary.data ? alertSummary.data.open + alertSummary.data.in_progress : undefined
  const lastUpdated = Math.max(agents.dataUpdatedAt, pending.dataUpdatedAt, alertSummary.dataUpdatedAt, audit.dataUpdatedAt, status.dataUpdatedAt)
  const value = (data: unknown, shown: number | undefined) => (data === undefined ? "—" : shown ?? 0)
  const firstName = administrator?.display_name?.split(" ")[0]

  const kpis: Record<KpiId, ReactNode> = {
    pending: <StatCard key="pending" label="Pending approvals" value={value(pending.data, pending.data?.count)} hint="Requests waiting for a human decision" tone={pending.data?.count ? "warning" : "success"} icon={<CheckSquare size={16} />} to="/approvals" />,
    incidents: <StatCard key="incidents" label="Active incidents" value={value(alertSummary.data, activeIncidents)} hint={alertSummary.data ? `${alertSummary.data.active_critical} critical · ${alertSummary.data.open} unassigned` : "Open and in progress"} tone={alertSummary.data?.active_critical ? "danger" : activeIncidents ? "warning" : "success"} icon={<ShieldAlert size={16} />} to="/incidents" />,
    signals: <StatCard key="signals" label="Unread critical signals" value={value(notifications.data, notifications.data ? notifications.data.unread_critical + notifications.data.unread_high : undefined)} hint={notifications.data ? `${notifications.data.unread} unread in total` : "Critical and high"} tone={notifications.data?.unread_critical ? "danger" : notifications.data?.unread_high ? "warning" : "success"} icon={<Bell size={16} />} to="/notifications" />,
    agents: <StatCard key="agents" label="Registered agents" value={value(agents.data, agentList.length)} hint={`${agentList.length - suspended} active · ${suspended} suspended`} tone="info" icon={<Bot size={16} />} to="/agents" />,
    highRisk: <StatCard key="highRisk" label="High-risk agents" value={value(agents.data, highRisk)} hint="High or critical risk level" tone={highRisk ? "danger" : "success"} icon={<Gauge size={16} />} to="/risk" />,
    blocked: <StatCard key="blocked" label="Blocked attempts" value={value(agents.data, blocked)} hint="Refused actions across all agents" tone={blocked ? "warning" : "neutral"} icon={<LockKeyhole size={16} />} to="/audit" />,
  }

  const panels: Record<PanelId, () => ReactNode> = {
    approvals: () => (
      <Panel id="dashboard-queue" eyebrow="Needs a decision" title={PANELS.approvals.title} actions={<Link className="gg-link" to="/approvals">Open approvals</Link>}>
        <PanelState query={pending} label="Loading pending approvals">
          {() => pendingRequests.length === 0
            ? <EmptyState icon={<CheckSquare size={28} />} title="Nothing waiting" description="No tool request is waiting for a human decision." />
            : (
              <ul className="gg-list">
                {pendingRequests.slice(0, 6).map((request) => (
                  <li key={request.request_id}>
                    <StatusBadge value={request.policy_decision} />
                    <div className="gg-list__main">
                      <Link to={`/requests/${encodeURIComponent(request.request_id)}`}>{request.agent_name} · {request.action}</Link>
                      <small>{request.target || "No target"} · risk {request.risk_score}</small>
                    </div>
                    <span className="gg-list__time" title={request.timestamp}>{relativeTime(request.timestamp)}</span>
                  </li>
                ))}
                {pendingRequests.length > 6 && <li><Link className="gg-link" to="/approvals">{pendingRequests.length - 6} more waiting</Link></li>}
              </ul>
            )}
        </PanelState>
      </Panel>
    ),
    incidents: () => (
      <Panel id="dashboard-incidents" eyebrow="Respond" title={PANELS.incidents.title} actions={<Link className="gg-link" to="/incidents">Incident Center</Link>}>
        <PanelState query={openAlerts} label="Loading open incidents">
          {(data) => data.alerts.length === 0
            ? <EmptyState icon={<ShieldAlert size={28} />} title="No open incidents" description="New incidents appear here until someone takes ownership." />
            : (
              <ul className="gg-list">
                {data.alerts.map((alert) => (
                  <li key={alert.alert_id}>
                    <StatusBadge value={alert.severity} />
                    <div className="gg-list__main">
                      <Link to="/incidents">{alert.title}</Link>
                      <small>{alert.agent_name ?? "Install-level"}</small>
                    </div>
                    <span className="gg-list__time" title={alert.created_at}>{relativeTime(alert.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
        </PanelState>
      </Panel>
    ),
    risk: () => (
      <Panel id="dashboard-risk" eyebrow="Watch" title={PANELS.risk.title} actions={<Link className="gg-link" to="/risk">Risk Center</Link>}>
        <PanelState query={agents} label="Loading agents">
          {(data) => (
            <DataTable
              label="Agents by risk"
              columns={riskColumns}
              rows={data}
              rowKey={(agent) => agent.agent_name}
              pageSize={6}
              initialSort={{ key: "score", direction: "desc" }}
              rowTone={(agent) => (agent.agent_status === "SUSPENDED" || agent.risk_level === "CRITICAL" ? "danger" : agent.risk_level === "HIGH" ? "warning" : undefined)}
              empty={<EmptyState icon={<Bot size={28} />} title="No agents registered" description="Register an agent to start enforcing identity, scope and policy." action={<Link className="gg-link" to="/agents">Go to Agents</Link>} />}
            />
          )}
        </PanelState>
      </Panel>
    ),
    readiness: () => (
      <Panel id="dashboard-readiness" eyebrow="Organization" title={PANELS.readiness.title} actions={<Link className="gg-link" to="/getting-started">Getting Started</Link>}>
        {!orgId
          ? <EmptyState icon={<ClipboardList size={28} />} title="No active organization" description="Choose an organization from your account menu to see its readiness." />
          : (
            <PanelState query={lifecycle} label="Loading readiness">
              {(data) => (
                <div className="dashboard-readiness">
                  <p><strong>{data.checklist_complete} of {data.checklist.length}</strong> readiness steps complete · <StatusBadge value={data.status} /></p>
                  <progress max={data.checklist.length || 1} value={data.checklist_complete} aria-label="Readiness progress" />
                  <ul className="gg-list">
                    {data.checklist.filter((item) => !item.done).slice(0, 4).map((item) => (
                      <li key={item.key}><span className="dashboard-readiness__todo" aria-hidden="true" /><div className="gg-list__main"><span>{item.label}</span></div></li>
                    ))}
                  </ul>
                </div>
              )}
            </PanelState>
          )}
        <div className="dashboard-services">
          <p className="gg-panel__eyebrow">Service components</p>
          <PanelState query={status} label="Loading service status">
            {(data) => (
              <ul className="gg-list">
                {Object.entries(data.components).map(([name, state]) => (
                  <li key={name}><div className="gg-list__main"><span>{name.replaceAll("_", " ")}</span></div><StatusBadge value={state} /></li>
                ))}
              </ul>
            )}
          </PanelState>
        </div>
      </Panel>
    ),
    evidence: () => (
      <Panel id="dashboard-evidence" eyebrow="Evidence" title={PANELS.evidence.title} actions={<Link className="gg-link" to="/audit">Open Audit Trail</Link>}>
        <PanelState query={audit} label="Loading recent evidence">
          {(data) => data.events.length === 0
            ? <EmptyState icon={<FileSearch size={28} />} title="No evidence yet" description="Decisions, approvals and administrator actions are recorded here as they happen." />
            : (
              <ul className="gg-list">
                {data.events.map((event) => (
                  <li key={event.event_id}>
                    <Activity size={16} aria-hidden="true" />
                    <div className="gg-list__main">
                      {event.request_id
                        ? <Link to={`/requests/${encodeURIComponent(event.request_id)}`}>{event.summary}</Link>
                        : <strong>{event.summary}</strong>}
                      <small>{event.event_type.replaceAll("_", " ")}{event.agent_name ? ` · ${event.agent_name}` : ""}</small>
                    </div>
                    <StatusBadge value={event.outcome} />
                    <span className="gg-list__time" title={event.timestamp}>{relativeTime(event.timestamp)}</span>
                  </li>
                ))}
              </ul>
            )}
        </PanelState>
      </Panel>
    ),
    plan: () => (
      <Panel id="dashboard-plan" eyebrow="Organization" title={PANELS.plan.title} actions={<Link className="gg-link" to="/settings">Plan details</Link>}>
        <PanelState query={plan} label="Loading plan">
          {(data) => (
            <div className="dashboard-plan">
              <p><strong>{data.plan_label}</strong> · <StatusBadge value={data.restricted ? "RESTRICTED" : data.status} /></p>
              <ul className="gg-list">
                {METERS.map(([meter, label]) => {
                  const limit = data.limits[meter]?.hard ?? data.limits[meter]?.soft ?? null
                  const used = data.usage[meter] ?? 0
                  return (
                    <li key={meter}>
                      <div className="gg-list__main"><span>{label}</span></div>
                      <span className="gg-list__time">{limit === null ? `${used} · no limit` : `${used} of ${limit}`}</span>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
        </PanelState>
      </Panel>
    ),
    reports: () => (
      <Panel id="dashboard-reports" eyebrow="Evidence" title={PANELS.reports.title} actions={<Link className="gg-link" to="/compliance">All reports</Link>}>
        <PanelState query={reports} label="Loading reports">
          {(data) => data.reports.length === 0
            ? <EmptyState icon={<FileCheck2 size={28} />} title="No reports yet" description="Sealed evidence snapshots for reviewers appear here once one is generated." />
            : (
              <ul className="gg-list">
                {[...data.reports].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 4).map((report) => (
                  <li key={report.report_id}>
                    <FileCheck2 size={16} aria-hidden="true" />
                    <div className="gg-list__main"><span>{report.title}</span></div>
                    {report.integrity_verified !== undefined && <StatusBadge value={report.integrity_verified ? "VERIFIED" : "UNVERIFIED"} />}
                    <span className="gg-list__time" title={report.created_at}>{relativeTime(report.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
        </PanelState>
      </Panel>
    ),
  }

  const choosePreset = (id: string) => saveCustomization({ ...customization, preset: layout.presets.find((preset) => preset.id === id)?.id })

  return (
    <section className="gg-page dashboard-page">
      <PageHeader
        eyebrow={administrator?.active_org_name ? `Command Center · ${administrator.active_org_name}` : "Command Center"}
        title={<>{greetingFor(new Date().getHours())}{firstName ? `, ${firstName}` : ""}.</>}
        description={layout.preset.purpose}
        meta={
          <>
            <span>{status.data ? <>Service <StatusBadge value={status.data.status} /></> : status.isError ? "Service status unavailable" : "Checking service status…"}</span>
            <span>{lastUpdated ? `Updated ${relativeTime(new Date(lastUpdated).toISOString())} · refreshes every minute` : "Loading live data…"}</span>
          </>
        }
        actions={
          <>
            {layout.presets.length > 1 && (
              <label className="dashboard-view">
                <span>View</span>
                <select value={layout.preset.id} onChange={(event) => choosePreset(event.target.value)} aria-label="Command Center view">
                  {layout.presets.map((preset) => <option key={preset.id} value={preset.id}>{preset.label}</option>)}
                </select>
              </label>
            )}
            <button type="button" className="gg-button" onClick={() => setCustomizing(true)}><LayoutGrid size={16} aria-hidden="true" />Customize</button>
            <button type="button" className="gg-button" onClick={refreshAll}><RefreshCw size={16} aria-hidden="true" />Refresh</button>
          </>
        }
      />

      <StatGrid label="Security posture">
        {layout.kpis.map((id) => kpis[id])}
      </StatGrid>

      {layout.panels.length === 0
        ? <EmptyState icon={<LayoutGrid size={28} />} title="Every panel is hidden" description="Choose Customize to show the panels you want on this view." />
        : (
          <div className="dashboard-panels">
            {layout.panels.map((id) => (
              <div key={id} className={PANELS[id].wide ? "dashboard-panels__wide" : undefined}>{panels[id]()}</div>
            ))}
          </div>
        )}

      {customizing && (
        <div ref={dialogRef} className="gg-dialog" role="dialog" aria-modal="true" aria-labelledby="dashboard-customize-title">
          <div className="gg-dialog__panel dashboard-customize">
            <header className="gg-dialog__header">
              <div>
                <p className="gg-panel__eyebrow">{layout.preset.label} view</p>
                <h2 id="dashboard-customize-title">Customize the Command Center</h2>
              </div>
              <button ref={closeRef} type="button" className="gg-button" onClick={() => setCustomizing(false)} aria-label="Close"><X size={16} aria-hidden="true" />Done</button>
            </header>
            <p className="gg-muted">Show the panels you use and hide the rest. Your choice is saved for your account on this device.</p>
            <fieldset className="dashboard-customize__panels">
              <legend>Panels</legend>
              {PANEL_ORDER.map((id) => (
                <label className="gg-check" key={id}>
                  <input
                    type="checkbox"
                    checked={layout.panels.includes(id)}
                    onChange={(event) => saveCustomization(togglePanel(customization, layout.preset, id, event.target.checked))}
                  />
                  <span><strong>{PANELS[id].title}</strong><small>{PANELS[id].description}</small></span>
                </label>
              ))}
            </fieldset>
            <div className="gg-form__actions">
              <button type="button" className="gg-button" onClick={() => saveCustomization({ preset: customization.preset, pinned: [], hidden: [] })}>Reset to this view's panels</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
