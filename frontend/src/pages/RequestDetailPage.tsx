import { ArrowLeft, Bot, CheckCircle2, ClipboardList, Download, FileJson, RefreshCw, Route, ShieldCheck } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate, useParams } from "react-router-dom"

import { ErrorState, LoadingState } from "../components/AsyncState"
import "../styles/request-detail.css"

type Bundle = {
  request: Record<string, string | number | boolean | null>
  decision_explanation: string
  timeline: Array<{ type: string; timestamp: string; status: string; actor: string; detail: string }>
  redacted_evidence: Record<string, unknown>
  correlations: { agent_path: string; request_id: string }
}
const API = import.meta.env.VITE_API_BASE_URL ?? "/api"

export function safeBundleFilename(requestId: string) {
  return `greyguard-request-${requestId.replace(/[^a-zA-Z0-9_-]/g, "-")}.json`
}

async function loadBundle(id: string): Promise<Bundle> {
  const token = sessionStorage.getItem("greyguard_admin_pin")
  const response = await fetch(`${API}/request-investigations/${encodeURIComponent(id)}`, { headers: { "X-Admin-Pin": token ?? "" } })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail ?? "Request investigation could not be loaded.")
  return body as Bundle
}

export default function RequestDetailPage() {
  const { requestId = "" } = useParams()
  const navigate = useNavigate()
  const bundle = useQuery({ queryKey: ["request-investigation", requestId], queryFn: () => loadBundle(requestId), enabled: Boolean(requestId) })
  const request = bundle.data?.request
  const download = () => { const data = bundle.data; if (!data) return; const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })); const link = document.createElement("a"); link.href = url; link.download = safeBundleFilename(requestId); link.click(); URL.revokeObjectURL(url) }

  return <main className="request-investigation">
    <header className="request-investigation__hero"><button onClick={() => navigate("/requests")}><ArrowLeft size={17}/> All requests</button><div><span><Route/></span><div><p>Request investigation</p><h1>{request ? String(request.action) : requestId}</h1><code>{requestId}</code></div></div>{bundle.data && <div><button onClick={() => void bundle.refetch()}><RefreshCw size={16}/> Refresh</button><button onClick={download}><Download size={16}/> Export bundle</button></div>}</header>

    {bundle.isLoading && <LoadingState label="Loading request investigation" rows={6}/>}
    {bundle.isError && <ErrorState message={bundle.error.message} onRetry={() => void bundle.refetch()}/>}

    {bundle.data && request && (() => { const data = bundle.data; return <>
      <section className="request-investigation__posture">{[["Agent",request.agent_name,Bot],["Policy",request.policy_decision,ShieldCheck],["Approval",request.approval_status,ClipboardList],["Execution",request.execution_status,CheckCircle2]].map(([label,value,Icon]) => { const ItemIcon=Icon as typeof Bot; return <article key={label as string}><ItemIcon/><span>{label as string}</span><strong>{String(value)}</strong></article>})}</section>
      <section className="request-decision"><ShieldCheck/><div><strong>Why GreyGuard made this decision</strong><p>{data.decision_explanation}</p></div><button onClick={() => navigate(data.correlations.agent_path)}>Open agent investigation</button></section>
      <section className="request-investigation__grid"><article className="request-card"><header><Route/><div><h2>Approval and execution timeline</h2><p>Correlated lifecycle evidence in recorded order.</p></div></header><div className="request-timeline">{data.timeline.map((event,index) => <div key={`${event.type}-${event.timestamp}-${index}`}><span/><div><strong>{event.type} · {event.status}</strong><p>{event.detail}</p><small>{event.actor} · {new Date(event.timestamp).toLocaleString()}</small></div></div>)}</div></article><article className="request-card"><header><FileJson/><div><h2>Redacted raw evidence</h2><p>Sensitive credential fields are removed by the backend.</p></div></header><pre>{JSON.stringify(data.redacted_evidence, null, 2)}</pre></article></section>
    </> })()}
  </main>
}
