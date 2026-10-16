import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, CheckCircle2, Eye, List, Network, X } from "lucide-react"
import { useMemo, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { Link } from "react-router-dom"

import { EmptyState, ErrorState, LoadingState } from "../AsyncState"
import { TimeRangeControl } from "../page/TimeRangeControl"
import { useDismissableLayer } from "../../hooks/useDismissableLayer"
import { useTimeRangeParam } from "../../hooks/useUrlState"
import {
  COLUMNS,
  TYPE_LABELS,
  decidedBy,
  describeEdge,
  layout,
  pathOf,
  previewFor,
  type ControlGraph,
  type GraphNode,
} from "../../lib/controlGraph"
import { describeRange, rangeKey, rangeQuery } from "../../lib/timeRange"
import "../../styles/control-graph.css"

const API = import.meta.env.VITE_API_BASE_URL ?? "/api"

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`, { headers: { "X-Admin-Pin": sessionStorage.getItem("greyguard_admin_pin") ?? "" } })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail ?? `Request failed with status ${response.status}.`)
  return body as T
}

type Preview = {
  read_only: true
  unreachable_tools: string[]
  remaining_tools: string[]
  affected_requests: { count: number; sample: Array<{ request_id: string; timestamp: string; action: string; policy_decision: string; path: string }> }
  window: { since: string; retained_from: string }
  note: string | null
  how_to_apply: string
}

function formatDate(value?: unknown) {
  if (typeof value !== "string" || !value) return "Not recorded"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date)
}

function factLabel(key: string) {
  const text = key.replace(/_/g, " ")
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** One agent's relationships, read-only. Every node is a real button, in reading order. */
export function ControlGraphView({ agentName }: { agentName: string }) {
  const [range, setRange] = useTimeRangeParam("30d")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [asList, setAsList] = useState(false)
  const [previewing, setPreviewing] = useState<string | null>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const panelRef = useDismissableLayer<HTMLElement>({ open: Boolean(selectedId), onClose: () => setSelectedId(null), initialFocusRef: closeRef })

  const graph = useQuery({
    queryKey: ["agent-graph", agentName, rangeKey(range)],
    queryFn: () => get<ControlGraph>(`/agents/${encodeURIComponent(agentName)}/graph?${rangeQuery(range)}`),
  })
  const data = graph.data
  const agentId = `agent:${agentName}`
  const nodes = useMemo(() => new Map((data?.nodes ?? []).map((node) => [node.id, node])), [data])
  const columns = useMemo(() => (data ? layout(data) : null), [data])
  const selected = selectedId ? nodes.get(selectedId) ?? null : null
  const highlighted = useMemo(() => (selectedId && data ? pathOf(selectedId, data.edges, agentId) : null), [selectedId, data, agentId])
  const preview = selected ? previewFor(selected) : null
  const previewQuery = useQuery({
    queryKey: ["agent-impact-preview", agentName, preview?.change, preview?.target],
    queryFn: () => get<Preview>(`/agents/${encodeURIComponent(agentName)}/impact-preview?change=${preview!.change}${preview!.target ? `&target=${encodeURIComponent(preview!.target)}` : ""}`),
    enabled: Boolean(preview) && previewing === selectedId,
  })

  function select(node: GraphNode) {
    setSelectedId((current) => (current === node.id ? null : node.id))
    setPreviewing(null)
  }

  const decision = selected?.type === "request" && data ? decidedBy(selected.id, data.edges) : undefined

  return (
    <section className="control-graph" aria-label="Relationships">
      <div className="control-graph__bar">
        <TimeRangeControl value={range} onChange={setRange} label="Relationship window" />
        {data && (
          <p className="control-graph__summary" data-testid="graph-summary">
            {data.counts.request ?? 0} requests {describeRange(range)}: <strong>{data.decision_basis.recorded} with an exact decision record</strong>
            {data.decision_basis.inferred > 0 && <>, {data.decision_basis.inferred} inferred from publication time</>}
            {data.decision_basis.unknown > 0 && <>, {data.decision_basis.unknown} with no known policy version</>}.
            {" "}History is retained from {formatDate(data.window.retained_from)}; older history is not retained.
          </p>
        )}
        <button type="button" className="gg-button" aria-pressed={asList} onClick={() => setAsList((value) => !value)}>
          {asList ? <Network size={15} aria-hidden="true" /> : <List size={15} aria-hidden="true" />}
          {asList ? "Show as columns" : "Show as a list"}
        </button>
      </div>

      {data?.truncated && (
        <p className="control-graph__notice" role="status">
          <AlertTriangle size={15} aria-hidden="true" /> The graph is limited to {data.limit} items, so some are not shown
          {Object.keys(data.dropped).length > 0 && <> ({Object.entries(data.dropped).map(([type, count]) => `${count} ${type.replace("_", " ")}`).join(", ")})</>}.
          {" "}Narrow the window, or use <Link to={`/requests?q=${encodeURIComponent(agentName)}`}>Tool Requests</Link> for the full list.
        </p>
      )}
      {data && data.withheld.install_level > 0 && (
        <p className="control-graph__notice" role="status">
          {data.withheld.install_level} install-level incident{data.withheld.install_level === 1 ? "" : "s"} about this agent name exist but are not shown: install operator access is required.
        </p>
      )}

      {graph.isLoading && <LoadingState label="Loading relationships" rows={5} />}
      {graph.isError && <ErrorState message={graph.error.message} onRetry={() => void graph.refetch()} />}

      {data && columns && !asList && (
        <div className={`control-graph__columns${highlighted ? " has-selection" : ""}`}>
          {COLUMNS.map((column) => (
            <div className="control-graph__column" key={column.id} role="group" aria-labelledby={`cg-${column.id}`}>
              <h3 id={`cg-${column.id}`}>{column.title}<small>{column.hint}</small></h3>
              {columns[column.id].length === 0 ? (
                <p className="control-graph__empty">{column.id === "requests" ? `No requests ${describeRange(range)}.` : "None."}</p>
              ) : (
                <ul>
                  {columns[column.id].map((node) => {
                    const basis = node.type === "request" ? decidedBy(node.id, data.edges)?.basis : undefined
                    return (
                      <li key={node.id}>
                        <button
                          type="button"
                          className={`control-graph__node control-graph__node--${node.type}${highlighted?.has(node.id) ? " is-on-path" : ""}`}
                          aria-pressed={selectedId === node.id}
                          aria-label={`${TYPE_LABELS[node.type]}: ${node.label}${node.status ? `, ${node.status}` : ""}${basis ? `, ${basis === "recorded" ? "exact decision record" : "inferred decision"}` : ""}`}
                          onClick={() => select(node)}
                        >
                          <span className="control-graph__type">{TYPE_LABELS[node.type]}</span>
                          <span className="control-graph__label">{node.label}</span>
                          {node.status && <span className={`control-graph__status status--${node.status.toLowerCase()}`}>{node.status}</span>}
                          {basis && <span className={`control-graph__basis basis--${basis}`}>{basis === "recorded" ? "Exact" : "Inferred"}</span>}
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}

      {data && asList && (
        <div className="control-graph__list">
          {data.edges.length === 0 ? <EmptyState title="No relationships" description="Nothing is linked to this agent in the window." /> : (
            <ul>
              {data.edges.map((edge, index) => (
                <li key={`${edge.from}-${edge.kind}-${edge.to}-${index}`}>
                  <button type="button" onClick={() => { const node = nodes.get(edge.from); if (node) select(node) }}>{describeEdge(edge, nodes)}</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* In a portal, so no stacking context in the page can put the shell's top bar over it. */}
      {selected && createPortal(
        <aside className="control-graph__panel" ref={panelRef} aria-label={`${TYPE_LABELS[selected.type]} details`} tabIndex={-1}>
          <header>
            <div>
              <small>{TYPE_LABELS[selected.type]}</small>
              <h3>{selected.label}</h3>
            </div>
            <button type="button" ref={closeRef} className="control-graph__close" aria-label="Close details" onClick={() => setSelectedId(null)}><X size={16} aria-hidden="true" /></button>
          </header>
          {selected.status && <p><span className={`control-graph__status status--${selected.status.toLowerCase()}`}>{selected.status}</span></p>}
          {selected.facts && Object.keys(selected.facts).length > 0 && (
            <dl>
              {Object.entries(selected.facts).map(([key, value]) => (
                <div key={key}><dt>{factLabel(key)}</dt><dd>{key.endsWith("_at") || key === "timestamp" ? formatDate(value) : String(value ?? "Not recorded")}</dd></div>
              ))}
            </dl>
          )}

          {decision && (
            <section className={`control-graph__evidence evidence--${decision.basis}`} aria-label="Decision evidence">
              {decision.basis === "recorded" ? (
                <>
                  <h4><CheckCircle2 size={15} aria-hidden="true" /> Exact decision record</h4>
                  <dl>
                    <div><dt>Outcome</dt><dd>{decision.outcome}</dd></div>
                    <div><dt>Matched rule</dt><dd>{decision.rule_name} <code>{decision.matched_rule_id}</code></dd></div>
                    <div><dt>Rule type</dt><dd>{decision.rule_type}</dd></div>
                    <div><dt>Decided under</dt><dd>{nodes.get(decision.to)?.label ?? decision.to} ({decision.policy_source?.toLowerCase()})</dd></div>
                  </dl>
                  <p className={decision.record_intact ? "is-ok" : "is-bad"}>
                    {decision.record_intact ? "The record matches the fingerprint taken when it was written." : "The record no longer matches its fingerprint. Treat it as tampered."}
                  </p>
                  {decision.policy_matches === false && (
                    <p className="is-warn">The stored policy version has changed since this decision. The record keeps what actually decided.</p>
                  )}
                  {decision.policy_matches === true && <p className="is-ok">The stored policy version still holds the content that decided.</p>}
                </>
              ) : (
                <>
                  <h4><AlertTriangle size={15} aria-hidden="true" /> Inferred, not recorded</h4>
                  <p>{decision.note}</p>
                  <p>Likely version: {nodes.get(decision.to)?.label ?? decision.to}. A staged rollout or a publication at the same moment can make this wrong.</p>
                </>
              )}
            </section>
          )}
          {selected.type === "request" && !decision && (
            <p className="is-warn">No policy version is known for this request: it has no decision record, and no version was published before it.</p>
          )}

          {preview && (
            <section className="control-graph__preview" aria-label="Impact preview">
              <h4><Eye size={15} aria-hidden="true" /> Impact preview <span className="control-graph__readonly">Read-only</span></h4>
              <p>{preview.label}: what it would affect.</p>
              {previewing !== selected.id ? (
                <button type="button" className="gg-button" onClick={() => setPreviewing(selected.id)}>Preview impact</button>
              ) : previewQuery.isLoading ? <LoadingState label="Working out the impact" rows={2} /> : previewQuery.isError ? (
                <ErrorState message={previewQuery.error.message} onRetry={() => void previewQuery.refetch()} />
              ) : previewQuery.data && (
                <div data-testid="impact-preview">
                  <p><strong>Tools that would become unreachable:</strong> {previewQuery.data.unreachable_tools.length ? previewQuery.data.unreachable_tools.join(", ") : "none"}.</p>
                  <p><strong>{previewQuery.data.affected_requests.count}</strong> allowed or approval-pending request{previewQuery.data.affected_requests.count === 1 ? "" : "s"} since {formatDate(previewQuery.data.window.since)} would now be refused.</p>
                  {previewQuery.data.affected_requests.sample.length > 0 && (
                    <ul>{previewQuery.data.affected_requests.sample.slice(0, 5).map((request) => (
                      <li key={request.request_id}><Link to={request.path}>{request.action}</Link> · {formatDate(request.timestamp)}</li>
                    ))}</ul>
                  )}
                  {previewQuery.data.note && <p>{previewQuery.data.note}</p>}
                  <p className="control-graph__howto">{previewQuery.data.how_to_apply}</p>
                </div>
              )}
            </section>
          )}
          {selected.path && <Link className="gg-button" to={selected.path}>Open {TYPE_LABELS[selected.type].toLowerCase()} page</Link>}
        </aside>,
        document.body,
      )}
    </section>
  )
}
