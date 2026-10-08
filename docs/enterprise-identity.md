# GreyGuard enterprise identity

GreyGuard supports standards-based OIDC provider metadata for Microsoft Entra ID, Okta, Auth0, and compatible identity providers. The control plane stores issuer metadata and client identifiers but deliberately does not store provider client secrets: every configured provider is treated as a public client, authenticated with PKCE instead.

## Sign-in flow

`backend/app/enterprise_sso.py` implements the actual Authorization Code + PKCE sign-in flow on top of the provider/role-mapping configuration below (`GET /auth/sso/providers`, `POST /auth/sso/{provider_id}/begin`, `POST /auth/sso/callback`). The frontend login page shows an SSO button only for a provider that is both configured and currently enabled.

- `state`, `nonce`, and the PKCE code verifier are generated with `secrets.token_urlsafe`, stored server-side keyed by `state`, single-use (claimed atomically — a replayed callback with the same `state` is rejected), and expire after 10 minutes.
- The redirect URI is never accepted from the browser; it is always the one fixed value in `GREYGUARD_SSO_REDIRECT_URI`, which closes the open-redirect-via-`redirect_uri` attack class rather than trying to validate a caller-supplied one.
- The ID token's signature is verified with PyJWT against the provider's own JWKS (fetched and cached through the SSRF-safe `outbound_delivery` sender, never a separate network path) before any claim is trusted. Only RS256/ES256 are ever permitted — the algorithm is never taken from the token itself, and the matched key's type is cross-checked against it, closing the classic alg/key-type confusion families (including a forged `none` or `HS256` token).
- `iss`, `aud`, `exp`, `iat`, and `sub` are required and validated with a 60-second clock-skew allowance; `azp` is checked when the token carries multiple audiences; the token's `nonce` must match the one stored for that sign-in attempt.
- A JWKS lookup that misses the token's `kid` triggers exactly one forced re-fetch (to tolerate legitimate key rotation) before failing closed.
- The resulting role always comes from the role mappings below, evaluated fresh on every sign-in — an identity whose claims match no mapping is rejected, it is never given a default role.
- A successful sign-in creates or updates a local administrator record by email (`admin_auth.provision_sso_administrator`), including taking over a pre-existing *local-password* administrator account with a matching email. `enterprise_identity.save_provider` therefore fails closed on email-domain scope: configuring a provider requires either a non-empty `allowed_domains` list or an explicit `allow_any_domain=true`, so an operator cannot accidentally leave a provider unscoped and let any email it vouches for take over an existing administrator's role.
- No ID token, access token, authorization code, client secret, state, nonce, or PKCE verifier is ever written to the evidence log or included in an error message.

Role mappings translate explicit provider claims into GreyGuard roles. Workload identities use certificate SHA-256 thumbprints, bounded scopes, expiry, and status without persisting certificate material. A workload identity may optionally be bound to an already-registered agent (`agent_name`), which is what lets that certificate authenticate *as* that agent — see `docs/agent-certificate-authentication.md` for the full nginx/mTLS boundary, header contract, and revocation behavior; this is a second, additive way for an agent to prove the identity it already has via `X-Agent-Name`/`X-Agent-Key`, not a separate identity system.

Temporary privilege elevation is time-bound, recorded, and requires approval by a different Platform Administrator. Break-glass activation is limited to specifically designated active administrators with MFA, requires a detailed reason, expires automatically, and produces an immutable security event, and remains available independently of SSO so an identity-provider outage never locks out a designated administrator.

Production deployments must terminate TLS at a trusted boundary, set `GREYGUARD_SSO_REDIRECT_URI` to the public HTTPS callback URL registered with each provider, retain identity events according to organizational policy, and keep IdP secrets in the existing secrets manager rather than this configuration store (none are needed for the PKCE flow itself).
