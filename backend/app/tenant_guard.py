"""Structural safety net against silent cross-tenant data leaks.

GreyGuard has no shared data-access layer: every backend module opens its own connection and
writes its own raw SQL (see db_compat.py). Tenant isolation (P2) therefore cannot be enforced in
one chokepoint - it means adding an `org_id` column to every per-resource table and an
`org_id = ?` predicate to every query against it, by hand, across the whole codebase. A single
missed predicate among hundreds of call sites would be a silent cross-tenant data leak in a
security product.

This module is the safety net, built and proven in P2.1 while both registries below are still
near-empty, so the mechanism is trustworthy before P2.2's real per-table sweep depends on it.
`db_compat.connect()` routes every statement through `check_statement()` on both the SQLite and
PostgreSQL paths - enabled unconditionally, production included, because a raised
`TenantScopingError` is categorically preferable to a silent cross-tenant read.
"""
from __future__ import annotations

import re

# Tables that carry an org_id column and must be scoped by it in every query. Grown one entry
# per table in the same commit as that table's P2.2 migration, so the guard is never aware of a
# column before it exists and never silently skips one after.
#
# P2.2 batch 1 (simulation_runs, capability_removals/_steps, universal_capability_controls,
# universal_control_events): simple ADD COLUMN for most of these, except
# universal_capability_controls, whose primary key was `capability` alone (five fixed named
# rows) - adding a column without reshaping the key would let two orgs collide on the same
# capability name, so that one table was rebuilt with a composite (capability, org_id) key
# instead (see universal_controls.py's initialize_universal_controls()).
#
# P2.2 batch 2 (adapter_configs, adapter_events): same composite-key reshape for
# adapter_configs, whose primary key was `adapter_id` alone (seven fixed named rows) - the same
# shape of fix as universal_capability_controls, for the same reason (see
# adapter_control.py's initialize_adapter_control()). adapter_events needed only a plain ADD
# COLUMN. abuse_protection's three tables were also considered this batch and reclassified as
# GLOBAL_TABLES instead - see the comment there for why.
#
# P2.2 batch 3 (browser_connectors, defensive_response_plans, endpoint_collectors,
# endpoint_telemetry_events): all four use UUID-generated primary keys, not fixed named rows, so
# a plain ADD COLUMN was sufficient - no composite-key reshape needed. endpoint_telemetry_events
# has no live call site writing to it anywhere in the codebase today (confirmed by search); the
# column was still added for schema completeness and to let it leave PENDING_TENANT_SCOPING
# honestly rather than leaving a quietly-abandoned table in the "undecided" bucket.
#
# P2.2 batch 4 (service_accounts, service_account_keys, service_account_events):
# service_accounts had a different fixed-shape problem than batches 1-2's - not a fixed set of
# named rows, but a plain `UNIQUE(name)` constraint (case-insensitive, COLLATE NOCASE/citext)
# that would let two orgs collide on the same human-chosen account name. Reshaped to
# `UNIQUE(name, org_id)` via the same SQLite rename/rebuild dance used for a composite primary
# key, since SQLite can't alter a UNIQUE constraint in place either. The bearer-key verification
# route (`authenticate_service_key`, used by `POST /service-accounts/verify`) deliberately takes
# no org_id parameter: it looks a key up by its globally-unique random `key_prefix` before any
# org is knowable, then reads org_id back off the resolved row - the same "identify first, scope
# second" shape as admin_auth's own session-token lookups.
#
# P2.2 batch 5 (threat_register, threat_register_history): threat_register has the same
# fixed-row-set shape as universal_capability_controls/adapter_configs in batches 1-2 - 30 fixed
# threat_id rows seeded from the THREATS tuple, keyed by threat_id alone - so it got the same
# composite (threat_id, org_id) primary-key reshape. threat_register_history needed only a plain
# ADD COLUMN (AUTOINCREMENT surrogate key, no fixed-row problem).
#
# P2.2 batch 6 (isolation_config, isolation_executions): isolation_config is the first of the
# seven singleton `CHECK(config_id=1)` tables flagged in PENDING_TENANT_SCOPING's comments to
# actually land - reshaped to a composite (config_id, org_id) key, the same treatment as the
# fixed-row-set tables above. isolation_executions needed only a plain ADD COLUMN. A real
# architectural finding this batch: `emergency_terminate()` originally killed every RUNNING
# sandbox container on the host regardless of org - scoped it by org_id so one org's emergency
# stop can never terminate another org's container (that would have been a cross-tenant denial
# of service, not just a tenancy gap), including the in-memory `_running` fallback registry,
# which now carries org_id alongside each entry.
#
# P2.2 batch 7 (isolation_operations_config, isolated_workspaces, quarantined_artifacts):
# isolation_operations_config is the second singleton to land - same composite-key reshape.
# isolated_workspaces had its own uniqueness problem, like service_accounts in batch 4:
# `agent_name` was globally UNIQUE, which would let two orgs collide on an agent of the same
# name - reshaped to UNIQUE(agent_name, org_id). This one had a filesystem consequence too, not
# just a database one: workspace paths were `workspace_root/<agent_name>`, so two orgs with the
# same agent name would have shared the same directory on disk. Fixed by nesting workspace paths
# under an org_id subdirectory (`workspace_root/<org_id>/<agent_name>`) so filesystem isolation
# matches database isolation. quarantined_artifacts needed only a plain ADD COLUMN - its
# artifact_id is a UUID, so no on-disk collision risk (quarantine_root/<artifact_id>.bin stays
# flat and collision-free regardless of org).
#
# P2.2 batch 8 (simulation_config): the third singleton to land, same composite-key reshape -
# and the one explicitly deferred back in batch 1 when simulation_runs was scoped (see that
# commit's note: "set_enabled() unchanged (operates on the still-global simulation_config
# singleton, deliberately deferred)"). update_simulation_lab() in api.py was the one remaining
# call site anywhere in the codebase that still called a simulations function without an
# org_id - fixed in the same commit as this table's migration.
ORG_SCOPED_TABLES: frozenset[str] = frozenset({
    "simulation_runs",
    "capability_removals",
    "capability_removal_steps",
    "universal_capability_controls",
    "universal_control_events",
    "adapter_configs",
    "adapter_events",
    "browser_connectors",
    "defensive_response_plans",
    "endpoint_collectors",
    "endpoint_telemetry_events",
    "service_accounts",
    "service_account_keys",
    "service_account_events",
    "threat_register",
    "threat_register_history",
    "isolation_config",
    "isolation_executions",
    "isolation_operations_config",
    "isolated_workspaces",
    "quarantined_artifacts",
    "simulation_config",
    # P2.2 batch 11: secret_references had the same uniqueness problem as service_accounts
    # (batch 4) and isolated_workspaces (batch 7) - `name` was globally UNIQUE
    # (case-insensitive), which would let two orgs collide on the same human-chosen secret
    # name. Reshaped to UNIQUE(name, org_id). emergency_revoke_all() originally revoked every
    # ACTIVE secret on the install for a given provider regardless of org - scoped it by org_id
    # so one org's emergency revocation can never revoke another org's secret (the same
    # cross-tenant availability risk already fixed for emergency_terminate() in batch 6).
    # secret_events needed only a plain ADD COLUMN.
    "secret_references",
    "secret_events",
    # P2.2 batch 12: report_schedules and incident_postmortems both use UUID-generated primary
    # keys, so a plain ADD COLUMN sufficed - no composite-key or uniqueness reshape this batch.
    # run_due_schedules() (report_governance.py) is a background worker with no HTTP/admin
    # context, the same shape as the outbound-delivery-style workers - its claim query is
    # deliberately cross-org (one process services every org's due schedules in a single pass,
    # documented with an explanatory SQL comment so the guard sees why no org_id predicate
    # belongs there), but every subsequent read/update of a claimed row is scoped by that row's
    # own org_id, and the generated report itself is built with that org's org_id.
    "report_schedules",
    "incident_postmortems",
})

