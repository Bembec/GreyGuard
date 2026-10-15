# Data protection

## In transit

- **TLS is the operator's responsibility at the edge.** The shipped frontend image listens on plain HTTP port 8080, published on the host's loopback interface only, and must be placed behind a TLS-terminating proxy or load balancer [TC-DP-1].
- **TLS template.** `deployment/nginx-tls.conf` is a production template that redirects HTTP to HTTPS, allows only TLS 1.2 and 1.3, disables session tickets and sets HSTS [TC-DP-1].
- **Browser security headers.** The shipped configuration sets a restrictive Content Security Policy, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and a Permissions Policy that disables camera, microphone and geolocation [TC-DP-2].
- **Outbound deliveries.** Every outbound request must use `https://`. The destination is resolved once and the connection is pinned to the validated address. Loopback, link-local, multicast, reserved and cloud-metadata addresses are always refused, and private addresses are refused unless an administrator has allowlisted the host [TC-DP-3].

## At rest

- **Live data.** GreyGuard does **not** encrypt the live database itself. Encryption at rest depends on the host's disk, volume or managed-database encryption, which is the operator's responsibility (GreyGuard's, for Hosted and Dedicated; the customer's, for Self-hosted) [TC-DP-4].
- **Backups.** Production PostgreSQL backups made with `postgres_backup_ops` are verified but **not encrypted by GreyGuard**; the operator must encrypt and access-control them and keep them outside the live data volume. The AES-256-GCM backup tool (`encrypted_backups`) applies only to non-production SQLite installs [TC-DP-5].

## Credentials

- Administrator passwords are hashed with PBKDF2-HMAC-SHA256 at 310,000 iterations; agent keys are also stored only as PBKDF2 hashes [TC-DP-6].
- Session access and refresh tokens, gateway enrollment tokens and gateway node credentials are stored only as SHA-256 hashes [TC-DP-6].
- **TOTP MFA seeds are stored in the database unencrypted,** because the server must read them to verify a code. They are protected by database access control and are replaced with `REDACTED` in organization exports [TC-DP-7].

## Secrets and keys

- **Integration secrets are references, not values.** GreyGuard stores a reference to Vault, AWS Secrets Manager, Azure Key Vault, Google Secret Manager or an environment variable, resolves it just in time, and never writes the value to its database, API responses or audit events [TC-DP-8].
- **Signing keys** (policy, report, distribution and release signing) and the database credentials are environment secrets held by the operator [TC-DP-9].
- **Customer-managed keys are not offered** in any deployment model; they are not implemented or verified [TC-DP-9].
- **Telemetry redaction.** Passwords, secrets, tokens, credentials, authorization values, API keys and PINs are redacted before telemetry is logged, retained, displayed or exported [TC-DP-10].
