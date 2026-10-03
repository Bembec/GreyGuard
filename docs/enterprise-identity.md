# GreyGuard enterprise identity

GreyGuard supports standards-based OIDC provider metadata for Microsoft Entra ID, Okta, Auth0, and compatible identity providers. The control plane stores issuer metadata and client identifiers but deliberately does not store provider client secrets.

Role mappings translate explicit provider claims into GreyGuard roles. Workload identities use certificate SHA-256 thumbprints, bounded scopes, expiry, and status without persisting certificate material.

Temporary privilege elevation is time-bound, recorded, and requires approval by a different Platform Administrator. Break-glass activation is limited to specifically designated active administrators with MFA, requires a detailed reason, expires automatically, and produces an immutable security event.

Production deployments must terminate TLS at a trusted boundary, validate OIDC discovery and token signatures against the configured issuer, retain identity events according to organizational policy, and keep IdP secrets in the existing secrets manager rather than this configuration store.
