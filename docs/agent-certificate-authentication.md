# Agent certificate authentication (optional mTLS)

GreyGuard agents normally authenticate with `X-Agent-Name` / `X-Agent-Key` (see
`docs/agent-integration.md`). This adds a second, additive way to prove the same identity: a
client TLS certificate, verified by the reverse proxy. **Nothing about key-based authentication
changes.** An agent that never presents a certificate is authenticated exactly as it always has
been. This path is itself disabled until an operator explicitly turns it on.

## Trust boundary: nginx verifies, GreyGuard trusts the verdict

GreyGuard does not parse or validate a certificate chain itself. nginx is the TLS termination
point for this deployment (see `docs/deployment-operations-part2.md`), and when agent mTLS is
enabled, nginx is also the **only** verifier of the certificate chain and its validity period.
The backend trusts nginx's verdict through two headers nginx sets on every proxied request:

| Header | Source | Meaning |
|---|---|---|
| `X-SSL-Client-Verify` | `$ssl_client_verify` | `SUCCESS`, `NONE` (no certificate presented), or `FAILED:<reason>` (expired, untrusted, wrong CA, etc. — nginx determines this during the TLS handshake) |
| `X-SSL-Client-Cert` | `$ssl_client_escaped_cert` | URL-escaped PEM of the verified certificate, empty when none was presented |

**This is only safe because of two properties that must both hold:**

1. **The backend is never reachable except through nginx.** In `docker-compose.production.yml`
   the `backend` service has no published port and sits on the internal-only
   `greyguard-internal` network; only the `frontend` (nginx) container can reach it.
2. **nginx unconditionally overwrites these two header names on every request it proxies**,
   regardless of what the original client sent. `proxy_set_header` in nginx always replaces a
   header of the same name — it never merges with or passes through a client-supplied value. A
   client cannot set its own `X-SSL-Client-Verify: SUCCESS` and have it reach the backend
   unless it goes directly through property 1's violation. The `proxy_set_header` lines for
   these two headers in `deployment/nginx-tls.conf` are placed directly in each location block
   (never inside a conditional), specifically so they always run.

Given both properties, the backend's only remaining job is to require **exact equality**
(`X-SSL-Client-Verify == "SUCCESS"`) and treat every other value — `NONE`, any `FAILED:...`,
absent entirely — as "no certificate," never as a partial or implicit success.

As a third, independent layer, the backend also requires the deployment to explicitly opt in
with `GREYGUARD_TRUST_CLIENT_CERT_HEADERS=true`. Leaving it unset (the default) makes
certificate authentication always fail, even with a perfectly well-formed, verified header pair
— so a backend that is accidentally exposed without the network isolation above still refuses
to trust these headers until an operator has deliberately turned the feature on.

## Enabling it

1. Issue or obtain a CA that will sign agent client certificates. This CA is independent of the
   CA used for the server's own TLS certificate.
2. In `deployment/nginx-tls.conf`, uncomment and configure:
   ```
   ssl_client_certificate /etc/nginx/tls/agent-ca.pem;
   ssl_verify_client optional;
   ssl_verify_depth 2;
   ```
   `optional` (not `on`) is required: this same listener also serves browser/admin traffic,
   which never presents a client certificate and must not be forced to.
3. Set `GREYGUARD_TRUST_CLIENT_CERT_HEADERS=true` on the backend.
4. Issue a client certificate to the agent from that CA, and register it:
   `POST /enterprise-identity/workloads` with the certificate's PEM text, a name, a subject, and
   `agent_name` set to an **already-registered** agent (one that already has an
   `X-Agent-Name`/`X-Agent-Key` identity — certificate authentication proves the same identity
   by a second method, it does not create a new kind of identity). The registration computes
   the certificate's SHA-256 thumbprint (of its PEM text, not the parsed DER bytes — see
   `enterprise_identity.certificate_thumbprint`) and stores only that thumbprint, never the
   certificate material itself.
5. The agent now authenticates by presenting that certificate during the TLS handshake instead
   of (or alongside — the header is simply not sent) `X-Agent-Key`.

## Revocation

`POST /enterprise-identity/workloads/{workload_id}/revoke` with a reason immediately and
permanently invalidates that certificate binding (`status` becomes `REVOKED`, `revoked_at` is
recorded). A revoked, expired, or otherwise non-`ACTIVE`/agent-bound workload identity is
indistinguishable from "no matching certificate" to the authentication check — both fail the
same way. Revoking a workload identity does not touch the agent's `X-Agent-Key` credential or
scopes at all; the two credential types are revoked independently.

Separately, suspending the **agent itself** (`credential_status` leaving `ACTIVE` on its
`X-Agent-Name`/`X-Agent-Key` identity) also blocks certificate authentication for that agent,
even if its certificate binding is still active — identity suspension is agent-wide, not
per-credential-type.

## Evidence

Every attempt — success or failure — is recorded in the same `authentication_events` table used
by key-based authentication, with outcomes `CERTIFICATE_AUTHENTICATED` or
`CERTIFICATE_AUTHENTICATION_FAILED`. The specific reason for a failure (unverified proxy status,
no matching registered certificate, claimed-agent mismatch, revoked agent) is recorded in that
evidence row, but the error returned to the caller is always the same generic message — mirroring
the existing key-based authentication's own convention of never telling a caller *why* their
attempt failed. A successful certificate authentication also updates the workload identity's
`last_authenticated_at`.

## What this does not do

- It does not change how `X-Agent-Name`/`X-Agent-Key` authentication works, and does not weaken
  it: an existing agent integration is completely unaffected whether or not this feature is ever
  enabled.
- It does not grant any scope beyond what the bound agent already has. A certificate only proves
  *which* agent is calling; `main.enforce_agent_scope` checks the resulting identity's stored
  scopes exactly as it does for a key-authenticated request.
- It does not support a certificate authenticating as an agent that does not already exist, or
  as more than one agent.
