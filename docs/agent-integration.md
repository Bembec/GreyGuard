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
