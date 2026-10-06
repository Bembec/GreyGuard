# PostgreSQL persistence migration

GreyGuard now routes application persistence through `db_compat`. SQLite remains the default for development and existing installations. Setting `GREYGUARD_DATABASE_URL` to a PostgreSQL URL selects psycopg and translates the narrowly defined legacy SQL compatibility surface: parameter markers, serial identifiers, binary columns, idempotent inserts, the correlation upsert, table discovery, and column discovery.

## Mandatory activation sequence

1. Create and verify an encrypted SQLite backup.
2. Run the full SQLite backend suite.
3. Run `python -m backend.app.migration_readiness`; it must report ready.
4. Run `docker compose -f deployment/postgresql-parity.yml up --build --abort-on-container-exit --exit-code-from parity`.
5. Initialize the approved target with `python scripts/initialize_database_backend.py` while the PostgreSQL URL is configured.
6. Run `python scripts/migrate_sqlite_to_postgresql.py --source PATH_TO_DB --confirm` in the controlled migration environment.
7. Retain the generated per-table row-count and source-checksum evidence.
8. Run application smoke, authentication, policy, isolation, audit-integrity, backup, and rollback checks.
9. Change production only after documented approval.

Rollback means stopping writes, pointing GreyGuard back to the preserved SQLite database and known-good release, verifying readiness and authentication, and investigating every write accepted by PostgreSQL after cutover. Do not attempt automatic bidirectional synchronization.
