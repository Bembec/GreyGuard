"""PostgreSQL startup must be safe when several backend workers start at once."""

from backend.app import db_compat


class FakeUniqueViolation(Exception):
    pass


class FakePsycopg:
    class errors:
        UniqueViolation = FakeUniqueViolation


class FakeConnection:
    def __init__(self, raise_on_create=False):
        self.raise_on_create = raise_on_create
        self.statements = []
        self.committed = 0
        self.rolled_back = 0

    def execute(self, sql, parameters=()):
        self.statements.append(sql)
        if self.raise_on_create and sql.startswith("CREATE EXTENSION"):
            raise FakeUniqueViolation("citext already exists")

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def test_extension_creation_takes_a_lock_and_runs_once_per_process(monkeypatch):
    monkeypatch.setattr(db_compat, "_extensions_ready", False)
    first, second = FakeConnection(), FakeConnection()
    db_compat._ensure_extensions(first, FakePsycopg)
    db_compat._ensure_extensions(second, FakePsycopg)
    assert first.statements[0].startswith("SELECT pg_advisory_xact_lock")
    assert "CREATE EXTENSION IF NOT EXISTS citext" in first.statements
    assert first.committed == 1
    assert second.statements == []


def test_concurrent_extension_creation_by_another_worker_is_tolerated(monkeypatch):
    monkeypatch.setattr(db_compat, "_extensions_ready", False)
    connection = FakeConnection(raise_on_create=True)
    db_compat._ensure_extensions(connection, FakePsycopg)
    assert connection.rolled_back == 1
    assert db_compat._extensions_ready is True


def test_startup_and_extension_locks_never_share_a_key():
    # Sharing a key would deadlock a worker that holds the startup lock.
    assert db_compat.STARTUP_LOCK_KEY != db_compat.EXTENSION_LOCK_KEY


def test_initialization_lock_is_a_no_op_without_postgresql(monkeypatch):
    monkeypatch.delenv("GREYGUARD_DATABASE_URL", raising=False)
    with db_compat.initialization_lock() as lock:
        assert lock._connection is None
