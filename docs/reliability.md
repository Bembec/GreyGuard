# Reliability: availability, failure modes, data placement and measured load

This page states what GreyGuard does today when parts of it fail, where data lives, and what load it has been measured to carry. It promises no SLA: the roadmap forbids one until measured operation supports it. A denied security decision is GreyGuard working, not an outage.

## High availability

**Today the shipped deployment (`docker-compose.production.yml`) is not highly available.** It runs:

- one backend container running **one** process, which the image enforces (`--workers 1`);
- one PostgreSQL container;
- one frontend container.

Containers restart on failure (`restart: unless-stopped`).

**The blocker for running more than one backend process.** Agent runtime state (risk score, blocked attempts, suspension) is held in process memory and saved to a file in the data directory. Two processes sharing that state diverge. With the image's former `--workers 2`, this was reproduced as an enforcement bypass:

- an agent suspended by one worker was still allowed by the other;
- the other worker's next save wrote the suspension back to `ACTIVE`.

Since P3, the image runs one worker, and a second server process on the same data directory refuses to start (`main.claim_runtime_state()`).

**The path to HA**, in order:

1. Move agent runtime state into the database, with atomic per-agent updates. This is required.
2. Run several backend replicas behind a load balancer. Everything else is already database-backed, and the delivery workers already claim work with leases, so several workers can run safely.
3. Use a managed or replicated PostgreSQL with failover, and point-in-time recovery for backups.

## Failure-mode matrix

| Failure | What happens | Safe? |
|---|---|---|
| PostgreSQL unavailable | Requests that need the database fail; agents get errors rather than decisions. `/health/ready` reports not ready, and the status page shows the database as a major outage. | Fails closed: no action is allowed without a decision. |
| Backend process crashes | The container restarts. In-flight requests are lost and agents retry. Agent runtime state is saved on each change, so the last saved state is reloaded. | Yes |
| Second backend process started on the same data directory | Refuses to start with an explicit error. | Yes (since P3) |
| Delivery worker stops or fails a tick | Queued SIEM, incident and notification deliveries wait in the database. Claimed items are released after their 120-second lease. The status page shows the delivery worker as degraded. | Evidence is kept; delivery is delayed. |
| A delivery destination is down | Retries with backoff, then a dead letter after the destination's maximum attempts. Every attempt is recorded as evidence. | Yes |
| Gateway loses the control plane | Enforces its last bundle until `valid_until`, then denies everything. | Fails closed within the offline allowance. |
| Distribution signing key missing | Gateway enrollment and bundles return `503`; the status page shows policy distribution as not configured. | Yes |
| Billing provider unreachable | No webhook means no state change. A past-due org keeps its grace deadline. | Yes |
| Self-hosted clock wound back | The licence lease is measured from the install's clock high-water mark, and rollback is reported. | Yes |
| Disk full or data directory lost | PostgreSQL deployments keep their data in the database volume. The data directory holds isolated workspaces, quarantine and runtime state. Restore from backup ([production-deployment.md](production-deployment.md)). | Recover from backup |

## Regional data placement

| Data | Where it lives |
|---|---|
| All org data: agents, requests, evidence, policies, integrations, billing references | The install's PostgreSQL, in the region the install runs in. There is no cross-region replication. |
| Backups | Wherever the operator stores `postgres_backup_ops.py` output. Keep them in the same region for regional commitments. |
| Workspace files and quarantine | The backend's data volume, in the same region. |
| Data sent to integrations | The destinations each org configures (SIEM, incident system, notifications). They may be in any region; that is the org's choice. |
| Billing | Opaque references only. The mock provider sends nothing anywhere. |
| Gateway bundles (hybrid) | The customer's network, at the customer's gateway. |

A single-region install keeps all GreyGuard-held data in that region. Multi-region tenancy (choosing a region per org within one install) is **not built**. The Dedicated model gives a region choice by running a separate install.

## Measured load

Measured with `scripts/benchmark_load.py` on 2026-10-15. The benchmark ran a real uvicorn server (one process) on a 4-vCPU development Codespace, with 16 concurrent clients over HTTP and rate limits lifted through the operator API. The raw results are in `artifacts/benchmarks/p3-sqlite.json` and `p3-postgresql.json`.

**These are observations of one small machine, not capacity commitments.** Every request in every run succeeded.

| Path | SQLite | PostgreSQL 17, no pool | PostgreSQL 17, pooled |
|---|---|---|---|
| `GET /health` | 84 req/s · p95 281 ms | 14 req/s · p95 1,239 ms | **93 req/s · p95 190 ms** |
| `GET /entitlements` (authenticated read) | 29 · p95 693 ms | 6.8 · p95 2,448 ms | **45 · p95 388 ms** |
| `POST /tool-requests` (agent hot path) | 12 · p95 1,777 ms | 5.0 · p95 3,777 ms | **16 · p95 1,395 ms** |
| `GET /gateways/bundle` (policy read plus Ed25519 signing) | 50 · p95 442 ms | 11 · p95 1,637 ms | **71 · p95 267 ms** |
| Export queue drain (real queue code, no-op transport) | 121 items/s | 11 items/s | **119 items/s** |
| Live-event streams held open (100 requested) | 100 connected | 39 connected | **100 connected** |

### What the numbers show

- **Without a pool, PostgreSQL was 4–11× slower than SQLite.** `db_compat` opened a new connection, with authentication, for every database call, and one request makes many. A small connection pool (`GREYGUARD_DB_POOL_SIZE`, default 10) took PostgreSQL to SQLite's level or better on every path, and every live stream connected (`artifacts/benchmarks/p3-postgresql-pooled.json`).
- **Per-request bookkeeping is still heavy.** Even pooled, a simple request does several database writes (rate-limit counters and observability), and the agent hot path writes its evidence. These figures are one process on 4 vCPUs.

### Follow-up work, in priority order

1. ~~A PostgreSQL connection pool~~. Done.
2. Database-backed agent runtime state, which is also the HA blocker above.
3. Cheaper per-request bookkeeping.
4. Re-measuring after each of these.

No capacity figure should be quoted to a customer until these are done and measured.
