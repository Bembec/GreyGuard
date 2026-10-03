# GreyGuard Observability

GreyGuard emits W3C trace context, OTLP-compatible JSON spans, Prometheus text
metrics, and structured JSON request logs. Platform Administrators control
collection and sampling from **Observability**.

Every request receives `X-Correlation-ID` and `traceparent` response headers.
Clients may supply a valid correlation ID and W3C traceparent. When a tool
request is created, GreyGuard binds its correlation ID to the request ID so
later approval, execution, and investigation routes continue the same
correlation automatically.

## Export surfaces

- `GET /observability/traces` returns bounded OTLP JSON trace evidence.
- `GET /observability/metrics` returns Prometheus text format.
- Structured request logs use JSON with trace, span, correlation, status, path,
  method, and duration fields.

All surfaces require Platform Administrator authorization. Passwords, secrets,
tokens, credentials, authorization values, API keys, and PINs are redacted
before telemetry is logged, retained, displayed, or exported.

## Sampling and retention

Tracing defaults to 25% deterministic sampling with a maximum of 5,000 stored
spans. Sampling accepts values from 0% to 100%; retention accepts 100 to 100,000
spans. Metrics and structured logs may be disabled independently. Configuration
changes affect new requests.

## Removal and emergency disablement

Set trace sampling to 0% and disable tracing, metrics, and structured logs.
Existing span evidence remains bounded by retention until removed under the
organization's evidence policy. Removal of the module must also remove its API
routes and middleware, then rerun security and correlation tests.