# Tables that are deliberately never org-scoped - identity/account tables that represent a
# person or the control-plane install itself, migration bookkeeping, and the org tables
# themselves (an org row does not belong to an org). Every table in the schema must appear in
# exactly one of these two sets; a table in neither fails the CI check in
# tests/test_tenant_guard.py::test_every_schema_table_is_in_exactly_one_registry.
GLOBAL_TABLES: frozenset[str] = frozenset({
    "administrators",
    "administrator_sessions",
    "administrator_refresh_tokens",
    "administrator_security_events",
    "organizations",
    "org_memberships",
    "org_invitations",
    "greyguard_migration_control",
    # Shared request-throttling infrastructure (abuse_protection.py), reclassified out of
    # PENDING_TENANT_SCOPING during P2.2 batch 2 after tracing its real call sites: it is read
    # and written from enforce_administrator_rbac(), a global HTTP middleware that runs on
    # EVERY request - including /auth/login itself, before any session or org is resolved.
    # The identifier it throttles by is an IP address or agent name, never an org. Scoping
    # these by org_id would be a real security regression. not a tenancy gap: an attacker
    # hammering the login endpoint could bypass the limit entirely by spreading requests
    # across different org contexts, and there is no org to attribute an anonymous pre-auth
    # attacker to in the first place. This is shared install-wide security infrastructure, the
    # same category as the identity tables above, not per-resource tenant data.
    "rate_limit_policies",
    "rate_limit_counters",
    "abuse_events",
    # Same shape as abuse_protection's tables above, reclassified during P2.2 batch 9 after
    # tracing its real call sites: observe_request() (api.py) is a global pre-auth HTTP
    # middleware wrapping EVERY request - including /auth/login and every unauthenticated
    # route - before any session or org is resolved. observability_spans/_correlations record
    # method/path/status/duration for that HTTP layer, not a tenant's resource data, and the
    # overwhelming majority of spans (every unauthenticated request, every request whose auth
    # fails) could never be attributed to an org in the first place. observability_config's
    # tracing/metrics/retention toggles are an install-wide operational switch, the same
    # category as abuse_protection's throttling policy, not a per-org setting - a platform
    # operator debugging latency needs to see traces across every org, not one filtered to
    # whichever org happens to be viewing /observability/traces. No schema change: this was a
    # registry reclassification only, the same as abuse_protection's in batch 2.
    "observability_config",
    "observability_spans",
    "observability_correlations",
    # P2.2 batch 10: traced both tables flagged in PENDING_TENANT_SCOPING's comments for the
    # same scrutiny abuse_protection/observability got. authentication_events
    # (database.py/main.py/agent_certificate_auth.py) logs agent identity-verification
    # attempts - claimed vs. authenticated agent name, outcome, reason - fired at the agent
    # request-ingress layer before any administrator session exists, and agents are not
    # tenant-scoped at all yet (agent_identities is still in PENDING_TENANT_SCOPING below); it
    # would be premature and architecturally inconsistent to scope this table to an org concept
    # that doesn't apply to agents yet. oidc_login_attempts (enterprise_sso.py) is single-use
    # OAuth2 state/nonce/PKCE-verifier data keyed by a random `state` token, created and looked
    # up entirely before the administrator it belongs to has authenticated - the whole reason
    # the table exists is that no session (and therefore no org) is resolvable yet during an
    # SSO redirect round-trip. Both are pre-auth security/handshake state, not tenant resource
    # data - the same category as administrator_sessions and abuse_protection's tables above.
    "authentication_events",
    "oidc_login_attempts",
})

