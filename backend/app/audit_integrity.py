"""Tamper-evident audit chaining, retention, immutable mode, and legal holds."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from .database import database_path


GENESIS_HASH = "0" * 64


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def initialize_audit_integrity():
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS audit_integrity_chain (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT, source_table TEXT NOT NULL,
            source_id TEXT NOT NULL, payload_hash TEXT NOT NULL, previous_hash TEXT NOT NULL,
            record_hash TEXT NOT NULL UNIQUE, sealed_at TEXT NOT NULL,
            UNIQUE(source_table,source_id))""")
        connection.execute("""CREATE TABLE IF NOT EXISTS audit_retention_config (
            config_id INTEGER PRIMARY KEY CHECK(config_id=1), retention_days INTEGER NOT NULL,
            immutable_enabled INTEGER NOT NULL, updated_at TEXT NOT NULL, updated_by TEXT NOT NULL)""")
        connection.execute("INSERT OR IGNORE INTO audit_retention_config VALUES(1,365,0,?,?)", (utc_now(), "system"))
        connection.execute("""CREATE TABLE IF NOT EXISTS audit_legal_holds (
            hold_id TEXT PRIMARY KEY, name TEXT NOT NULL, reason TEXT NOT NULL,
            agent_name TEXT, starts_at TEXT, ends_at TEXT, active INTEGER NOT NULL,
            created_at TEXT NOT NULL, created_by TEXT NOT NULL, released_at TEXT, released_by TEXT)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS audit_integrity_checks (
            check_id TEXT PRIMARY KEY, checked_at TEXT NOT NULL, checked_by TEXT NOT NULL,
            valid INTEGER NOT NULL, records_checked INTEGER NOT NULL, first_invalid_sequence INTEGER)""")


def _canonical(row):
    return json.dumps(dict(row), separators=(",", ":"), sort_keys=True, default=str)


def seal_audit_events():
    initialize_audit_integrity()
    sealed = 0
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        previous = connection.execute("SELECT record_hash FROM audit_integrity_chain ORDER BY sequence DESC LIMIT 1").fetchone()
        previous_hash = previous[0] if previous else GENESIS_HASH
        rows = connection.execute("""SELECT * FROM audit_events WHERE CAST(id AS TEXT) NOT IN (
            SELECT source_id FROM audit_integrity_chain WHERE source_table='audit_events') ORDER BY id""").fetchall()
        for row in rows:
            payload_hash = hashlib.sha256(_canonical(row).encode()).hexdigest()
            record_hash = hashlib.sha256(f"{previous_hash}:{payload_hash}:audit_events:{row['id']}".encode()).hexdigest()
            connection.execute("INSERT INTO audit_integrity_chain(source_table,source_id,payload_hash,previous_hash,record_hash,sealed_at) VALUES(?,?,?,?,?,?)",
                ("audit_events", str(row["id"]), payload_hash, previous_hash, record_hash, utc_now()))
            previous_hash = record_hash; sealed += 1
    return sealed


def verify_integrity(actor="system"):
    seal_audit_events(); valid = True; first_invalid = None; checked = 0; expected_previous = GENESIS_HASH
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        chain = connection.execute("SELECT * FROM audit_integrity_chain ORDER BY sequence").fetchall()
        for item in chain:
            checked += 1
            source = connection.execute("SELECT * FROM audit_events WHERE id=?", (item["source_id"],)).fetchone()
            payload_hash = hashlib.sha256(_canonical(source).encode()).hexdigest() if source else "MISSING"
            expected = hashlib.sha256(f"{expected_previous}:{payload_hash}:{item['source_table']}:{item['source_id']}".encode()).hexdigest()
            if payload_hash != item["payload_hash"] or item["previous_hash"] != expected_previous or item["record_hash"] != expected:
                valid = False; first_invalid = item["sequence"]; break
            expected_previous = item["record_hash"]
        check_id = "chk_" + uuid.uuid4().hex
        connection.execute("INSERT INTO audit_integrity_checks VALUES(?,?,?,?,?,?)", (check_id, utc_now(), actor, int(valid), checked, first_invalid))
    return {"check_id": check_id, "valid": valid, "records_checked": checked, "first_invalid_sequence": first_invalid}


def get_controls():
    initialize_audit_integrity()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        config = dict(connection.execute("SELECT * FROM audit_retention_config WHERE config_id=1").fetchone())
        holds = [dict(row) for row in connection.execute("SELECT * FROM audit_legal_holds ORDER BY created_at DESC")]
        last_check = connection.execute("SELECT * FROM audit_integrity_checks ORDER BY checked_at DESC LIMIT 1").fetchone()
        chain_count = connection.execute("SELECT COUNT(*) FROM audit_integrity_chain").fetchone()[0]
    config["immutable_enabled"] = bool(config["immutable_enabled"])
    for hold in holds: hold["active"] = bool(hold["active"])
    return {"config": config, "legal_holds": holds, "chain_records": chain_count, "last_check": dict(last_check) if last_check else None}


def update_retention(retention_days, immutable_enabled, actor):
    if not 30 <= retention_days <= 3650: raise ValueError("Retention must be between 30 and 3650 days.")
    initialize_audit_integrity()
    with sqlite3.connect(database_path) as connection:
        current = connection.execute("SELECT immutable_enabled FROM audit_retention_config WHERE config_id=1").fetchone()[0]
        if current and not immutable_enabled: raise PermissionError("Immutable retention cannot be disabled through the application.")
        connection.execute("UPDATE audit_retention_config SET retention_days=?,immutable_enabled=?,updated_at=?,updated_by=? WHERE config_id=1", (retention_days, int(immutable_enabled), utc_now(), actor))
    return get_controls()["config"]


def create_legal_hold(name, reason, agent_name, starts_at, ends_at, actor):
    if len(reason.strip()) < 12: raise ValueError("A detailed legal-hold reason is required.")
    hold_id = "hold_" + uuid.uuid4().hex
    with sqlite3.connect(database_path) as connection:
        connection.execute("INSERT INTO audit_legal_holds VALUES(?,?,?,?,?,?,?,?,?,?,?)", (hold_id,name.strip(),reason.strip(),agent_name,starts_at,ends_at,1,utc_now(),actor,None,None))
    return next(item for item in get_controls()["legal_holds"] if item["hold_id"] == hold_id)


def release_legal_hold(hold_id, actor):
    with sqlite3.connect(database_path) as connection:
        updated = connection.execute("UPDATE audit_legal_holds SET active=0,released_at=?,released_by=? WHERE hold_id=? AND active=1", (utc_now(),actor,hold_id)).rowcount
    if not updated: raise KeyError("Active legal hold not found.")
    return next(item for item in get_controls()["legal_holds"] if item["hold_id"] == hold_id)


def apply_retention(actor, confirm=False):
    if not confirm: raise PermissionError("Explicit retention-deletion confirmation is required.")
    controls = get_controls(); config = controls["config"]
    if config["immutable_enabled"]: raise PermissionError("Deletion is blocked while immutable retention is enabled.")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=config["retention_days"])).isoformat()
    seal_audit_events()
    with sqlite3.connect(database_path) as connection:
        protected = connection.execute("SELECT COUNT(*) FROM audit_legal_holds WHERE active=1").fetchone()[0]
        if protected: raise PermissionError("Retention deletion is blocked while a legal hold is active.")
        deleted = connection.execute("DELETE FROM audit_events WHERE timestamp<?", (cutoff,)).rowcount
    return {"deleted": deleted, "cutoff": cutoff, "actor": actor, "integrity_evidence_preserved": True}
