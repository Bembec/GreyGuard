"""Unit tests for backend.app.postgres_backup_ops.

No real PostgreSQL server or pg_dump/pg_restore binaries are required: every
test stubs `subprocess.run` so these run anywhere, matching how
`test_malware_scanner.py` exercises its adapter against a fake server rather
than a real one. A real end-to-end rehearsal belongs in
`deployment/postgresql-rehearsal.yml`-style CI, not here.
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from backend.app import postgres_backup_ops


POSTGRES_URL = "postgresql://greyguard:secret@localhost/greyguard"


def test_database_url_rejects_non_postgresql(monkeypatch):
    monkeypatch.delenv("GREYGUARD_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        postgres_backup_ops._database_url()


def test_database_url_normalizes_psycopg_scheme(monkeypatch):
    monkeypatch.setenv("GREYGUARD_DATABASE_URL", "postgresql+psycopg://greyguard:secret@localhost/greyguard")
    assert postgres_backup_ops._database_url() == POSTGRES_URL


def test_backup_writes_manifest_on_success(tmp_path, monkeypatch):
    monkeypatch.setenv("GREYGUARD_DATABASE_URL", POSTGRES_URL)
    destination = tmp_path / "dump.pgcustom"

    def fake_run(argv, capture_output=True, text=True, check=False):
        if argv[0] == "pg_dump":
            destination.write_bytes(b"dump-bytes")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(postgres_backup_ops.subprocess, "run", fake_run)

    manifest = postgres_backup_ops.backup_database(destination)

    assert manifest["size_bytes"] == len(b"dump-bytes")
    assert manifest["format"] == "pg_dump-custom"
    manifest_path = destination.with_suffix(destination.suffix + ".manifest.json")
    assert manifest_path.exists()


def test_backup_failure_removes_partial_file_and_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("GREYGUARD_DATABASE_URL", POSTGRES_URL)
    destination = tmp_path / "dump.pgcustom"

    def fake_run(argv, capture_output=True, text=True, check=False):
        destination.write_bytes(b"partial")
        return SimpleNamespace(returncode=1, stdout="", stderr="connection refused")

    monkeypatch.setattr(postgres_backup_ops.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="connection refused"):
        postgres_backup_ops.backup_database(destination)

    assert not destination.exists()
    assert not destination.with_suffix(destination.suffix + ".manifest.json").exists()


def test_backup_never_writes_manifest_when_verification_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("GREYGUARD_DATABASE_URL", POSTGRES_URL)
    destination = tmp_path / "dump.pgcustom"

    def fake_run(argv, capture_output=True, text=True, check=False):
        if argv[0] == "pg_dump":
            destination.write_bytes(b"dump-bytes")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="not a valid archive")

    monkeypatch.setattr(postgres_backup_ops.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="structural verification"):
        postgres_backup_ops.backup_database(destination)

    assert not destination.with_suffix(destination.suffix + ".manifest.json").exists()


def test_verify_database_raises_on_invalid_dump(tmp_path, monkeypatch):
    path = tmp_path / "bad.pgcustom"
    path.write_bytes(b"not a dump")

    def fake_run(argv, capture_output=True, text=True, check=False):
        return SimpleNamespace(returncode=1, stdout="", stderr="unexpected end of file")

    monkeypatch.setattr(postgres_backup_ops.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="structural verification"):
        postgres_backup_ops.verify_database(path)


def test_verify_database_passes_on_valid_dump(tmp_path, monkeypatch):
    path = tmp_path / "good.pgcustom"
    path.write_bytes(b"dump")

    def fake_run(argv, capture_output=True, text=True, check=False):
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(postgres_backup_ops.subprocess, "run", fake_run)

    assert postgres_backup_ops.verify_database(path) is True


def test_restore_requires_confirm(tmp_path, monkeypatch):
    monkeypatch.setenv("GREYGUARD_DATABASE_URL", POSTGRES_URL)
    calls = []
    monkeypatch.setattr(postgres_backup_ops.subprocess, "run", lambda *a, **k: calls.append(a) or SimpleNamespace(returncode=0, stdout="", stderr=""))

    with pytest.raises(ValueError, match="confirmation"):
        postgres_backup_ops.restore_database(tmp_path / "dump.pgcustom", confirm=False)

    assert calls == []


def test_restore_invokes_pg_restore_with_safe_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("GREYGUARD_DATABASE_URL", POSTGRES_URL)
    backup = tmp_path / "dump.pgcustom"
    backup.write_bytes(b"dump")
    calls = []

    def fake_run(argv, capture_output=True, text=True, check=False):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(postgres_backup_ops.subprocess, "run", fake_run)

    postgres_backup_ops.restore_database(backup, confirm=True)

    restore_call = calls[-1]
    assert restore_call[0] == "pg_restore"
    assert f"--dbname={POSTGRES_URL}" in restore_call
    assert "--clean" in restore_call
    assert "--if-exists" in restore_call
    assert "--no-owner" in restore_call
    assert str(backup) in restore_call


def test_restore_failure_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("GREYGUARD_DATABASE_URL", POSTGRES_URL)
    backup = tmp_path / "dump.pgcustom"
    backup.write_bytes(b"dump")

    def fake_run(argv, capture_output=True, text=True, check=False):
        if argv[0] == "pg_restore" and "--list" in argv:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="database is being accessed by other users")

    monkeypatch.setattr(postgres_backup_ops.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="being accessed"):
        postgres_backup_ops.restore_database(backup, confirm=True)