# Tables that exist today but have not yet had a tenant-scoping decision made - not a silent
# gap, an explicit, honest "not yet" so the coverage check can tell the difference between
# "deliberately global" and "nobody has looked at this table yet." Every table here is expected
# to move into ORG_SCOPED_TABLES as its own P2.2 batch lands (removed from this set in the same
# commit, mirroring how entries are added to ORG_SCOPED_TABLES) - except that this is an
# expectation, not a guarantee: abuse_protection's three tables started in this set too, until
# tracing their actual call sites in P2.2 batch 2 showed they are genuinely global
# infrastructure, not per-resource data (see GLOBAL_TABLES above). Two more tables below are
# flagged for the same scrutiny when their batch comes up, for the same reason (pre-auth,
# request-level security tracking with no org to attribute to yet).
#
# The seven marked (*) are singleton config tables (one global row today, PK a CHECK(col=1)
# constraint) that need the same composite-key reshape universal_capability_controls and
# adapter_configs got, not a plain ADD COLUMN - flagged now so whichever batch tackles them
# doesn't rediscover that the hard way.
PENDING_TENANT_SCOPING: frozenset[str] = frozenset({
    "agent_credential_events",
    "agent_identities", "alert_notes", "approval_events", "audit_events",
    "audit_integrity_chain", "audit_integrity_checks", "audit_legal_holds",
    "audit_retention_config",  # *
    "break_glass_activations",
    "callback_evidence", "compliance_reports",
    "enterprise_identity_events",
    "execution_events", "expiring_approval_links", "export_destinations", "export_queue",
    "external_incident_records", "identity_providers", "identity_role_mappings",
    "incident_destinations",
    "notification_deliveries", "notification_destinations", "notification_retention_events",
    "notification_retention_policy",  # *
    "notification_retention_tombstones", "notification_templates",
    "outbound_allowed_private_hosts", "outbound_delivery_evidence", "policy_adapters",
    "policy_change_events",
    "policy_emergency_controls",  # *
    "policy_emergency_events", "policy_integration_events", "policy_rollouts",
    "policy_test_cases", "policy_versions", "privilege_elevations",
    "security_alerts", "security_notifications",
    "tool_requests", "workload_identities",
})

