import { Activity, ArrowLeft, Bot, Clock3, FileSearch, Fingerprint, KeyRound, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState"
import "../styles/agent-detail.css"

type Investigation = {
  agent: { agent_name: string; agent_status: string; risk_score: number; risk_level: string; blocked_attempts: number; identity: null | { scopes: string[]; credential_status: string; created_at?: string | null; rotated_at?: string | null; revoked_at?: string | null } }
  risk_history: Array<{ event_id: string; timestamp: string; action: string; outcome: string; severity: string; risk_added: number; risk_score: number; risk_level: string }>
  authentication_history: Array<{ event_id: string; timestamp: string; action: string | null; outcome: string; severity: string; summary: string }>
  requests: Array<{ request_id: string; timestamp: string; action: string; target: string; policy_decision: string; approval_status: string; execution_status: string; risk_added: number; risk_score: number; path: string }>
  summary: { risk_events: number; authentication_events: number; requests: number; denied_requests: number }
}

type CredentialHistory = {
  events: Array<{ id: number; agent_name: string; timestamp: string; event_type: "ISSUED" | "ROTATED" | "REVOKED"; actor: string }>
  total: number
}

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"
const CREDENTIAL_HISTORY_PAGE_SIZE = 10

export function formatAgentEvidenceDate(value?: string | null) {
  if (!value) return "Not recorded"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date)
}

async function loadInvestigation(agentName: string): Promise<Investigation> {
  const token = sessionStorage.getItem("greyguard_admin_pin")
  const response = await fetch(`${API}/agent-investigations/${encodeURIComponent(agentName)}`, { headers: { "X-Admin-Pin": token ?? "" } })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail ?? "Agent investigation could not be loaded.")
  return body as Investigation
}

async function loadCredentialHistory(agentName: string, offset: number): Promise<CredentialHistory> {
  const token = sessionStorage.getItem("greyguard_admin_pin")
  const response = await fetch(`${API}/agents/${encodeURIComponent(agentName)}/credential-history?limit=${CREDENTIAL_HISTORY_PAGE_SIZE}&offset=${offset}`, { headers: { "X-Admin-Pin": token ?? "" } })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail ?? "Credential history could not be loaded.")
  return body as CredentialHistory
}

