# SDK Troubleshooting

## Authentication failed

Confirm the agent name matches the identity that issued the credential. Rotate
the credential if it may have been copied, logged, or exposed. Do not print it
while diagnosing the problem.

## Action is outside declared scopes

The SDK blocked the request locally. Compare the action with the `scopes`
supplied to the client, then verify the server-side identity has the same scope.
Expand scope only when the workload genuinely requires it.

## GreyGuard is unavailable

Confirm the API health endpoint responds, the base URL is correct, and local
firewall or proxy settings permit the connection. Submissions retry bounded
temporary failures; authentication and policy failures are not retryable.

## Request remains pending

An `ASK` policy requires an authorized administrator to approve or deny the
request. Keep the request ID and inspect it through the request investigation
view instead of submitting duplicates.

## Duplicate operation concern

Allow the SDK to generate an idempotency key, or persist one application key
per logical operation. Never generate a new key merely because the first
response timed out.

## JavaScript module cannot be found

Install the package from the repository root with:

```powershell
npm install .\sdk\javascript
```

Then import from `@greyguard/sdk`. Node.js 18 or newer is required.
