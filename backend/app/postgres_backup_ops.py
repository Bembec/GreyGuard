"""Atomic PostgreSQL backup, verification, and restore commands.

`database_ops.py` only ever touches the local SQLite file at `database_path`,
which is not the database of record once `GREYGUARD_DATABASE_URL` selects
PostgreSQL (see `db_compat.py`) - exactly the configuration
`docker-compose.production.yml` uses. This module is that deployment's
equivalent: it shells out to the standard `pg_dump`/`pg_restore` client
tools (no new Python dependency) against the same connection URL the
application itself uses, so backup and restore always act on the real data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _database_url() -> str:
    url = os.environ.get("GREYGUARD_DATABASE_URL", "").strip()
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise RuntimeError("GREYGUARD_DATABASE_URL must select PostgreSQL to use these commands.")
    return url.replace("postgresql+psycopg://", "postgresql://")


def backup_database(destination) -> dict:
    url = _database_url()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["pg_dump", f"--dbname={url}", "--format=custom", "--file", str(destination)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        if destination.exists():
            destination.unlink()
        raise RuntimeError(f"pg_dump failed: {result.stderr.strip()}")
    verify_database(destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": destination.name,
        "sha256": digest,
        "size_bytes": destination.stat().st_size,
        "format": "pg_dump-custom",
    }
    destination.with_suffix(destination.suffix + ".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_database(path) -> bool:
    """Confirm the dump file is structurally valid, without requiring a live server."""
    path = Path(path)
    result = subprocess.run(["pg_restore", "--list", str(path)], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Backup failed structural verification: {result.stderr.strip()}")
    return True


def restore_database(backup, confirm: bool = False) -> None:
    if not confirm:
        raise ValueError("Restore requires explicit confirmation.")
    url = _database_url()
    backup = Path(backup)
    verify_database(backup)
    result = subprocess.run(
        ["pg_restore", f"--dbname={url}", "--clean", "--if-exists", "--no-owner", "--no-privileges", str(backup)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pg_restore failed: {result.stderr.strip()}")


def main():
    parser = argparse.ArgumentParser(description="GreyGuard PostgreSQL backup operations")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("backup"); create.add_argument("destination")
    verify = commands.add_parser("verify"); verify.add_argument("path")
    restore = commands.add_parser("restore"); restore.add_argument("backup"); restore.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.command == "backup":
        print(json.dumps(backup_database(args.destination), indent=2))
    elif args.command == "verify":
        verify_database(args.path)
        print("Backup structure: ok")
    else:
        restore_database(args.backup, args.confirm)
        print("Restore complete.")


if __name__ == "__main__":
    main()
