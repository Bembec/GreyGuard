"""The PostgreSQL connection pool keeps the old per-call semantics: only idle connections with no
open transaction are reused, an open transaction is rolled back as a close would, broken
connections are dropped, long-idle ones are checked, and the pool is bounded."""
import types

import pytest

from backend.app import db_compat

IDLE, INTRANS = "IDLE", "INTRANS"


class FakeConnection:
    def __init__(self):
        self.closed = self.broken = False
        self.info = types.SimpleNamespace(transaction_status=IDLE)
        self.rollbacks = self.pings = 0

    def rollback(self):
        self.rollbacks += 1
        self.info.transaction_status = IDLE

    def close(self):
        self.closed = True

    def execute(self, sql, *_):
        self.pings += 1
        if self.broken:
            raise FakePsycopg.Error("server closed the connection")


class FakePsycopg:
    class Error(Exception):
        pass

    pq = types.SimpleNamespace(TransactionStatus=types.SimpleNamespace(IDLE=IDLE))
    opened = []

    @classmethod
    def connect(cls, url):
        connection = FakeConnection()
        cls.opened.append(connection)
        return connection


@pytest.fixture(autouse=True)
def empty_pool(monkeypatch):
    monkeypatch.setattr(db_compat, "_POOL", {})
    FakePsycopg.opened = []


def test_an_idle_connection_is_reused():
    first, fresh = db_compat._acquire("pg://x", FakePsycopg)
    assert fresh
    db_compat._release("pg://x", first, FakePsycopg)
    again, fresh = db_compat._acquire("pg://x", FakePsycopg)
    assert again is first and not fresh and len(FakePsycopg.opened) == 1


def test_an_open_transaction_is_rolled_back_before_reuse():
    connection, _ = db_compat._acquire("pg://x", FakePsycopg)
    connection.info.transaction_status = INTRANS
    db_compat._release("pg://x", connection, FakePsycopg)
    assert connection.rollbacks == 1 and not connection.closed


def test_broken_or_closed_connections_are_never_reused():
    connection, _ = db_compat._acquire("pg://x", FakePsycopg)
    connection.broken = True
    db_compat._release("pg://x", connection, FakePsycopg)
    assert connection.closed
    assert db_compat._acquire("pg://x", FakePsycopg)[0] is not connection


def test_a_long_idle_connection_is_checked_and_dropped_if_dead(monkeypatch):
    connection, _ = db_compat._acquire("pg://x", FakePsycopg)
    db_compat._release("pg://x", connection, FakePsycopg)
    monkeypatch.setattr(db_compat, "POOL_IDLE_CHECK_SECONDS", -1)
    connection.broken = False
    connection.execute = lambda *_: (_ for _ in ()).throw(FakePsycopg.Error("gone"))
    replacement, fresh = db_compat._acquire("pg://x", FakePsycopg)
    assert fresh and replacement is not connection and connection.closed


def test_the_pool_is_bounded_and_can_be_disabled(monkeypatch):
    monkeypatch.setenv("GREYGUARD_DB_POOL_SIZE", "2")
    connections = [db_compat._acquire("pg://x", FakePsycopg)[0] for _ in range(4)]
    for connection in connections:
        db_compat._release("pg://x", connection, FakePsycopg)
    assert len(db_compat._POOL["pg://x"]) == 2 and sum(c.closed for c in connections) == 2
    monkeypatch.setenv("GREYGUARD_DB_POOL_SIZE", "0")
    extra = db_compat._acquire("pg://y", FakePsycopg)[0]
    db_compat._release("pg://y", extra, FakePsycopg)
    assert extra.closed
