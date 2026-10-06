# Pre-final hardening

This gate adds evidence beyond ordinary unit tests before GreyGuard's final
documentation and acceptance phases.

## Migration rehearsal

Run the SQLite-to-PostgreSQL migrator only against an initialized, empty target
owned by a dedicated migration operator. The command requires `--confirm`, makes
and hashes an offline source backup, verifies table content with order-independent
digests, repairs PostgreSQL identity sequences, and confirms the SQLite source was
not modified.

```powershell
python scripts\migrate_sqlite_to_postgresql.py `
  --source backend\data\greyguard.db `
  --database-url $env:GREYGUARD_DATABASE_URL `
  --confirm
```

Keep both files from `artifacts/` with the change record. Rollback means stopping
the PostgreSQL deployment, restoring the verified SQLite backup, restoring the
previous configuration, and validating `/health` before reopening traffic.

## Performance baseline

Start the API, then capture a repeatable health-endpoint concurrency baseline:

```powershell
python scripts\benchmark_greyguard.py --requests 100 --concurrency 10
```

The generated JSON records throughput, success rate, status counts, and latency.
Results describe that machine and configuration only; they are not a universal
capacity claim. Production sizing requires representative data, authenticated
workflows, sustained tests, resource monitoring, and an agreed service objective.

