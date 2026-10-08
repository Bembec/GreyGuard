# Production deployment and database operations

Copy `.env.production.example` to `.env.production`, replace every example credential and hostname, and keep that file outside version control. Validate the Compose model with `docker compose -f docker-compose.production.yml config`, then build with `docker compose -f docker-compose.production.yml build`.

The frontend binds only to loopback. Place a TLS-terminating reverse proxy or managed load balancer in front of port 8080. The backend is reachable only through the internal container network.

`docker-compose.production.yml` runs the backend against **PostgreSQL** (`GREYGUARD_DATABASE_URL` is constructed from `GREYGUARD_POSTGRES_PASSWORD`); PostgreSQL, not SQLite, is the database of record, and `db_compat.py` refuses to start with `GREYGUARD_ENV=production` unless a PostgreSQL URL is configured. The `greyguard-data` volume holds only isolated-workspace and quarantined-artifact files (`isolation_operations.py`) alongside an unused SQLite file - it is **not** a backup of the application's data and must not be treated as one. The database itself lives in the separate `greyguard-postgres` volume.

Start with `docker compose -f docker-compose.production.yml up -d`. Inspect health using `docker compose -f docker-compose.production.yml ps` and application logs using `docker compose -f docker-compose.production.yml logs --tail 200`.

Create a verified backup before upgrades, from a host with the PostgreSQL client tools installed (`pg_dump`/`pg_restore`) and `GREYGUARD_DATABASE_URL` set to the same value the backend container uses:

`python -m backend.app.postgres_backup_ops backup backups/greyguard-YYYYMMDD.pgcustom`

Verify it with `python -m backend.app.postgres_backup_ops verify backups/greyguard-YYYYMMDD.pgcustom`. Restore only while GreyGuard is stopped: `python -m backend.app.postgres_backup_ops restore backups/greyguard-YYYYMMDD.pgcustom --confirm`. Keep backups encrypted, access-controlled, and outside the live data volume. Separately back up the `greyguard-data` volume's quarantine/workspace files if that evidence must survive a restore too - the PostgreSQL dump does not include it.

`backend/app/database_ops.py` (SQLite backup/verify/restore) is unrelated to this deployment: it only applies to a non-production, non-Postgres setup, and `db_compat.py` will not let `GREYGUARD_ENV=production` start against SQLite at all. Do not use it against a `docker-compose.production.yml` deployment.

Upgrade procedure: create and verify a backup, record the current Git commit and container image digests, build the new images, apply the release, verify health and login, then retain the backup until the release has passed its observation window. Roll back by stopping services, restoring the verified backup, deploying the recorded image versions, and verifying health again.
