# Agent Framework Adapters

GreyGuard adapters translate framework-specific structured tool calls into the
same authenticated, scoped, policy-controlled request lifecycle. They do not
execute framework code, make outbound connections, or store credentials.

## Supported adapters

| Adapter ID | Input action field | Input arguments field |
| --- | --- | --- |
| `mcp_gateway` | `name` | `arguments` |
| `langchain` | `tool` | `input` |
| `langgraph` | `action` | `state` |
| `crewai` | `tool` | `arguments` |
| `autogen` | `function_call.name` | `function_call.arguments` |
| `generic_webhook` | `action` | `payload` |
| `agentguard_legacy` | `permission` | `context` |

All requests require a registered GreyGuard agent name and credential. The
requested action must be present in both the agent scope and the adapter's
capability manifest.

## Activation checklist

1. Open **Agent Adapters** as a Platform Administrator.
2. Select the minimum allowed actions.
3. Enter a responsible owner and a specific purpose statement.
4. Run the isolated test environment.
5. Enable the adapter only after the test passes.
6. Use the adapter-specific `/adapter-requests/{adapter_id}` endpoint.

Adapters are disabled by default. Turning an adapter off activates its kill
switch immediately; new translated requests fail closed. Existing GreyGuard
audit and request evidence remains available.

## Security boundaries

- Maximum inbound payload size is 32 KiB.
- Sensitive argument fields are redacted before persistence.
- The test environment performs translation only and creates no request.
- No adapter imports or executes LangChain, LangGraph, CrewAI, AutoGen, or MCP
  runtime code.
- No adapter has direct access to the tool executor.
- Temporary submission retries require one idempotency key.

To remove an adapter, activate its kill switch, revoke affected agent
credentials if necessary, preserve audit evidence, remove its definition and
tests, and verify that `/adapters` no longer advertises it.
