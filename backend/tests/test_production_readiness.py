import sqlite3
import pytest
from backend.app import database_ops
from backend.app.production_config import load_production_config


def test_production_configuration_fails_closed():
    with pytest.raises(RuntimeError, match="Missing required"):
        load_production_config({"GREYGUARD_ENV":"production"})


def test_production_configuration_rejects_wildcards():
    env={"GREYGUARD_ENV":"production","GREYGUARD_BOOTSTRAP_EMAIL":"owner@example.com","GREYGUARD_BOOTSTRAP_PASSWORD":"VeryStrongPassword123!","GREYGUARD_ALLOWED_ORIGINS":"*","GREYGUARD_TRUSTED_HOSTS":"greyguard.example.com"}
    with pytest.raises(RuntimeError, match="Wildcard"): load_production_config(env)


def test_backup_and_restore_are_verified(tmp_path, monkeypatch):
    source=tmp_path/"source.db"; backup=tmp_path/"backup.db"; restored=tmp_path/"restored.db"
    with sqlite3.connect(source) as connection: connection.execute("CREATE TABLE evidence(value TEXT)"); connection.execute("INSERT INTO evidence VALUES('preserved')")
    monkeypatch.setattr(database_ops,"database_path",source)
    manifest=database_ops.backup_database(backup)
    assert len(manifest["sha256"])==64 and database_ops.verify_database(backup)
    database_ops.restore_database(backup,restored,confirm=True)
    with sqlite3.connect(restored) as connection: assert connection.execute("SELECT value FROM evidence").fetchone()[0]=="preserved"


def test_restore_requires_confirmation(tmp_path):
    with pytest.raises(ValueError, match="confirmation"): database_ops.restore_database(tmp_path/"backup.db",confirm=False)
