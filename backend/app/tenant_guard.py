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
ORG_SCOPED_TABLES: frozenset[str] = frozenset({
    "simulation_runs",
    "capability_removals",
    "capability_removal_steps",
    "universal_capability_controls",
    "universal_control_events",
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
})

# Tables that exist today but have not yet had a tenant-scoping decision made - not a silent
# gap, an explicit, honest "not yet" so the coverage check can tell the difference between
# "deliberately global" and "nobody has looked at this table yet." Every table here is a
# per-resource table that will eventually move into ORG_SCOPED_TABLES as its own P2.2 batch
# lands (removed from this set in the same commit, mirroring how entries are added to
# ORG_SCOPED_TABLES). The seven marked (*) are singleton config tables (one global row today,
# PK a CHECK(col=1) constraint) that need the same composite-key reshape
# universal_capability_controls just got, not a plain ADD COLUMN - flagged now so whichever
# batch tackles them doesn't rediscover that the hard way.
PENDING_TENANT_SCOPING: frozenset[str] = frozenset({
    "abuse_events", "adapter_configs", "adapter_events", "agent_credential_events",
    "agent_identities", "alert_notes", "approval_events", "audit_events",
    "audit_integrity_chain", "audit_integrity_checks", "audit_legal_holds",
    "audit_retention_config",  # *
    "authentication_events", "break_glass_activations", "browser_connectors",
    "callback_evidence", "compliance_reports", "defensive_response_plans",
    "endpoint_collectors", "endpoint_telemetry_events", "enterprise_identity_events",
    "execution_events", "expiring_approval_links", "export_destinations", "export_queue",
    "external_incident_records", "identity_providers", "identity_role_mappings",
    "incident_destinations", "incident_postmortems", "isolated_workspaces",
    "isolation_config",  # *
    "isolation_executions",
    "isolation_operations_config",  # *
    "notification_deliveries", "notification_destinations", "notification_retention_events",
    "notification_retention_policy",  # *
    "notification_retention_tombstones", "notification_templates",
    "observability_config",  # *
    "observability_correlations", "observability_spans", "oidc_login_attempts",
    "outbound_allowed_private_hosts", "outbound_delivery_evidence", "policy_adapters",
    "policy_change_events",
    "policy_emergency_controls",  # *
    "policy_emergency_events", "policy_integration_events", "policy_rollouts",
    "policy_test_cases", "policy_versions", "privilege_elevations", "quarantined_artifacts",
    "rate_limit_counters", "rate_limit_policies", "report_schedules", "secret_events",
    "secret_references", "security_alerts", "security_notifications",
    "service_account_events", "service_account_keys", "service_accounts",
    "simulation_config",  # *
    "threat_register", "threat_register_history", "tool_requests", "workload_identities",
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
