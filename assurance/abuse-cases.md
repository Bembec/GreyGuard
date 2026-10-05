# Abuse-case review

Required cases: stolen administrator session; compromised agent credential; cross-agent evidence request; scope escalation; forged approval; replayed execution; concurrent double execution; prompt injection requesting a dangerous tool; malicious tool output; traversal or symlink escape; unrestricted egress request; secret in a log/export; rate-limit exhaustion; audit manipulation; insider misuse; kill-switch bypass; poisoned dependency; and malicious webhook destination.

For each case record the precondition, attempted abuse, expected BLOCK or REFUSED outcome, risk and suspension behavior, alert, preserved evidence, recovery action, test reference, owner, and review date. Tests must use synthetic identities and targets only.
