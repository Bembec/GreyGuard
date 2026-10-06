from scripts import benchmark_greyguard, migrate_sqlite_to_postgresql


def test_migration_digest_is_order_independent_and_binary_safe():
    first = [(2, b"evidence"), (1, "preserved")]
    second = [(1, "preserved"), (2, memoryview(b"evidence"))]
    assert migrate_sqlite_to_postgresql.rows_digest(first) == (
        migrate_sqlite_to_postgresql.rows_digest(second)
    )


def test_file_hash_detects_source_changes(tmp_path):
    source = tmp_path / "source.db"
    source.write_bytes(b"before")
    original = migrate_sqlite_to_postgresql.file_hash(source)
    source.write_bytes(b"after")
    assert migrate_sqlite_to_postgresql.file_hash(source) != original


def test_percentile_reports_tail_latency():
    values = [1, 2, 3, 4, 100]
    assert benchmark_greyguard.percentile(values, 0.5) == 2
    assert benchmark_greyguard.percentile(values, 0.95) == 4

