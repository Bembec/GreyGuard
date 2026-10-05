# Communication integrations

GreyGuard supports governed delivery preparation for email, Slack, Microsoft Teams, PagerDuty and Opsgenie. Destinations are disabled by default and store only references to externally managed credentials or endpoints.

Events are redacted before queueing. Minimum-severity rules reduce noise, deterministic keys suppress duplicates, quiet hours defer non-critical messages, and approved critical alerts may bypass quiet hours. Escalation delay is stored per destination for worker scheduling. Every delivery attempt records status, attempt count, delivery time and sanitized failure evidence.

Templates accept only the approved fields `title`, `severity`, `summary`, `event_type` and `resource_path`; credential fields cannot be interpolated. Production workers must resolve endpoint references just in time, verify recipients, use TLS, enforce timeouts and immediately stop sending when an integration is disabled.

Removal requires disabling the destination, stopping its worker, revoking the external credential, preserving required delivery evidence and confirming that no queued delivery remains active.
