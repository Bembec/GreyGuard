# Audit integrity and retention

GreyGuard seals audit events into a SHA-256 chain. Each record binds the canonical source payload, source identity and previous chain hash. Verification detects source edits, missing records, reordered links and modified chain entries.

Retention defaults to 365 days and requires explicit confirmation before deletion. Active legal holds block retention deletion. Immutable mode is intentionally one-way through the application; disabling it requires a documented offline recovery procedure and independent authorization.

Integrity-chain and verification evidence remains separate from normal event deletion. Platform Administrator authorization is required for verification, retention changes, legal holds and controlled deletion. Legal-hold release is recorded rather than deleting the hold.

Operational checks should run verification after backup restoration, before compliance exports and on a schedule. A failed result must create an incident, freeze retention deletion and preserve the affected database for investigation.