_STATEMENT_TABLE = re.compile(
    r"\b(?:FROM|UPDATE|INTO|TABLE)\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"'`]?(\w+)[\"'`]?",
    re.IGNORECASE,
)

# Pure schema DDL that restructures a table rather than reading/writing its rows - never
# scoped by org_id by nature (a RENAME or DROP has no column list to mention org_id in at
# all), so these are exempt rather than false-positives waiting to happen. CREATE TABLE is
# deliberately NOT here: it stays checked, because a CREATE TABLE for an org-scoped table is
# expected to define an org_id column and so naturally mentions the literal token - exempting
# it too would silently let a table be (re)created without that column and only surface the
# mistake later, on the first real query against it.
_SCHEMA_RESTRUCTURING_STATEMENT = re.compile(
    r"^\s*ALTER\s+TABLE\s+\S+\s+RENAME\b|^\s*DROP\s+TABLE\b",
    re.IGNORECASE,
)


class TenantScopingError(RuntimeError):
    """Raised when a query against an org-scoped table has no org_id predicate."""


def extract_table_name(sql: str) -> str | None:
    """Best-effort table-name extraction matching this codebase's own hand-written SQL shape
    (one simple statement per `.execute()` call, never a multi-table join written as a single
    scoped target - joins read from multiple tables but only one is ever the thing being
    filtered for tenancy, and that one is always the first FROM/UPDATE/INTO/TABLE token)."""
    match = _STATEMENT_TABLE.search(sql)
    return match.group(1) if match else None


def check_statement(sql: str) -> None:
    if _SCHEMA_RESTRUCTURING_STATEMENT.search(sql):
        return
    table = extract_table_name(sql)
    if table is None or table not in ORG_SCOPED_TABLES:
        return
    if re.search(r"\borg_id\b", sql, re.IGNORECASE) is None:
        raise TenantScopingError(
            f"Query against org-scoped table '{table}' has no org_id predicate: {sql!r}"
        )
