# GreyGuard JavaScript/TypeScript SDK

The GreyGuard SDK provides a zero-dependency, typed client for Node.js 18+
and modern browsers.

## Install locally

```powershell
npm install .\sdk\javascript
```

## Safe usage

Load agent credentials from environment variables or a secret manager. Do not
embed a credential in browser-delivered code, logs, source control, or errors.

```js
import { GreyGuardClient } from "@greyguard/sdk"

const client = new GreyGuardClient({
  baseUrl: process.env.GREYGUARD_URL ?? "http://127.0.0.1:8000",
  agentName: process.env.GREYGUARD_AGENT_NAME,
  credential: process.env.GREYGUARD_AGENT_KEY,
  scopes: ["read_file"],
})

const result = await client.submit({
  action: "read_file",
  target: "public_report.txt",
})

console.log(result.request_id, result.execution_status)
```

Submissions reuse one `Idempotency-Key` during transient retries. Reuse a
custom key only for the same logical request. Policy evaluation is deliberately
not retried because it can update security state.
