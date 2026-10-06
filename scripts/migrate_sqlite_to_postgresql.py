"""One-way, evidenced SQLite-to-PostgreSQL migration rehearsal."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg


def quote(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError(f"Unsafe identifier: {name}")
    return f'"{name}"'


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value):
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        return {"bytes_sha256": hashlib.sha256(value).hexdigest(), "length": len(value)}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def rows_digest(rows) -> str:
    """Return an order-independent digest for cross-engine content checks."""
    encoded = [
        json.dumps([_canonical(value) for value in row], separators=(",", ":"), sort_keys=True)
        for row in rows
    ]
    return hashlib.sha256("\n".join(sorted(encoded)).encode("utf-8")).hexdigest()


def repair_sequences(postgres, tables: dict) -> list[dict]:
    repaired = []
    for table, detail in tables.items():
        for column in detail["column_names"]:
            sequence = postgres.execute(
                "SELECT pg_get_serial_sequence(%s, %s)", (table, column)
            ).fetchone()[0]
            if not sequence:
                continue
            maximum = postgres.execute(
                f"SELECT MAX({quote(column)}) FROM {quote(table)}"
            ).fetchone()[0]
            if maximum is None:
                postgres.execute("SELECT setval(%s, 1, false)", (sequence,))
            else:
                postgres.execute("SELECT setval(%s, %s, true)", (sequence, maximum))
            repaired.append({"table": table, "column": column, "sequence": sequence})
    return repaired


def migrate(source: Path, url: str, confirm: bool = False, backup: Path | None = None) -> dict:
    if not confirm:
        raise ValueError("Migration requires explicit confirmation.")
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise ValueError("A PostgreSQL URL is required.")
    if not source.is_file():
        raise FileNotFoundError(source)

    source_hash = file_hash(source)
    backup = backup or Path("artifacts/pre-migration-greyguard.db")
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, backup)
    if file_hash(backup) != source_hash:
        raise RuntimeError("Pre-migration backup verification failed.")

    evidence = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "source_sha256": source_hash,
        "backup": str(backup),
        "backup_sha256": file_hash(backup),
        "tables": {},
    }
    sqlite = sqlite3.connect(source)
    sqlite.row_factory = sqlite3.Row
    postgres = psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"))
    try:
        source_tables = [
            row[0]
            for row in sqlite.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        target_tables = {
            row[0]
            for row in postgres.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            )
        }
        missing = [name for name in source_tables if name not in target_tables]
        if missing:
            raise RuntimeError("PostgreSQL schema is missing tables: " + ", ".join(missing))

        postgres.execute("SET session_replication_role = replica")
        for table in source_tables:
            postgres.execute(f"TRUNCATE TABLE {quote(table)} CASCADE")
        for table in source_tables:
            columns = [
                row[1] for row in sqlite.execute(f"PRAGMA table_info({quote(table)})")
            ]
            rows = sqlite.execute(f"SELECT * FROM {quote(table)}").fetchall()
            if rows:
                placeholders = ",".join(["%s"] * len(columns))
                column_sql = ",".join(quote(value) for value in columns)
                with postgres.cursor() as cursor:
                    cursor.executemany(
                        f"INSERT INTO {quote(table)} ({column_sql}) VALUES ({placeholders})",
                        [tuple(row) for row in rows],
                    )
            evidence["tables"][table] = {
                "rows": len(rows),
                "columns": len(columns),
                "column_names": columns,
                "source_digest": rows_digest(rows),
            }
        postgres.execute("SET session_replication_role = DEFAULT")
        evidence["sequences_repaired"] = repair_sequences(postgres, evidence["tables"])
        postgres.commit()

        for table, detail in evidence["tables"].items():
            target_rows = postgres.execute(f"SELECT * FROM {quote(table)}").fetchall()
            detail["target_digest"] = rows_digest(target_rows)
            detail["verified"] = (
                len(target_rows) == detail["rows"]
                and detail["target_digest"] == detail["source_digest"]
            )
            if not detail["verified"]:
                raise RuntimeError(f"Content verification failed for {table}")
        if file_hash(source) != source_hash:
            raise RuntimeError("Source SQLite database changed during migration.")
        evidence["completed_at"] = datetime.now(timezone.utc).isoformat()
        evidence["verified"] = True
        return evidence
    except Exception:
        postgres.rollback()
        raise
    finally:
        sqlite.close()
        postgres.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--database-url", default=os.environ.get("GREYGUARD_DATABASE_URL"))
    parser.add_argument("--backup", default="artifacts/pre-migration-greyguard.db")
    parser.add_argument("--evidence", default="artifacts/postgresql-migration-evidence.json")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    evidence = migrate(
        Path(args.source), args.database_url or "", args.confirm, Path(args.backup)
    )
    output = Path(args.evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
