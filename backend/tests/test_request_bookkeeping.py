"""Per-request bookkeeping: schema initialization runs once per database, and the observability
configuration is read once per request and cached briefly - without serving stale settings after
a local change or initializing the wrong database."""
import time

from backend.app import db_compat, observability


def test_initialize_once_runs_once_per_database_and_again_for_a_new_one(tmp_path, monkeypatch):
    monkeypatch.delenv("GREYGUARD_DATABASE_URL", raising=False)
    monkeypatch.setattr(db_compat, "_INITIALIZED", set())
    calls = []
    first, second = tmp_path / "a.db", tmp_path / "b.db"
    first.touch()
    second.touch()
    for _ in range(3):
        db_compat.initialize_once("module", first, lambda: calls.append("a"))
    db_compat.initialize_once("module", second, lambda: calls.append("b"))
    assert calls == ["a", "b"]
    # A missing database file is always initialized (and not remembered).
    missing = tmp_path / "missing.db"
    db_compat.initialize_once("module", missing, lambda: calls.append("missing"))
    db_compat.initialize_once("module", missing, lambda: calls.append("missing"))
    assert calls == ["a", "b", "missing", "missing"]


def test_config_is_cached_briefly_and_a_local_change_applies_at_once(tmp_path, monkeypatch):
    monkeypatch.setattr(observability, "database_path", tmp_path / "obs.db")
    monkeypatch.setattr(observability, "_config_cache", {})
    observability.initialize_observability()
    observability.update_config(True, True, False, 0.25, 1000, "admin")
    assert observability.get_config(cached=True)["sample_rate"] == 0.25
    observability.update_config(True, True, False, 0.75, 1000, "admin")
    assert observability.get_config(cached=True)["sample_rate"] == 0.75
    # A change made directly (as another worker process would) is picked up after the TTL.
    with observability.sqlite3.connect(observability.database_path) as connection:
        connection.execute("UPDATE observability_config SET sample_rate=0.5 WHERE config_id=1")
    assert observability.get_config(cached=True)["sample_rate"] == 0.75
    monkeypatch.setattr(observability, "CONFIG_TTL_SECONDS", 0.0)
    time.sleep(0.01)
    assert observability.get_config(cached=True)["sample_rate"] == 0.5
    assert observability.get_config()["sample_rate"] == 0.5


def test_a_request_reads_the_config_once(tmp_path, monkeypatch):
    monkeypatch.setattr(observability, "database_path", tmp_path / "obs.db")
    monkeypatch.setattr(observability, "_config_cache", {})
    observability.initialize_observability()
    reads = []
    original = observability.get_config
    monkeypatch.setattr(observability, "get_config", lambda cached=False: reads.append(cached) or original(cached))
    context = observability.start_request("GET", "/health")
    observability.finish_request(context, 200)
    assert len(reads) == 1 and "_config" not in context
