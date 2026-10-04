"""Atomic GreyGuard SQLite backup, verification, and restore commands."""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from .database import database_path


def backup_database(destination):
    source = Path(database_path); destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst: src.backup(dst)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "database": destination.name, "sha256": digest, "size_bytes": destination.stat().st_size}
    destination.with_suffix(destination.suffix + ".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    verify_database(destination)
    return manifest


def verify_database(path):
    with sqlite3.connect(Path(path)) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if result != "ok": raise RuntimeError(f"Database integrity check failed: {result}")
    return True


def restore_database(backup, target=None, confirm=False):
    if not confirm: raise ValueError("Restore requires explicit confirmation.")
    backup = Path(backup); target = Path(target or database_path)
    verify_database(backup); target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".restore")
    src = sqlite3.connect(backup)
    dst = sqlite3.connect(temporary)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    verify_database(temporary); temporary.replace(target)
    return target


def main():
    parser=argparse.ArgumentParser(description="GreyGuard database operations"); commands=parser.add_subparsers(dest="command",required=True)
    create=commands.add_parser("backup"); create.add_argument("destination")
    verify=commands.add_parser("verify"); verify.add_argument("path")
    restore=commands.add_parser("restore"); restore.add_argument("backup"); restore.add_argument("--target"); restore.add_argument("--confirm",action="store_true")
    args=parser.parse_args()
    if args.command=="backup": print(json.dumps(backup_database(args.destination),indent=2))
    elif args.command=="verify": verify_database(args.path); print("Database integrity: ok")
    else: print(f"Restored database to {restore_database(args.backup,args.target,args.confirm)}")


if __name__ == "__main__": main()


