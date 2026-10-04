# GreyGuard production operations runbook

## Health and recovery

`/health/live` proves the process can respond. `/health/ready` verifies required dependencies and returns HTTP 503 when traffic should not be routed to the instance. Container health, application readiness, logs, request correlation, and resource consumption must be checked after every deployment.

Before an upgrade, create and verify a database backup, record the Git tag and image digests, review dependency alerts, and confirm an authorized rollback owner. Deploy only from a protected release tag after CI, CodeQL, dependency audit, frontend build, backend tests, and container build succeed.

If readiness fails, stop routing new traffic, capture correlated logs, preserve evidence, verify storage availability and database integrity, and restore the last verified backup only after the incident owner approves. Roll back to recorded image digests rather than rebuilding an old source tree.

## Controlled release checklist

- Change reviewed and approved by a separate maintainer.
- Backend, frontend, security and container jobs successful.
- Database backup verified and recovery location documented.
- Configuration changes reviewed without exposing secret values.
- Release tag and immutable image digests recorded.
- Readiness, authentication, policy enforcement and audit evidence verified after deployment.
- Rollback window monitored and closure recorded.

## Graceful operations

Docker sends SIGTERM before its stop timeout. Uvicorn stops accepting new work and drains active requests before exit. Operators should use `docker compose stop -t 30` before backups or maintenance and avoid terminating the process or copying a live SQLite file directly.
