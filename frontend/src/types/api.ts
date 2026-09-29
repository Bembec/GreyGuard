export interface AgentIdentity {
  agent_name: string
  scopes: string[]
  credential_status: string
  created_at: string
  rotated_at: string | null
  revoked_at: string | null
}

export interface Agent {
  agent_name: string
  agent_status: "ACTIVE" | "SUSPENDED"
  risk_score: number
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
  blocked_attempts: number
  identity: AgentIdentity | null
}

export interface HealthResponse {
  status: string
  version: string
  registered_agents: number
  registered_identities: number
  controlled_tools: number
  sandbox_initialized: boolean
}
