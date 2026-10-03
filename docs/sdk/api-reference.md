# SDK API Reference

## Python

### `GreyGuardClient(...)`

Required arguments are `base_url`, `agent_name`, and `credential`. Optional
settings include declared `scopes`, request `timeout`, and `max_retries`.

### `evaluate(action)`

Authenticates and evaluates one action. Returns `PolicyEvaluation`. It is never
automatically retried.

### `submit(request, idempotency_key=None)`

Submits a `ToolRequest` and returns `ToolRequestResult`. Temporary failures are
retried using one agent-scoped idempotency key.

### `get_request(request_id)`

Returns the latest state and evidence for one agent-owned request.

## JavaScript and TypeScript

### `new GreyGuardClient(options)`

Required options are `baseUrl`, `agentName`, and `credential`. Optional options
include `scopes`, `timeoutMs`, `maxRetries`, and a compatible Fetch function.

### `evaluate(action)`

Returns a `Promise<PolicyEvaluation>` and is never automatically retried.

### `submit(request, options?)`

Returns a `Promise<ToolRequestResult>`. Supply `options.idempotencyKey` only
when the application must keep the same logical operation across restarts.

### `getRequest(requestId)`

Returns the latest state for one request owned by the authenticated agent.

## Typed failures

| Failure | Meaning |
| --- | --- |
| `AuthenticationError` | Identity or credential rejected |
| `AuthorizationError` | Authenticated identity lacks permission |
| `ScopeValidationError` | Client-declared scopes rejected the action locally |
| `RequestError` | Transport, server, or response failure |

Python exceptions expose `status_code`; JavaScript `RequestError` exposes
`statusCode`. Error details are redacted before exposure.
