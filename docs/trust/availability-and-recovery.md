# Availability and recovery

- **No SLA.** GreyGuard publishes no uptime commitment and no committed recovery point (RPO) or recovery time (RTO) objectives. They wait for measured operation [TC-AV-1].
- **Single host, not highly available.** The shipped deployment runs on one host. A crashed worker process is replaced and containers restart, but losing the host or the database stops the service. Running several backend replicas is safe, because all shared state, including agent suspensions, is in the database. Multi-host high availability is documented as remaining work [TC-AV-2].
- **Failure modes fail closed.** If the database is unavailable, no action is allowed. A gateway cut off from the control plane enforces its last bundle until it expires, then denies everything. Deliveries that fail are retried, then dead-lettered, with every attempt recorded [TC-AV-3].
- **Backups.** Production PostgreSQL backups are made and verified with `postgres_backup_ops`. Backups cover the whole install; restoring a single organization is not supported, and an organization's export is its own copy [TC-AV-4]. See [Data protection](data-protection.md) for backup encryption.
- **Disaster-recovery drill.** The scripted drill restores an encrypted backup to temporary storage and verifies it without touching the live database. **It exercises the SQLite backup path.** A PostgreSQL disaster-recovery drill is not yet recorded [TC-AV-5].
- **Status page.** A public status page (`/status`) shows component health and the support severity definitions [TC-AV-6].
- **Data placement.** An install keeps all GreyGuard-held data in the region where it runs, with no cross-region replication. Choosing a region per organization within one install is not built; the Dedicated model gives a region choice by running a separate install [TC-AV-7].
- **Measured load.** The load measurements published in the reliability document are observations of one small machine, not capacity commitments [TC-AV-8].
