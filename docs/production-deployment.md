# Production deployment and database operations

Copy `.env.production.example` to `.env.production`, replace every example credential and hostname, and keep that file outside version control. Validate the Compose model with `docker compose -f docker-compose.production.yml config`, then build with `docker compose -f docker-compose.production.yml build`.

The frontend binds only to loopback. Place a TLS-terminating reverse proxy or managed load balancer in front of port 8080. The backend is reachable only through the internal container network. Persistent SQLite state uses the `greyguard-data` volume.

Start with `docker compose -f docker-compose.production.yml up -d`. Inspect health using `docker compose -f docker-compose.production.yml ps` and application logs using `docker compose -f docker-compose.production.yml logs --tail 200`.

Create a verified backup before upgrades:

`python -m backend.app.database_ops backup backups/greyguard-YYYYMMDD.db`

Verify it with `python -m backend.app.database_ops verify backups/greyguard-YYYYMMDD.db`. Restore only while GreyGuard is stopped: `python -m backend.app.database_ops restore backups/greyguard-YYYYMMDD.db --confirm`. Keep backups encrypted, access-controlled, and outside the live data volume.

Upgrade procedure: create and verify a backup, record the current Git commit and container image digests, build the new images, apply the release, verify health and login, then retain the backup until the release has passed its observation window. Roll back by stopping services, restoring the verified backup, deploying the recorded image versions, and verifying health again.
