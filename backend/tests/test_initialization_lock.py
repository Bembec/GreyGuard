"""initialization_lock must actually serialize concurrent SQLite initializers.

Regression for a real crash found while smoke-testing a Docker build: multiple
initialize_*() functions across backend/app check a column's presence via
PRAGMA table_info before ALTER TABLE ADD COLUMN, which races under concurrent
access - both workers see the column missing, both ALTER, the second raises
"duplicate column name", and since uvicorn treats a worker startup failure as
fatal to the whole process group, the entire backend.Dockerfile container
crash-loops under its own documented `--workers 2` default with a SQLite
backend. initialization_lock previously only protected PostgreSQL (via an
advisory lock); for SQLite it was a no-op.
"""
import sqlite3
import threading
import time

import pytest

from backend.app import db_compat


@pytest.fixture()
def no_postgres(monkeypatch):
    monkeypatch.delenv("GREYGUARD_DATABASE_URL", raising=False)


def test_sqlite_lock_serializes_the_check_then_alter_race(tmp_path, monkeypatch, no_postgres):
    monkeypatch.setattr("backend.app.paths.data_directory", lambda: tmp_path)
    db_path = tmp_path / "race.db"
    with sqlite3.connect(db_path) as setup:
        setup.execute("CREATE TABLE demo(id INTEGER PRIMARY KEY)")

    errors = []

    def worker():
        try:
            with db_compat.initialization_lock():
                connection = sqlite3.connect(db_path)
                try:
                    columns = {row[1] for row in connection.execute("PRAGMA table_info(demo)")}
                    # Widen the race window: without the lock, both threads would
                    # reach this point believing the column is still missing.
                    time.sleep(0.05)
                    if "extra" not in columns:
                        connection.execute("ALTER TABLE demo ADD COLUMN extra TEXT")
                        connection.commit()
                finally:
                    connection.close()
        except Exception as error:  # noqa: BLE001 - captured for the assertion below
            errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    with sqlite3.connect(db_path) as check:
        columns = {row[1] for row in check.execute("PRAGMA table_info(demo)")}
    assert "extra" in columns


def test_sqlite_lock_blocks_a_second_holder_until_the_first_releases(tmp_path, monkeypatch, no_postgres):
    monkeypatch.setattr("backend.app.paths.data_directory", lambda: tmp_path)
    order = []

    def hold_first():
        with db_compat.initialization_lock():
            order.append("first-acquired")
            time.sleep(0.2)
            order.append("first-released")

    first = threading.Thread(target=hold_first)
    first.start()
    time.sleep(0.05)  # let the first thread acquire before the second tries

    with db_compat.initialization_lock():
        order.append("second-acquired")

    first.join(timeout=30)
    assert order == ["first-acquired", "first-released", "second-acquired"]
