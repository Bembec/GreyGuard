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

The queue processor accepts an injected transport function so production deployments can use a separately constrained HTTPS or TLS worker. The worker should use outbound allowlists, certificate verification, strict timeouts and workload identity. Never place destination credentials in GreyGuard source code.

## Removal

Disable the destination, stop its worker, revoke external credentials, preserve required delivery evidence, remove queued records according to the approved retention policy, and verify no network route remains.
