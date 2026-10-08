# PostgreSQL persistence migration

GreyGuard now routes application persistence through `db_compat`. SQLite remains the default for development and existing installations. Setting `GREYGUARD_DATABASE_URL` to a PostgreSQL URL selects psycopg and translates the narrowly defined legacy SQL compatibility surface: parameter markers, serial identifiers, binary columns, idempotent inserts, the correlation upsert, table discovery, and column discovery.

## Baseline schema

`backend/migrations/versions/20261008_02_baseline_schema.py` creates every one of GreyGuard's 80 tables against a PostgreSQL target. It was captured, not hand-written: generated from `pg_dump --schema-only` against a database created by actually running every `initialize_*()` function in `backend/app` (not just the ones the real startup lifespan calls directly - `admin_auth.initialize_admin_auth()` is lazy-only, invoked on first admin operation rather than at startup, and was missed on the first capture attempt until a direct cross-check of every `CREATE TABLE IF NOT EXISTS` in the codebase against the capture caught it: 80 defined, 80 captured, zero missing either direction). Verified by re-running `alembic upgrade head` against an empty database and diffing the resulting schema against the original capture (zero unexpected differences) and by running `scripts/verify_postgresql_parity.py` against a database created purely by the migration, with no imperative initialization ever run (20 passed). Rebaseline the same way - capture, don't hand-transcribe - if the schema changes enough to need a new baseline.

## Mandatory activation sequence

1. Create and verify an encrypted SQLite backup.
2. Run the full SQLite backend suite.
3. Run `python -m backend.app.migration_readiness`; it must report ready.
4. Run `docker compose -f deployment/postgresql-parity.yml up --build --abort-on-container-exit --exit-code-from parity`.
5. Initialize the approved target with `alembic upgrade head` (not `scripts/initialize_database_backend.py` alone - that only creates tables the startup lifespan eagerly initializes, missing `admin_auth`'s lazily-created tables; the migration creates all 80).
6. Run `python scripts/migrate_sqlite_to_postgresql.py --source PATH_TO_DB --confirm` in the controlled migration environment.
7. Retain the generated per-table row-count and source-checksum evidence.
8. Run application smoke, authentication, policy, isolation, audit-integrity, backup, and rollback checks. Backup/restore checks against the PostgreSQL target use `backend/app/postgres_backup_ops.py` (see `docs/production-deployment.md`), not the SQLite-only `database_ops.py`.
9. Change production only after documented approval.

Rollback means stopping writes, pointing GreyGuard back to the preserved SQLite database and known-good release, verifying readiness and authentication, and investigating every write accepted by PostgreSQL after cutover. Do not attempt automatic bidirectional synchronization.
