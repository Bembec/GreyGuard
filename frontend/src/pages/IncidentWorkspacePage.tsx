import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowLeft, Bot, CircleHelp, Clock3, Copy, Download, FileSearch, Link2, RefreshCw, ShieldAlert, ShieldCheck, UserRound } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import { ConfirmDialog } from "../components/ConfirmDialog"
import { ExplanationCard, type Explanation } from "../components/explanation/ExplanationCard"
import { PageHeader } from "../components/page/PageHeader"
import { useShowMore } from "../components/page/ShowMore"
import { useToast } from "../context/ToastContext"
import { safePackageFilename } from "../lib/incidentPackage"
import type { IncidentSla } from "../lib/incidentSla"
import "../styles/incident-workspace.css"

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"

type SectionError = { error: string }
type Action = { id: string; label: string; to_status?: string; requires_note?: boolean; target?: string | null; confirm_text?: string | null;
  available: boolean; unavailable_reason: string | null }

const CONTAINMENT = ["revoke_credential", "disable_agent", "disable_tool", "terminate_isolation"]

type Entry = { type: string; timestamp: string; actor: string; text: string; path: string | null; trigger?: boolean; action_record?: boolean }

export type Workspace = {
  incident: { alert_id: string; title: string; summary: string; severity: string; status: string; created_at: string; updated_at: string;
    event_type: string; agent_name: string | null; request_id: string | null; resolution_note: string | null; install_level: boolean }
  owner: { name: string | null; email: string | null; kind: "member" | "free_text" | null; candidates?: Array<{ email: string; display_name: string }> }
  sla: IncidentSla | SectionError
  explanation: Explanation | null | SectionError
  timeline: { entries: Entry[]; truncated: boolean; window: { since: string } } | SectionError
  agent: null | SectionError | { agent_name: string; known: boolean; status?: string; risk_score?: number; credential_status?: string | null;
    scopes?: string[]; path?: string; graph_path?: string; note?: string }
  related: Array<{ alert_id: string; title: string; severity: string; status: string; created_at: string; path: string }> | SectionError
  integrity: SectionError | { decision_record_intact: boolean | null; policy_unchanged: boolean | null; basis: string | null;
    audit_chain: null | { last_verified_at: string; valid: boolean } }
  actions: { primary: Action | null; others: Action[] }
  why_you_see_this: string
}

class HttpError extends Error {
  readonly status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function call<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "", ...options.headers },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new HttpError((body as { detail?: string }).detail ?? `Request failed with status ${response.status}.`, response.status)
  return body as T
}

export function isSectionError(value: unknown): value is SectionError {
  return Boolean(value) && typeof value === "object" && "error" in (value as object)
}

function formatDate(value?: string | null) {
  if (!value) return "Not recorded"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date)
}

const TIMELINE_FILTERS = [
  { id: "all", label: "Everything" },
  { id: "record", label: "Action record" },
  { id: "evidence", label: "Evidence" },
] as const

const TYPE_LABELS: Record<string, string> = {
  INCIDENT_OPENED: "Opened", REQUEST: "Request", APPROVAL: "Approval", EXECUTION: "Execution", DECISION: "Decision",
  AUTHENTICATION: "Authentication", STATUS_CHANGED: "Status", ASSIGNED: "Owner", NOTE_ADDED: "Note", CONTAINMENT: "Containment", EXPORTED: "Export", SLA_BREACH: "SLA",
}

const OPEN_STATES = ["within", "due_soon", "breached"]

function SlaMeta({ sla }: { sla: IncidentSla | SectionError }) {
  if ("error" in sla) return <span><Clock3 size={14} aria-hidden="true" /> SLA could not be loaded</span>
  const due = sla.deadline && sla.state && OPEN_STATES.includes(sla.state) ? ` · ${sla.state === "breached" ? "was due" : "due"} ${formatDate(sla.deadline)}` : ""
  return (
    <span className={sla.state ? `incident-workspace__sla is-${sla.state}` : undefined} title={sla.basis ?? undefined}>
      <Clock3 size={14} aria-hidden="true" /> {sla.text}{due}
      {!sla.configured && sla.text === "No SLA set" && <> · <Link to="/incidents#response-targets">Response targets</Link></>}
    </span>
  )
}

function SectionFailure({ value, onRetry }: { value: SectionError; onRetry: () => void }) {
  return <ErrorState message={value.error} onRetry={onRetry} />
}

function Unavailable({ reason }: { reason: string | null }) {
  if (!reason) return null
  return <p className="incident-workspace__unavailable"><CircleHelp size={14} aria-hidden="true" /><span><strong>Why is this unavailable?</strong> {reason}</span></p>
}

