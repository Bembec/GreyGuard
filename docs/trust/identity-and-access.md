# Identity and access

## Administrators

- **Individual accounts only.** Each administrator signs in with a local password or through enterprise single sign-on (OIDC Authorization Code with PKCE, for Microsoft Entra ID, Okta, Auth0 and compatible providers). ID tokens are verified against the provider's own keys, only RS256 and ES256 are accepted, and the redirect URI is fixed by configuration rather than taken from the browser [TC-IAM-1].
- **Sessions.** Access tokens last 15 minutes. Refresh tokens last seven days and rotate on every use; reusing an old refresh token revokes its whole family and every session of that administrator [TC-IAM-2].
- **MFA.** TOTP MFA is available to every account, and an account with MFA enabled cannot sign in without a valid code. MFA is **not enforced install-wide**; the organization readiness checklist reports whether every member has enabled it [TC-IAM-3].
- **Roles.** Three roles: Platform Administrator, Security Analyst and Auditor (read-only) [TC-IAM-4].
- **Elevation and break-glass.** Temporary privilege elevation needs approval from a different Platform Administrator and expires. Break-glass access is limited to designated administrators with MFA, needs a reason, expires and is recorded as a security event [TC-IAM-5].

## Agents

- An agent authenticates with its name and key. The key is stored only as a hash [TC-DP-6].
- **Optional mutual TLS.** An agent can instead present a client certificate verified by the reverse proxy. This is off by default, needs an explicit opt-in on the backend, and stores only the certificate's thumbprint [TC-IAM-6].
- **Failure messages.** Failed attempts are recorded as evidence with their reason. The caller always receives the same generic message [TC-IAM-6].

## Tenant isolation

- **Every query is checked.** Every query against an organization-scoped table must carry an `org_id` predicate; the tenant guard rejects any query that lacks one [TC-IAM-7].
- **Acceptance suite.** An acceptance suite built from the application's own route table and API schema sends every route an attacker organization's credentials and the victim organizations' identifiers. Any route that leaks data fails it, and a route added later is covered automatically [TC-IAM-8].
