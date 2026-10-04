# Policy Governance Operations

GreyGuard stores every enforcement policy as an immutable version. Analysts may create and test drafts, but a draft does not affect live enforcement until a different Platform Administrator approves it.

## Change workflow

1. Create or update a draft with a meaningful change summary.
2. Run policy simulation, stored test cases and conflict detection.
3. Submit the draft. Submission locks it against editing.
4. A different Platform Administrator approves or rejects it.
5. Approval archives the previous version and activates the approved version.
6. Rollback always creates a new auditable draft; it never silently rewrites history.

## Emergency controls

The Platform Administrator can activate a global deny policy or disable named agents, tools and integrations. Emergency changes are audited and fail closed. Use global deny only during active containment, preserve evidence, investigate the cause and document approval before re-enabling operations.

## Safety guarantees

- Simulation never executes tools or changes agent state.
- Unknown actions default to `BLOCK`.
- Policy test cases are repeatable and version-specific.
- High-risk `ALLOW` rules and blocked actions with zero risk are flagged for review.
- The policy creator cannot approve the same change.
- Emergency switches are enforced server-side, not only hidden in the interface.

