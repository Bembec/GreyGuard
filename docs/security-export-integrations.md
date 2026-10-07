# Security, SIEM and observability exports

GreyGuard can prepare minimized, redacted security events for signed webhooks, Splunk, Microsoft Sentinel, Elastic Security, Grafana Loki, TLS Syslog and STIX/TAXII consumers.

## Safety model

- Destinations are created disabled and require explicit Platform Administrator enablement.
- Non-Syslog endpoints require HTTPS; Syslog requires TLS.
- Credentials and signing keys remain outside the database. Configuration stores only an environment-variable reference.
- Events are redacted and minimized before entering the export queue.
- Per-destination limits bound delivery volume.
- Failed deliveries use bounded retry attempts and move to a dead-letter state.
- Success/failure timestamps and sanitized error details provide destination-health evidence.
- Disabling a destination immediately prevents new queue entries and worker delivery.

## Data profiles

`MINIMAL` sends only time, type, severity, outcome and correlation identifiers. `STANDARD` adds selected investigation fields. `FORENSIC` retains the redacted event and should be enabled only when the destination and retention purpose are approved.

## Worker integration

`backend/app/outbound_worker.py` runs a background delivery loop inside the API process (safe under the two-worker production deployment: every queue row is claimed atomically before a worker acts on it, so the two processes never send the same export twice). It sends through `backend/app/outbound_delivery.py`, which enforces HTTPS, resolves and validates every destination address on each attempt (blocking loopback, link-local, multicast, unspecified, cloud metadata and private addresses unless explicitly allowed per exact hostname by a Platform Administrator), pins the connection to the validated address to resist DNS rebinding, never follows redirects, and applies bounded connect/read/total timeouts. The queue processor still accepts an injected transport function for tests. Syslog (`tls://`) delivery is not yet implemented; those exports fail closed to a dead-letter state with a clear error rather than being silently dropped or mis-sent. Never place destination credentials in GreyGuard source code.

## Removal

Disable the destination, stop its worker, revoke external credentials, preserve required delivery evidence, remove queued records according to the approved retention policy, and verify no network route remains.
