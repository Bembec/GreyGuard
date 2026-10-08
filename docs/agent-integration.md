# GreyGuard Agent Integration

GreyGuard governs only agents explicitly registered and connected to its API.

## Core principle

> Agent identity is not the same as agent permission.

A credential proves the agent identity. Scopes, policy, risk, approvals,
suspension state, and sandbox controls determine what it may do.

## Safe integration flow

1. An administrator registers an agent.
2. GreyGuard issues its credential once.
3. The credential is stored outside source code.
4. The administrator assigns minimum required scopes.
5. The agent uses `GreyGuardAgentClient`.
6. GreyGuard evaluates every request before controlled execution.
7. Evidence appears in Audit Trail and Live Operations.

## Agent example

```python
from backend.sdk import GreyGuardAgentClient

agent = GreyGuardAgentClient(
    base_url="http://127.0.0.1:8000",
    agent_name="document_agent",
    credential="read-from-environment",
)

result = agent.request_tool(
    action="read_file",
    target="public_report.txt",
    dry_run=True,
)
```

The SDK never executes an operation itself. GreyGuard remains responsible for
identity, authorization, human approval, risk, and sandboxed execution.

## Credential rotation, revocation, and history

`POST /agents/{agent_name}/credential/rotate` issues a new credential and immediately
invalidates the previous one; `POST /agents/{agent_name}/credential/revoke` disables the agent's
credential entirely without issuing a replacement. Both require Platform Administrator
permission (`identity:manage`) and record who did it.

`GET /agents/{agent_name}/credential-history` (readable by any administrator role, like other
evidence views) returns a paginated, newest-first log of every issue/rotate/revoke event for
that agent — timestamp and the administrator who performed it, `limit`/`offset` for paging.
It never includes the credential or its hash; those are never persisted anywhere past the
response that first displayed a new credential to the administrator who issued or rotated it.
The agent detail page in the console shows this history with Newer/Older paging.

## Certificate-based authentication (optional)

An agent may instead (or additionally) prove its identity with a TLS client certificate verified
by the reverse proxy, in deployments that enable it. This is a second way to prove the same
identity a registered agent already has — it changes nothing about scopes, policy, or the above
flow. See `docs/agent-certificate-authentication.md` for the nginx/mTLS boundary this requires.
