export interface ToolRequest {
  action: string
  target?: string
  payload?: Record<string, unknown>
  dryRun?: boolean
}

export interface PolicyEvaluation {
  action: string
  policy_decision: "ALLOW" | "ASK" | "BLOCK" | string
  approval?: string | null
  risk_score?: number | null
  [key: string]: unknown
}

export interface ToolRequestResult {
  request_id: string
  action: string
  approval_status?: string | null
  execution_status?: string | null
  policy_decision?: string | null
  [key: string]: unknown
}

export type FetchImplementation = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Response>

export interface GreyGuardClientOptions {
  baseUrl: string
  agentName: string
  credential: string
  scopes?: Iterable<string>
  timeoutMs?: number
  maxRetries?: number
  fetch?: FetchImplementation
  sleep?: (milliseconds: number) => Promise<void>
}

export class GreyGuardError extends Error {}
export class AuthenticationError extends GreyGuardError {}
export class AuthorizationError extends GreyGuardError {}
export class ScopeValidationError extends GreyGuardError {}
export class RequestError extends GreyGuardError {
  statusCode: number | null
  details: unknown
}

export class GreyGuardClient {
  constructor(options: GreyGuardClientOptions)
  readonly baseUrl: string
  readonly agentName: string
  readonly timeoutMs: number
  readonly maxRetries: number
  toJSON(): {
    baseUrl: string
    agentName: string
    credential: "[REDACTED]"
  }
  evaluate(action: string): Promise<PolicyEvaluation>
  submit(
    request: ToolRequest,
    options?: { idempotencyKey?: string },
  ): Promise<ToolRequestResult>
  getRequest(requestId: string): Promise<ToolRequestResult>
}

export function redact<T>(value: T): T
