"""Proves the tenant_guard mechanism itself works, before P2.2's real per-table sweep depends
on it (see tenant_guard.py's module docstring). ORG_SCOPED_TABLES is empty in production right
now - these tests exercise the guard against a synthetic scoped table, monkeypatching the
registry rather than waiting for a real table to be migrated."""
import pytest
from backend.app import db_compat, organizations, tenant_guard


def test_extract_table_name_handles_the_four_statement_shapes_this_codebase_uses():
    assert tenant_guard.extract_table_name("SELECT * FROM widgets WHERE id = ?") == "widgets"
    assert tenant_guard.extract_table_name("UPDATE widgets SET name = ? WHERE id = ?") == "widgets"
    assert tenant_guard.extract_table_name("INSERT INTO widgets (id) VALUES (?)") == "widgets"
    assert tenant_guard.extract_table_name("DELETE FROM widgets WHERE id = ?") == "widgets"
    assert tenant_guard.extract_table_name("CREATE TABLE IF NOT EXISTS widgets (id TEXT)") == "widgets"


def test_a_query_against_an_unscoped_table_is_never_flagged():
    tenant_guard.check_statement("SELECT * FROM administrators WHERE admin_id = ?")


def test_a_query_missing_org_id_against_a_scoped_table_raises(monkeypatch):
    monkeypatch.setattr(tenant_guard, "ORG_SCOPED_TABLES", frozenset({"widgets"}))
    with pytest.raises(tenant_guard.TenantScopingError):
        tenant_guard.check_statement("SELECT * FROM widgets WHERE id = ?")


def test_a_query_including_org_id_against_a_scoped_table_passes(monkeypatch):
    monkeypatch.setattr(tenant_guard, "ORG_SCOPED_TABLES", frozenset({"widgets"}))
    tenant_guard.check_statement("SELECT * FROM widgets WHERE id = ? AND org_id = ?")


def test_every_schema_table_is_in_exactly_one_registry(tmp_path, monkeypatch):
    """The CI-check half of the safety net: a table that is in neither ORG_SCOPED_TABLES nor
    GLOBAL_TABLES must fail loudly, not be silently unprotected. This runs the real
    organizations.initialize_organizations() against a throwaway database and confirms every
    table it creates is accounted for."""
    from backend.app import admin_auth
    path = tmp_path / "coverage.db"
    monkeypatch.setattr(admin_auth, "database_path", path)
    monkeypatch.setattr(organizations, "database_path", path)
    admin_auth.initialize_admin_auth()
    organizations.initialize_organizations()
    with db_compat.connect(path) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}
    accounted_for = tenant_guard.ORG_SCOPED_TABLES | tenant_guard.GLOBAL_TABLES
    missing = tables - accounted_for
    assert missing == set(), f"Tables with no tenant-scoping decision recorded: {missing}"


def test_two_org_contamination_fixture_proves_scoped_queries_never_cross_orgs(tmp_path, monkeypatch):
    """The minimal version of P2.2's capstone fixture, proven now against a synthetic table so
    the pattern is trusted before 60 real tables depend on it: provision two orgs, seed one row
    each into a scoped table, and confirm a correctly org_id-scoped query for org A never
    returns org B's row (and vice versa)."""
    monkeypatch.setattr(tenant_guard, "ORG_SCOPED_TABLES", frozenset({"widgets"}))
    path = tmp_path / "contamination.db"
    with db_compat.connect(path) as connection:
        connection.execute("CREATE TABLE widgets (id TEXT, org_id TEXT, secret TEXT)")
        # Named columns, matching this codebase's own INSERT convention everywhere (see
        # organizations.py/admin_auth.py) - a bare positional "VALUES (...)" never mentions
        # org_id in the SQL text at all, which the guard correctly treats as unscoped.
        connection.execute("INSERT INTO widgets (id,org_id,secret) VALUES ('w1','org_a','org-a-secret')")
        connection.execute("INSERT INTO widgets (id,org_id,secret) VALUES ('w2','org_b','org-b-secret')")
        connection.row_factory = db_compat.Row
        org_a_rows = connection.execute("SELECT * FROM widgets WHERE org_id = ?", ("org_a",)).fetchall()
        org_b_rows = connection.execute("SELECT * FROM widgets WHERE org_id = ?", ("org_b",)).fetchall()
    assert [row["secret"] for row in org_a_rows] == ["org-a-secret"]
    assert [row["secret"] for row in org_b_rows] == ["org-b-secret"]


def test_the_guard_runs_through_the_real_connection_path_not_just_check_statement_directly(tmp_path, monkeypatch):
    """Confirms db_compat.connect() actually routes through the guard end-to-end, not just that
    check_statement() works in isolation."""
    monkeypatch.setattr(tenant_guard, "ORG_SCOPED_TABLES", frozenset({"widgets"}))
    path = tmp_path / "guarded.db"
    with db_compat.connect(path) as connection:
        connection.execute("CREATE TABLE widgets (id TEXT, org_id TEXT)")
        with pytest.raises(tenant_guard.TenantScopingError):
            connection.execute("SELECT * FROM widgets")
        connection.execute("SELECT * FROM widgets WHERE org_id = ?", ("org_default",))
