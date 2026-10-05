# Capability removal and rollback

GreyGuard retires sensitive capabilities through a fail-closed, evidence-preserving workflow. Starting a removal disables the capability and activates its integration kill switch before any uninstall or data operation occurs.

## Ordered workflow

The control plane requires interface and configuration shutdown, credential revocation, worker and network termination, component removal, controlled data handling, evidence preservation, database and release rollback, residual-process verification, secret rotation, administrator notification, and post-removal testing. A step cannot be skipped and every completion requires evidence.

Emergency shutdown opens the same audited workflow for every registered high-risk capability. It freezes new use immediately but does not automatically delete application data or audit records. Destructive data handling remains an explicit, reviewed workflow step.

Only Platform Administrators can begin workflows, submit step evidence, or activate emergency shutdown. A workflow closes only after all fourteen controls have been verified.
