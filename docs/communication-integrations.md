# Communication integrations

GreyGuard supports governed delivery preparation for email, Slack, Microsoft Teams, PagerDuty and Opsgenie. Destinations are disabled by default and store only references to externally managed credentials or endpoints.

Events are redacted before queueing. Minimum-severity rules reduce noise, deterministic keys suppress duplicates, quiet hours defer non-critical messages, and approved critical alerts may bypass quiet hours. Escalation delay is stored per destination for worker scheduling. Every delivery attempt records status, attempt count, delivery time and sanitized failure evidence.

Templates accept only the approved fields `title`, `severity`, `summary`, `event_type` and `resource_path`; credential fields cannot be interpolated. A background worker (`backend/app/outbound_worker.py`) delivers queued notifications through the shared SSRF-safe sender in `backend/app/outbound_delivery.py`: HTTPS-only webhook URLs, fresh address validation and DNS-rebinding-resistant connection pinning on every attempt, no redirect following, bounded timeouts, capped exponential backoff with jitter, and a dead-letter state after the destination's configured attempt limit. Delivery is immediately stopped for a disabled destination because disabled destinations are never claimed by the worker. EMAIL is accepted as a channel but its SMTP transport is not yet implemented; those notifications fail closed to a dead-letter state rather than being silently dropped.

Removal requires disabling the destination, stopping its worker, revoking the external credential, preserving required delivery evidence and confirming that no queued delivery remains active.
