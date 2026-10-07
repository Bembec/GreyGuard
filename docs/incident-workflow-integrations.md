# Incident workflow integrations

GreyGuard creates deduplicated incident records in Jira and ServiceNow. Integrations are disabled by default, require HTTPS and keep credentials in an external secret provider. A background worker (`backend/app/outbound_worker.py`) resolves only the external credential environment reference at send time, presents it as a bearer credential, and delivers through the shared SSRF-safe sender in `backend/app/outbound_delivery.py` with fresh address validation, DNS-rebinding-resistant connection pinning, no redirect following, bounded timeouts, an `Idempotency-Key` on every request, and capped exponential backoff with jitter up to the destination's configured attempt limit before moving to a dead-letter state. Creation status, external identifiers, delivery time and sanitized failures are retained as evidence.

Expiring approval links use 256-bit random tokens stored only as SHA-256 hashes. The plaintext token is shown once, expires within 5–60 minutes, is single-use and still requires an authenticated GreyGuard administrator. Consuming a link applies its predetermined approval or denial to the pending tool request and records the link identifier in the approval note.

Callbacks require an HMAC-SHA256 signature and an externally stored signing-key reference. Invalid or modified callbacks are rejected while retaining hash-only verification evidence.

To remove an integration, disable it, stop its worker, revoke its external credentials and callback key, revoke outstanding links, preserve required evidence and verify that no queued record remains active.
