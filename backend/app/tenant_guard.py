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

# Tables that carry an org_id column and must be scoped by it in every query. Empty until a
# table's P2.2 migration lands - grown one entry per table in the same commit as that migration,
# so the guard is never aware of a column before it exists and never silently skips one after.
ORG_SCOPED_TABLES: frozenset[str] = frozenset()

# Tables that are deliberately never org-scoped - identity/account tables that represent a
# person or the control-plane install itself, migration bookkeeping, and the org tables
# themselves (an org row does not belong to an org). Every table in the schema must appear in
# exactly one of these two sets; a table in neither fails the CI check in
# tests/test_tenant_guard_coverage.py.
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

_STATEMENT_TABLE = re.compile(
    r"\b(?:FROM|UPDATE|INTO|TABLE)\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"'`]?(\w+)[\"'`]?",
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
    table = extract_table_name(sql)
    if table is None or table not in ORG_SCOPED_TABLES:
        return
    if re.search(r"\borg_id\b", sql, re.IGNORECASE) is None:
        raise TenantScopingError(
            f"Query against org-scoped table '{table}' has no org_id predicate: {sql!r}"
        )
