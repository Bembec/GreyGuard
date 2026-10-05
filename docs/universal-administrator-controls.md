# Universal administrator controls

GreyGuard Section 15 provides a shared fail-closed gate for Tier 2 and Tier 3 capabilities. Registered capabilities start disabled. Enablement requires a named owner, purpose, exact permission manifest, future expiry, rate and resource limits, and an auditable administrator identity.

The gate enforces agent and target allowlists, separate human approval, dry-run requirements, global and integration kill switches, per-agent disablement, automatic expiry, data minimization, sensitive-field redaction, activation/use evidence, and notification requirements. Missing or invalid configuration blocks the operation.

The simulation lab is wired through the universal gate before a scenario can run. Other high-impact integrations can adopt the same gate by calling the registered capability and exact permission before their controlled adapter executes.

Every capability exposes a removal plan: disable, activate its kill switch, revoke credentials, stop workers, remove network access, preserve evidence, restore the previous safe configuration, and rerun the disabled-means-disabled regression test.