export default function IncidentWorkspacePage() {
  const { alertId = "" } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { pushToast } = useToast()
  const [filter, setFilter] = useState<(typeof TIMELINE_FILTERS)[number]["id"]>("all")
  const [pending, setPending] = useState<Action | null>(null)
  const [note, setNote] = useState("")
  const [noteOpen, setNoteOpen] = useState(false)
  const [ownerChoice, setOwnerChoice] = useState<string | null>(null)
  const [containing, setContaining] = useState<Action | null>(null)
  const [typed, setTyped] = useState("")
  const [reason, setReason] = useState("")

  const workspace = useQuery({
    queryKey: ["incident-workspace", alertId],
    queryFn: () => call<Workspace>(`/incidents/${encodeURIComponent(alertId)}/workspace`),
    enabled: Boolean(alertId),
    retry: (count, error) => !(error instanceof HttpError && error.status === 404) && count < 2,
  })
  const data = workspace.data
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["incident-workspace", alertId] })

  // The owner as the API knows it: a member's email, or a legacy free-text owner kept as it is.
  const currentOwner = data?.owner.email ?? (data?.owner.kind === "free_text" ? data.owner.name : null)
  const change = useMutation({
    mutationFn: (input: { status: string; note?: string; owner?: string | null }) => call(`/alerts/${encodeURIComponent(alertId)}`, {
      method: "PUT",
      body: JSON.stringify({ status: input.status, assigned_to: input.owner === undefined ? currentOwner : input.owner, note: input.note || null }),
    }),
    onSuccess: () => { setPending(null); setNote(""); setOwnerChoice(null); refresh(); pushToast({ tone: "success", title: "Incident updated", message: "The change is in the action record." }) },
    onError: (error: Error) => pushToast({ tone: "error", title: "Not updated", message: error.message }),
  })
  const addNote = useMutation({
    mutationFn: (text: string) => call(`/alerts/${encodeURIComponent(alertId)}/notes`, { method: "POST", body: JSON.stringify({ note: text }) }),
    onSuccess: () => { setNote(""); setNoteOpen(false); refresh(); pushToast({ tone: "success", title: "Note added", message: "It is in the action record." }) },
    onError: (error: Error) => pushToast({ tone: "error", title: "Note not added", message: error.message }),
  })
  const contain = useMutation({
    mutationFn: (input: { action: string; confirm: string; reason: string }) =>
      call<{ summary: string }>(`/incidents/${encodeURIComponent(alertId)}/actions`, { method: "POST", body: JSON.stringify(input) }),
    onSuccess: (result) => { setContaining(null); setTyped(""); setReason(""); refresh(); pushToast({ tone: "success", title: "Containment applied", message: `GreyGuard ${result.summary}. It is in the action record.` }) },
    onError: (error: Error) => pushToast({ tone: "error", title: "Not applied", message: error.message }),
  })
  const exportPackage = useMutation({
    mutationFn: () => call<{ manifest: { package: string } }>(`/incidents/${encodeURIComponent(alertId)}/package`, { method: "POST" }),
    onSuccess: (pkg) => {
      const url = URL.createObjectURL(new Blob([JSON.stringify(pkg, null, 2)], { type: "application/json" }))
      const link = document.createElement("a")
      link.href = url
      link.download = safePackageFilename(alertId)
      link.click()
      URL.revokeObjectURL(url)
      refresh()
      pushToast({ tone: "success", title: "Package exported", message: `SHA-256 ${pkg.manifest.package.slice(0, 12)}…; the export is in the action record.` })
    },
    onError: (error: Error) => pushToast({ tone: "error", title: "Not exported", message: error.message }),
  })
  const verify = useMutation({
    mutationFn: () => call<{ valid: boolean; records_checked: number }>("/audit-integrity/verify", { method: "POST" }),
    onSuccess: (result) => { refresh(); pushToast({ tone: result.valid ? "success" : "error", title: result.valid ? "Audit chain verified" : "Audit chain invalid", message: `${result.records_checked} records checked.` }) },
    onError: (error: Error) => pushToast({ tone: "error", title: "Not verified", message: error.message }),
  })

  const timeline = data && !isSectionError(data.timeline) ? data.timeline : null
  const entries = (timeline?.entries ?? []).filter((entry) => filter === "all" || (filter === "record" ? entry.action_record : !entry.action_record))
  const more = useShowMore(entries, filter)

  function start(action: Action) {
    if (!action.available) return
    if (action.requires_note) { setPending(action); return }
    change.mutate({ status: action.to_status! })
  }

  if (workspace.isLoading) return <main className="incident-workspace gg-page-pad"><LoadingState label="Loading the incident" rows={6} /></main>
  if (workspace.isError) {
    const missing = workspace.error instanceof HttpError && workspace.error.status === 404
    return (
      <main className="incident-workspace gg-page-pad">
        {missing
          ? <EmptyState title="Incident not found" description="It does not exist, or it is not in your organization." action={<Link className="gg-button" to="/incidents">Back to Incident Center</Link>} />
          : <ErrorState message={workspace.error.message} onRetry={() => void workspace.refetch()} />}
      </main>
    )
  }
  if (!data) return null
  const { incident, actions } = data
  const primary = actions.primary
  const noteAction = actions.others.find((action) => action.id === "note")

  return (
    <main className="incident-workspace gg-page-pad">
      <PageHeader
        eyebrowSuffix="Investigation"
        title={incident.title}
        description={incident.summary}
        actions={<>
          <button type="button" className="gg-button" onClick={() => navigate("/incidents")}><ArrowLeft size={16} aria-hidden="true" />All incidents</button>
          <button type="button" className="gg-button" onClick={() => { void navigator.clipboard?.writeText(window.location.href); pushToast({ tone: "info", title: "Link copied", message: "Anyone opening it still needs access to this organization." }) }}><Copy size={16} aria-hidden="true" />Copy link</button>
          <button type="button" className="gg-button" onClick={() => void workspace.refetch()}><RefreshCw size={16} aria-hidden="true" />Refresh</button>
          <button type="button" className="gg-button" disabled={exportPackage.isPending} onClick={() => exportPackage.mutate()}><Download size={16} aria-hidden="true" />Export package</button>
          {primary && <button type="button" className="gg-button gg-button--primary" disabled={!primary.available || change.isPending} onClick={() => start(primary)}>{primary.label}</button>}
        </>}
        meta={
          <div className="incident-workspace__meta" data-testid="incident-meta">
            <span className={`incident-workspace__badge severity--${incident.severity.toLowerCase()}`}>{incident.severity}</span>
            <span className={`incident-workspace__badge status--${incident.status.toLowerCase()}`}>{incident.status}</span>
            <span><UserRound size={14} aria-hidden="true" /> {data.owner.name ? <>{data.owner.name}{data.owner.kind === "free_text" && <small> (legacy owner)</small>}</> : "No owner"}</span>
            <SlaMeta sla={data.sla} />
            <span>Opened {formatDate(incident.created_at)}</span>
            {incident.install_level && <span className="incident-workspace__badge">Install-level</span>}
          </div>
        }
      />
      {primary && !primary.available && <Unavailable reason={primary.unavailable_reason} />}

      {pending && (
        <form className="incident-workspace__note-form" onSubmit={(event) => { event.preventDefault(); if (note.trim()) change.mutate({ status: pending.to_status!, note }) }}>
          <label htmlFor="status-note">{pending.label}: a note is required</label>
          <textarea id="status-note" value={note} maxLength={2000} onChange={(event) => setNote(event.target.value)} placeholder="What was done, or why this was not a real threat" />
          <div><button type="submit" className="gg-button gg-button--primary" disabled={!note.trim() || change.isPending}>{pending.label}</button>
            <button type="button" className="gg-button" onClick={() => { setPending(null); setNote("") }}>Cancel</button></div>
        </form>
      )}

      <div className="incident-workspace__grid">
        <section className="incident-workspace__timeline" aria-labelledby="timeline-heading">
          <header>
            <h2 id="timeline-heading">Timeline</h2>
            <div className="incident-workspace__filters" role="group" aria-label="Timeline filter">
              {TIMELINE_FILTERS.map((item) => <button key={item.id} type="button" aria-pressed={filter === item.id} onClick={() => setFilter(item.id)}>{item.label}</button>)}
            </div>
          </header>
          {isSectionError(data.timeline) ? <SectionFailure value={data.timeline} onRetry={refresh} /> : (
            <>
              {timeline && <p className="incident-workspace__hint">From {formatDate(timeline.window.since)}, newest first.{timeline.truncated && " Not everything fits: the full evidence is in the Audit Trail."}</p>}
              {entries.length === 0
                ? <EmptyState title={filter === "record" ? "No actions recorded yet" : "Nothing in this window"} description={filter === "record" ? "Status changes, notes and containment actions appear here." : "No evidence was recorded in the window."} />
                : <ol className="incident-workspace__entries">
                  {more.visible.map((entry, index) => (
                    <li key={`${entry.type}-${entry.timestamp}-${index}`} className={entry.trigger ? "is-trigger" : entry.action_record ? "is-record" : undefined}>
                      <span className="incident-workspace__type">{TYPE_LABELS[entry.type] ?? entry.type}</span>
                      <div>
                        <p>{entry.path ? <Link to={entry.path}>{entry.text}</Link> : entry.text}</p>
                        <small title={entry.timestamp}>{entry.actor} · {formatDate(entry.timestamp)}</small>
                      </div>
                    </li>
                  ))}
                </ol>}
              {more.control}
            </>
          )}
          <div className="incident-workspace__add-note">
            {noteOpen ? (
              <form onSubmit={(event) => { event.preventDefault(); if (note.trim()) addNote.mutate(note.trim()) }}>
                <label htmlFor="incident-note">Note</label>
                <textarea id="incident-note" value={note} maxLength={2000} onChange={(event) => setNote(event.target.value)} />
                <div><button type="submit" className="gg-button gg-button--primary" disabled={!note.trim() || addNote.isPending}>Add note</button>
                  <button type="button" className="gg-button" onClick={() => setNoteOpen(false)}>Cancel</button></div>
              </form>
            ) : (
              <>
                <button type="button" className="gg-button" disabled={!noteAction?.available} onClick={() => setNoteOpen(true)}>Add a note</button>
                {noteAction && !noteAction.available && <Unavailable reason={noteAction.unavailable_reason} />}
              </>
            )}
          </div>
        </section>

        <aside className="incident-workspace__rail">
          <section aria-labelledby="what-happened">
            <h2 id="what-happened">What happened</h2>
            {isSectionError(data.explanation) ? <SectionFailure value={data.explanation} onRetry={refresh} />
              : data.explanation ? <ExplanationCard explanation={data.explanation} />
              : <p className="incident-workspace__hint">No linked request: this incident {incident.request_id ? "has no readable request" : "was raised from evidence that names no request (for example a failed sign-in, or a decision made before requests were linked to incidents)"}.</p>}
          </section>

          <section aria-labelledby="agent-heading">
            <h2 id="agent-heading"><Bot size={15} aria-hidden="true" /> Agent</h2>
            {isSectionError(data.agent) ? <SectionFailure value={data.agent} onRetry={refresh} /> : data.agent ? (
              data.agent.known ? (
                <dl className="incident-workspace__facts">
                  <div><dt>Agent</dt><dd><Link to={data.agent.path!}>{data.agent.agent_name}</Link></dd></div>
                  <div><dt>Status</dt><dd>{data.agent.status} · risk {data.agent.risk_score}</dd></div>
                  <div><dt>Credential</dt><dd>{data.agent.credential_status}</dd></div>
                  <div><dt>Scopes</dt><dd>{data.agent.scopes?.join(", ") || "None"}</dd></div>
                  <div><dt>Relationships</dt><dd><Link to={data.agent.graph_path!}><Link2 size={13} aria-hidden="true" /> Open the Control Graph</Link></dd></div>
                </dl>
              ) : <p className="incident-workspace__hint">{data.agent.agent_name}: {data.agent.note ?? "not a registered agent in this organization."}</p>
            ) : <p className="incident-workspace__hint">No agent is named in this incident.</p>}
          </section>

          <section aria-labelledby="related-heading">
            <h2 id="related-heading">Related incidents</h2>
            {isSectionError(data.related) ? <SectionFailure value={data.related} onRetry={refresh} /> : data.related.length === 0
              ? <p className="incident-workspace__hint">No other incidents for this agent.</p>
              : <ul className="incident-workspace__related">{data.related.map((item) => (
                <li key={item.alert_id}><Link to={item.path}>{item.title}</Link><small>{item.severity} · {item.status} · {formatDate(item.created_at)}</small></li>
              ))}</ul>}
          </section>

          <section aria-labelledby="integrity-heading">
            <h2 id="integrity-heading"><ShieldCheck size={15} aria-hidden="true" /> Evidence integrity</h2>
            {isSectionError(data.integrity) ? <SectionFailure value={data.integrity} onRetry={refresh} /> : (
              <ul className="incident-workspace__integrity">
                <li>{data.integrity.decision_record_intact === null ? "No decision record to verify for this incident."
                  : data.integrity.decision_record_intact ? "The decision record matches its fingerprint." : "The decision record does not match its fingerprint."}</li>
                <li>{data.integrity.audit_chain ? <>Audit chain last verified {formatDate(data.integrity.audit_chain.last_verified_at)}: {data.integrity.audit_chain.valid ? "valid" : "invalid"}.</> : "The audit chain has not been verified yet."}</li>
              </ul>
            )}
            {actions.others.filter((action) => action.id === "verify_chain").map((action) => (
              <div key={action.id}>
                <button type="button" className="gg-button" disabled={!action.available || verify.isPending} onClick={() => verify.mutate()}><FileSearch size={15} aria-hidden="true" />{action.label}</button>
                {!action.available && <Unavailable reason={action.unavailable_reason} />}
              </div>
            ))}
          </section>

          <section aria-labelledby="owner-heading">
            <h2 id="owner-heading"><UserRound size={15} aria-hidden="true" /> Owner</h2>
            <p className="incident-workspace__hint">
              {data.owner.kind === "member" ? <>Owned by <strong>{data.owner.name}</strong> ({data.owner.email}).</>
                : data.owner.kind === "free_text" ? <>Legacy owner: “{data.owner.name}”. Assign a member to replace it.</>
                : "Nobody owns this incident yet."}
            </p>
            {data.owner.candidates ? (
              <form className="incident-workspace__owner" onSubmit={(event) => { event.preventDefault(); if (ownerChoice !== null) change.mutate({ status: incident.status, owner: ownerChoice || null }) }}>
                <label htmlFor="owner-select" className="gg-sr-only">Choose an owner</label>
                <select id="owner-select" value={ownerChoice ?? data.owner.email ?? ""} onChange={(event) => setOwnerChoice(event.target.value)}>
                  <option value="">Nobody</option>
                  {data.owner.candidates.map((member) => <option key={member.email} value={member.email}>{member.display_name} ({member.email})</option>)}
                </select>
                <button type="submit" className="gg-button" disabled={ownerChoice === null || ownerChoice === (data.owner.email ?? "") || change.isPending}>Assign</button>
              </form>
            ) : <Unavailable reason={noteAction?.unavailable_reason ?? null} />}
          </section>

          <section aria-labelledby="containment-heading">
            <h2 id="containment-heading"><ShieldAlert size={15} aria-hidden="true" /> Containment</h2>
            <p className="incident-workspace__hint">Each action uses the same rights as its own page, asks you to type what it acts on, and is recorded with your reason.</p>
            <ul className="incident-workspace__actions">
              {actions.others.filter((action) => CONTAINMENT.includes(action.id)).map((action) => (
                <li key={action.id}>
                  <button type="button" className="gg-button" disabled={!action.available} onClick={() => { setContaining(action); setTyped(""); setReason("") }}>{action.label}</button>
                  {!action.available && <Unavailable reason={action.unavailable_reason} />}
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="actions-heading">
            <h2 id="actions-heading">Actions</h2>
            <ul className="incident-workspace__actions">
              {actions.others.filter((action) => action.id.startsWith("status:")).map((action) => (
                <li key={action.id}>
                  <button type="button" className="gg-button" disabled={!action.available} onClick={() => start(action)}>{action.label}</button>
                  {!action.available && <Unavailable reason={action.unavailable_reason} />}
                </li>
              ))}
            </ul>
          </section>
          <p className="incident-workspace__why"><CircleHelp size={13} aria-hidden="true" /><span><strong>Why am I seeing this?</strong> {data.why_you_see_this}</span></p>
        </aside>
      </div>

      <ConfirmDialog
        open={Boolean(containing)}
        title={containing?.label ?? ""}
        description={containing ? `This acts on ${containing.target === "TERMINATE" ? "every running isolated execution in this organization" : containing.target}. It takes effect immediately and is recorded in this incident.` : ""}
        confirmLabel={containing?.label ?? "Confirm"}
        busy={contain.isPending}
        confirmDisabled={!containing || typed.trim() !== containing.confirm_text || reason.trim().length < 5}
        onCancel={() => setContaining(null)}
        onConfirm={() => containing && contain.mutate({ action: containing.id, confirm: typed.trim(), reason: reason.trim() })}
      >
        {containing && (
          <div className="incident-workspace__confirm">
            <label htmlFor="containment-confirm">Type <code>{containing.confirm_text}</code> to confirm</label>
            <input id="containment-confirm" value={typed} autoComplete="off" onChange={(event) => setTyped(event.target.value)} />
            <label htmlFor="containment-reason">Reason (recorded)</label>
            <textarea id="containment-reason" value={reason} maxLength={1000} aria-describedby="containment-reason-hint" onChange={(event) => setReason(event.target.value)} />
            <small id="containment-reason-hint">At least 5 characters. It goes into the incident's action record.</small>
          </div>
        )}
      </ConfirmDialog>

      {primary && (
        <div className="incident-workspace__mobile-bar">
          <button type="button" className="gg-button gg-button--primary" disabled={!primary.available || change.isPending} onClick={() => start(primary)}>{primary.label}</button>
        </div>
      )}
    </main>
  )
}
