/**
 * The Control Graph's reading logic (P7.5 item 4). The server builds the graph and decides what the
 * caller may see; this file only lays it out and explains it.
 *
 * Layout is five fixed columns read left to right, in the order the gateway decides, not a
 * free-floating force graph: identity, scopes, tools and policy, requests, outcomes.
 */

export type NodeType = "agent" | "credential" | "scope" | "tool" | "control" | "policy_version" | "request" | "approval" | "incident"

export interface GraphNode {
  id: string
  type: NodeType
  label: string
  status?: string
  path?: string
  facts?: Record<string, unknown>
}

export interface GraphEdge {
  from: string
  to: string
  kind: "authenticates_with" | "grants" | "reaches" | "limits" | "governs" | "requested" | "uses" | "decided_by" | "reviewed_by" | "raised"
  basis?: "recorded" | "inferred"
  matched_rule_id?: string
  rule_type?: string
  rule_name?: string
  outcome?: string
  policy_source?: string
  record_intact?: boolean
  policy_matches?: boolean | null
  note?: string
}

export interface ControlGraph {
  agent: string
  generated_at: string
  window: { since: string; until: string | null; retained_from: string }
  depth: number
  limit: number
  nodes: GraphNode[]
  edges: GraphEdge[]
  counts: Record<string, number>
  decision_basis: { recorded: number; inferred: number; unknown: number }
  withheld: { install_level: number }
  truncated: boolean
  dropped: Record<string, number>
}

export const COLUMNS = [
  { id: "identity", title: "Identity", hint: "The agent, its credential and any control on it" },
  { id: "scopes", title: "Scopes", hint: "What the credential grants" },
  { id: "tools", title: "Tools and policy", hint: "What the scopes reach, and what decides" },
  { id: "requests", title: "Requests", hint: "In the window, grouped by decision" },
  { id: "outcomes", title: "Outcomes", hint: "Approvals and incidents" },
] as const

export type ColumnId = (typeof COLUMNS)[number]["id"]

/** Which column a node belongs in. Controls on the agent sit with identity; the rest with tools. */
export function columnOf(node: GraphNode, edges: GraphEdge[], agentId: string): ColumnId {
  switch (node.type) {
    case "agent":
    case "credential":
      return "identity"
    case "control":
      return edges.some((edge) => edge.from === node.id && edge.to === agentId && edge.kind === "limits") ? "identity" : "tools"
    case "scope":
      return "scopes"
    case "tool":
    case "policy_version":
      return "tools"
    case "request":
      return "requests"
    default:
      return "outcomes"
  }
}

const DECISION_ORDER = ["BLOCK", "REFUSED", "ASK", "ALLOW"]

export function layout(graph: ControlGraph): Record<ColumnId, GraphNode[]> {
  const agentId = `agent:${graph.agent}`
  const columns = Object.fromEntries(COLUMNS.map((column) => [column.id, [] as GraphNode[]])) as Record<ColumnId, GraphNode[]>
  for (const node of graph.nodes) columns[columnOf(node, graph.edges, agentId)].push(node)
  // Requests group by decision, the riskiest first; within a group the server's order (newest) stays.
  const rank = (node: GraphNode) => {
    const index = DECISION_ORDER.indexOf(node.status ?? "")
    return index === -1 ? DECISION_ORDER.length : index
  }
  columns.requests = columns.requests.map((node, index) => ({ node, index }))
    .sort((a, b) => rank(a.node) - rank(b.node) || a.index - b.index).map((item) => item.node)
  return columns
}

/**
 * A node's path: everything upstream and downstream of it. The agent is included when reached
 * but never expanded, because everything hangs off it and the highlight would cover the graph.
 */
export function pathOf(nodeId: string, edges: GraphEdge[], agentId: string): Set<string> {
  const path = new Set([nodeId])
  for (const direction of ["forward", "backward"] as const) {
    const queue = [nodeId]
    while (queue.length > 0) {
      const current = queue.shift() as string
      if (current === agentId && current !== nodeId) continue
      for (const edge of edges) {
        const [from, to] = direction === "forward" ? [edge.from, edge.to] : [edge.to, edge.from]
        if (from === current && !path.has(to)) {
          path.add(to)
          queue.push(to)
        }
      }
    }
  }
  return path
}

export function decidedBy(requestId: string, edges: GraphEdge[]): GraphEdge | undefined {
  return edges.find((edge) => edge.from === requestId && edge.kind === "decided_by")
}

const VERBS: Record<GraphEdge["kind"], string> = {
  authenticates_with: "authenticates with",
  grants: "grants",
  reaches: "reaches",
  limits: "limits",
  governs: "governs",
  requested: "requested",
  uses: "uses",
  decided_by: "was decided by",
  reviewed_by: "was reviewed:",
  raised: "raised",
}

/** One relationship as a sentence, for the list view and screen readers. */
export function describeEdge(edge: GraphEdge, nodes: Map<string, GraphNode>): string {
  const from = nodes.get(edge.from)?.label ?? edge.from
  const to = nodes.get(edge.to)?.label ?? edge.to
  let sentence = `${from} ${VERBS[edge.kind]} ${to}`
  if (edge.kind === "decided_by") {
    sentence += edge.basis === "recorded"
      ? ` (exact record${edge.rule_name ? `, rule “${edge.rule_name}”` : ""})`
      : " (inferred from publication time, not recorded)"
  }
  return sentence
}

/** Which change a node can preview, if any. The preview only reads; nothing is changed. */
export function previewFor(node: GraphNode): { change: "revoke_scope" | "revoke_credential" | "disable_tool"; target?: string; label: string } | null {
  if (node.type === "scope") return { change: "revoke_scope", target: node.label, label: `Revoking the ${node.label} scope` }
  if (node.type === "credential") return { change: "revoke_credential", label: "Revoking this agent's credential" }
  if (node.type === "tool") return { change: "disable_tool", target: node.label, label: `Disabling the ${node.label} tool` }
  return null
}

export const TYPE_LABELS: Record<NodeType, string> = {
  agent: "Agent", credential: "Credential", scope: "Scope", tool: "Tool", control: "Control",
  policy_version: "Policy version", request: "Request", approval: "Approval", incident: "Incident",
}
