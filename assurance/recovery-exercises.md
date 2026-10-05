# Recovery exercise record

## Backup restoration

Create an encrypted or access-controlled backup, verify its checksum and SQLite integrity, restore into a separate temporary location, confirm expected evidence rows, and record duration and operator. Never overwrite the active database during an exercise.

## Kill switch

Activate global policy deny and execution isolation kill switches, verify new workspaces/jobs/actions fail closed, terminate an approved synthetic job, preserve evidence, then restore service through documented approval.

## Disaster recovery

Assume loss of the active application host. Restore configuration through the secret provider, restore the verified database backup, deploy signed images, validate health/readiness, authentication, policy integrity, audit-chain integrity, sandbox denial defaults, and notification delivery. Record recovery time, recovery point, gaps, and corrective actions.

Exercises must be performed in a test environment and must not delete production data or contact real external targets.
