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


def test_rename_and_drop_table_are_exempt_even_against_a_scoped_table(monkeypatch):
    """Caught for real during P2.2 batch 1: universal_controls.py's SQLite-side primary-key
    reshape does `ALTER TABLE x RENAME TO x_pre_org` then `DROP TABLE x_pre_org` - neither
    statement has a column list to mention org_id in, so both must be exempt rather than
    false-positives. CREATE TABLE deliberately stays checked (see the module docstring)."""
    monkeypatch.setattr(tenant_guard, "ORG_SCOPED_TABLES", frozenset({"widgets"}))
    tenant_guard.check_statement("ALTER TABLE widgets RENAME TO widgets_pre_org")
    tenant_guard.check_statement("DROP TABLE widgets_pre_org")
    with pytest.raises(tenant_guard.TenantScopingError):
        tenant_guard.check_statement("ALTER TABLE widgets ADD COLUMN extra TEXT")


def test_a_query_missing_org_id_against_a_scoped_table_raises(monkeypatch):
    monkeypatch.setattr(tenant_guard, "ORG_SCOPED_TABLES", frozenset({"widgets"}))
    with pytest.raises(tenant_guard.TenantScopingError):
        tenant_guard.check_statement("SELECT * FROM widgets WHERE id = ?")


def test_a_query_including_org_id_against_a_scoped_table_passes(monkeypatch):
    monkeypatch.setattr(tenant_guard, "ORG_SCOPED_TABLES", frozenset({"widgets"}))
    tenant_guard.check_statement("SELECT * FROM widgets WHERE id = ? AND org_id = ?")


def test_every_schema_table_has_an_explicit_tenant_scoping_status():
    """The CI-check half of the safety net: a table that is in none of ORG_SCOPED_TABLES,
    GLOBAL_TABLES or PENDING_TENANT_SCOPING must fail loudly, not be silently unprotected -
    and a table cannot claim two statuses at once.

    Checked against the migration files' own CREATE TABLE statements (the authoritative,
    reviewed source of "every table GreyGuard creates" - the same ground truth the baseline
    migration itself was captured against) rather than dynamically bringing up every one of the
    ~25 initialize_*() functions across backend/app, which would need monkeypatching each
    module's own database_path global individually (see db_compat.py survey notes) for no
    extra confidence - the migration files are what actually ships.

    PENDING_TENANT_SCOPING must shrink to empty by the end of P2.2 - this test does not enforce
    that (P2.2 isn't done), only that nothing has fallen through every net at once.
    """
    import re
    from pathlib import Path
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations" / "versions"
    tables: set[str] = set()
    for migration_file in migrations_dir.glob("*.py"):
        text = migration_file.read_text(encoding="utf-8")
        tables.update(re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?public\.(\w+)", text))
        tables.update(m.group(1) for m in re.finditer(r'op\.create_table\(\s*"(\w+)"', text))
    assert len(tables) > 50, f"Expected the full schema, only found {len(tables)} tables - check the regex against the migration files' actual format."
    scoped, global_, pending = tenant_guard.ORG_SCOPED_TABLES, tenant_guard.GLOBAL_TABLES, tenant_guard.PENDING_TENANT_SCOPING
    assert not (scoped & global_), f"Tables claimed as both org-scoped and global: {scoped & global_}"
    assert not (scoped & pending), f"Tables claimed as both org-scoped and pending: {scoped & pending}"
    assert not (global_ & pending), f"Tables claimed as both global and pending: {global_ & pending}"
    missing = tables - (scoped | global_ | pending)
    assert missing == set(), f"Tables with no tenant-scoping decision recorded at all: {missing}"
    stale = (scoped | global_ | pending) - tables
    assert stale == set(), f"Registries reference tables that no longer exist in any migration: {stale}"


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