export default function AgentDetailPage() {
  const { agentName = "" } = useParams()
  const navigate = useNavigate()
  const investigation = useQuery({ queryKey: ["agent-investigation", agentName], queryFn: () => loadInvestigation(agentName), enabled: Boolean(agentName) })
  const [credentialHistoryOffset, setCredentialHistoryOffset] = useState(0)
  const credentialHistory = useQuery({
    queryKey: ["agent-credential-history", agentName, credentialHistoryOffset],
    queryFn: () => loadCredentialHistory(agentName, credentialHistoryOffset),
    enabled: Boolean(agentName),
  })

  const agent = investigation.data?.agent

  return <main className="agent-investigation">
    <header className="agent-investigation__hero">
      <button type="button" onClick={() => navigate("/agents")}><ArrowLeft size={17}/> All agents</button>
      <div><span><Bot size={20}/></span><div><p>Agent investigation</p><h1>{agent?.agent_name ?? agentName}</h1><small>Correlated identity, risk, authentication and controlled-execution evidence.</small></div></div>
      {investigation.data && <button type="button" onClick={() => void investigation.refetch()}><RefreshCw size={17}/> Refresh evidence</button>}
    </header>

    {investigation.isLoading && <LoadingState label="Loading agent investigation" rows={6}/>}
    {investigation.isError && <ErrorState message={investigation.error.message} onRetry={() => void investigation.refetch()}/>}

    {investigation.data && agent && (() => {
      const { summary, risk_history: risk, authentication_history: authentication, requests } = investigation.data
      return <>
        <section className="agent-investigation__posture">
          <article><ShieldCheck/><span>Status</span><strong>{agent.agent_status}</strong></article>
          <article><ShieldAlert/><span>Current risk</span><strong>{agent.risk_score} · {agent.risk_level}</strong></article>
          <article><Activity/><span>Blocked attempts</span><strong>{agent.blocked_attempts}</strong></article>
          <article><KeyRound/><span>Credential</span><strong>{agent.identity?.credential_status ?? "MISSING"}</strong></article>
        </section>

        <section className="agent-investigation__grid">
          <article className="investigation-card identity-card"><header><Fingerprint/><div><h2>Identity and scope boundaries</h2><p>Registered machine identity and permitted actions.</p></div></header>
            {agent.identity ? <><div className="scope-cloud">{agent.identity.scopes.map((scope) => <span key={scope}>{scope}</span>)}</div><dl><div><dt>Created</dt><dd>{formatAgentEvidenceDate(agent.identity.created_at)}</dd></div><div><dt>Last rotated</dt><dd>{formatAgentEvidenceDate(agent.identity.rotated_at)}</dd></div><div><dt>Revoked</dt><dd>{formatAgentEvidenceDate(agent.identity.revoked_at)}</dd></div></dl></> : <EmptyState title="Legacy identity" description="This agent has no registered scoped credential."/>}
          </article>
          <article className="investigation-card summary-card"><header><FileSearch/><div><h2>Evidence coverage</h2><p>Records correlated to this identity.</p></div></header><div>{[["Risk decisions",summary.risk_events],["Authentication",summary.authentication_events],["Tool requests",summary.requests],["Denied or refused",summary.denied_requests]].map(([label,value]) => <span key={label as string}><strong>{value}</strong><small>{label}</small></span>)}</div></article>
        </section>

        <section className="investigation-card"><header><Activity/><div><h2>Risk history</h2><p>Policy decisions and accumulated-risk movement.</p></div></header>{risk.length === 0 ? <EmptyState title="No risk evidence" description="No policy decisions are recorded for this agent."/> : <div className="evidence-table"><div className="evidence-table__head"><span>Time</span><span>Action</span><span>Decision</span><span>Risk movement</span></div>{risk.map((event) => <div key={event.event_id}><span>{formatAgentEvidenceDate(event.timestamp)}</span><strong>{event.action}</strong><span className={`evidence-outcome evidence-outcome--${event.outcome.toLowerCase()}`}>{event.outcome}</span><span>+{event.risk_added} → {event.risk_score} {event.risk_level}</span></div>)}</div>}</section>

        <section className="agent-investigation__grid">
          <article className="investigation-card"><header><Fingerprint/><div><h2>Authentication history</h2><p>Credential and scope-verification evidence.</p></div></header>{authentication.length === 0 ? <EmptyState title="No authentication evidence" description="No authentication attempts are recorded."/> : <div className="evidence-feed">{authentication.map((event) => <div key={event.event_id}><span className={`evidence-dot evidence-dot--${event.severity.toLowerCase()}`}/><div><strong>{event.outcome}</strong><p>{event.summary}</p><small><Clock3 size={12}/>{formatAgentEvidenceDate(event.timestamp)}</small></div></div>)}</div>}</article>
          <article className="investigation-card"><header><FileSearch/><div><h2>Tool requests and decisions</h2><p>Sanitized request lifecycle evidence.</p></div></header>{requests.length === 0 ? <EmptyState title="No tool requests" description="This identity has not submitted a controlled-tool request."/> : <div className="request-evidence">{requests.map((request) => <button type="button" key={request.request_id} onClick={() => navigate(request.path)}><div><strong>{request.action}</strong><small>{request.target || "No target"}</small></div><span>{request.policy_decision}</span><small>{request.execution_status}</small></button>)}</div>}</article>
        </section>

        <section className="investigation-card">
          <header><KeyRound/><div><h2>Credential history</h2><p>Issue, rotation, and revocation evidence &mdash; never the credential itself.</p></div></header>
          {credentialHistory.isLoading && <LoadingState label="Loading credential history" rows={3}/>}
          {credentialHistory.isError && <ErrorState message={credentialHistory.error.message} onRetry={() => void credentialHistory.refetch()}/>}
          {credentialHistory.data && (credentialHistory.data.events.length === 0
            ? <EmptyState title="No credential events" description="No issue, rotation, or revocation events are recorded for this agent."/>
            : <>
              <div className="evidence-table evidence-table--credential">
                <div className="evidence-table__head"><span>Time</span><span>Event</span><span>Actor</span></div>
                {credentialHistory.data.events.map((event) => <div key={event.id}>
                  <span>{formatAgentEvidenceDate(event.timestamp)}</span>
                  <strong className={`evidence-outcome evidence-outcome--${event.event_type === "REVOKED" ? "block" : event.event_type === "ROTATED" ? "ask" : "allow"}`}>{event.event_type}</strong>
                  <span>{event.actor}</span>
                </div>)}
              </div>
              <div className="credential-history__pager">
                <button type="button" disabled={credentialHistoryOffset === 0} onClick={() => setCredentialHistoryOffset((offset) => Math.max(0, offset - CREDENTIAL_HISTORY_PAGE_SIZE))}>Newer</button>
                <small>{Math.min(credentialHistoryOffset + 1, credentialHistory.data.total)}&ndash;{Math.min(credentialHistoryOffset + CREDENTIAL_HISTORY_PAGE_SIZE, credentialHistory.data.total)} of {credentialHistory.data.total}</small>
                <button type="button" disabled={credentialHistoryOffset + CREDENTIAL_HISTORY_PAGE_SIZE >= credentialHistory.data.total} onClick={() => setCredentialHistoryOffset((offset) => offset + CREDENTIAL_HISTORY_PAGE_SIZE)}>Older</button>
              </div>
            </>)}
        </section>
      </>
    })()}
  </main>
}
