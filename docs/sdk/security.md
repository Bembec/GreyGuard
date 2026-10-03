# SDK Security Practices

## Credential handling

- Give each workload its own agent identity.
- Grant only required action scopes.
- Load credentials from environment variables or a secret manager.
- Never log request headers, SDK internals, or environment variables.
- Rotate a credential after suspected exposure and revoke the previous value.
- Do not ship credentials in public browser or mobile bundles.

The SDKs redact credentials from their normal representations, but redaction is
not a substitute for safe application logging.

## Retry safety

Tool submissions retry only temporary failures: HTTP `429`, `502`, `503`, and
`504`, plus connection failures. Every retry reuses the same idempotency key,
so GreyGuard returns the original request instead of creating another request
or applying risk twice.

Policy evaluation is not retried because it can change security state. Reads
are safe to retry. Application code must reuse a custom idempotency key only
for the same logical tool request.

## Failure handling

- Treat authentication failures as credential incidents, not retry loops.
- Treat authorization failures as configuration or policy decisions.
- Do not weaken a requested action to evade a block.
- Set bounded timeouts and fail closed when GreyGuard is unavailable.
- Preserve the returned request ID for investigation and audit correlation.

## Browser warning

The JavaScript SDK uses standard Fetch APIs and can run in modern browsers,
but long-lived agent credentials must not be embedded in frontend code. Use it
from a trusted server-side runtime or an approved secure execution environment.
