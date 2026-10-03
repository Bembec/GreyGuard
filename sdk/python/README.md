# GreyGuard Python SDK

The GreyGuard SDK gives Python agents a typed, dependency-free client for
policy evaluation and controlled tool requests.

## Install for local development

```powershell
python -m pip install -e sdk\python
```

## Safe usage

Load credentials from the environment or a secret manager. Never hardcode,
print, or commit an agent credential.

```python
import os
from greyguard_sdk import GreyGuardClient, ToolRequest

client = GreyGuardClient(
    os.environ["GREYGUARD_URL"],
    os.environ["GREYGUARD_AGENT_NAME"],
    os.environ["GREYGUARD_AGENT_KEY"],
    scopes={"read_file"},
)

result = client.submit(ToolRequest(action="read_file", target="report.txt"))
print(result.request_id, result.execution_status)
```

Submission retries use one `Idempotency-Key`, preventing duplicate requests.
Reuse a custom idempotency key only for the same logical request. Policy
evaluation is intentionally not retried because it can update security state.
Client representations redact credentials, and `redact()` sanitizes structured
data before logging.
