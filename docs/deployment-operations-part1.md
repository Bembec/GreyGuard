# Deployment and operations — database foundation

This stage adds distinct development and test configuration examples, authenticated encrypted backups, PostgreSQL migration tooling, and an Alembic rehearsal environment.

## Encrypted backups

`GREYGUARD_BACKUP_KEY` must be a URL-safe base64 encoding of exactly 32 random bytes. Store it in an external secret manager, separately from backup files. Create an AES-256-GCM backup with `python -m backend.app.encrypted_backups create backend/data/greyguard.db backups/greyguard.ggb`. Restore only during an approved maintenance window using `python -m backend.app.encrypted_backups restore backups/greyguard.ggb backend/data/greyguard.db --confirm`.

The authenticated metadata contains the plaintext checksum, size, source name, and creation time. A wrong key or modified ciphertext fails restoration before database replacement. Restoration also runs SQLite integrity verification.

## PostgreSQL migration boundary

GreyGuard currently contains direct SQLite calls. Run `python -m backend.app.migration_readiness --output artifacts/postgresql-readiness.json` to create the conversion inventory. PostgreSQL must not replace the production datastore until this report returns `ready_for_postgresql: true`, data migration is rehearsed, parity tests pass, rollback is tested, and the change is approved.

`deployment/postgresql-rehearsal.yml` is intentionally isolated from the production Compose file. It creates a PostgreSQL rehearsal database and applies the Alembic migration-control baseline. It does not claim that the existing application persistence code has already been converted.

Part 2 will convert and verify the application persistence boundary, then add the remaining operational release, monitoring, TLS, disaster-recovery, and signed-artifact controls.
