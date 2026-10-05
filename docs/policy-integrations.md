# Policy Integrations and Staged Rollout

GreyGuard supports controlled integration records for Open Policy Agent, Cedar and Cerbos. All adapters are disabled by default. Enabling an adapter requires a named owner, purpose and HTTPS endpoint. GreyGuard does not store adapter credentials in these records or grant automatic network authority.

## Policy-as-code bundles

Policy versions can be exported as canonical JSON bundles protected with HMAC-SHA256. Configure `GREYGUARD_POLICY_SIGNING_KEY` with at least 32 characters through the production secret-management mechanism. Never commit the signing key to source control.

Bundle verification must succeed before a policy artifact is trusted by deployment automation. Any change to the signed document causes verification to fail.

## Staged rollout

A reviewed policy may be introduced to an explicit agent allowlist or a deterministic percentage of registered agents. Only one rollout can be active at a time. Operators may pause, resume, complete or cancel it. Agent selection uses a stable hash, preventing an agent from switching randomly between policy versions.

Recommended workflow:

1. Simulate the draft and run its stored tests.
2. Resolve conflict findings.
3. Submit the draft for independent approval.
4. Start at zero percent with a small named allowlist.
5. Monitor decisions, risk and execution evidence.
6. Increase the percentage gradually.
7. Pause immediately if unexpected denials, approvals or risk changes appear.
8. Complete the rollout only after evidence review.

