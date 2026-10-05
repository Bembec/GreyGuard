import base64,sqlite3
import pytest
from backend.app.encrypted_backups import create_encrypted_backup,restore_encrypted_backup
from backend.app.migration_readiness import inventory,validate_postgresql_url

def backup_key():return base64.urlsafe_b64encode(b"g"*32).decode()

def test_encrypted_backup_round_trip(tmp_path):
    source=tmp_path/"source.db";encrypted=tmp_path/"backup.ggb";restored=tmp_path/"restored.db"
    with sqlite3.connect(source) as connection:connection.execute("CREATE TABLE evidence(value TEXT)");connection.execute("INSERT INTO evidence VALUES('preserved')")
    manifest=create_encrypted_backup(source,encrypted,backup_key())
    assert encrypted.read_bytes()[:16]!=source.read_bytes()[:16] and manifest["algorithm"]=="AES-256-GCM"
    restore_encrypted_backup(encrypted,restored,backup_key(),confirm=True)
    with sqlite3.connect(restored) as connection:assert connection.execute("SELECT value FROM evidence").fetchone()[0]=="preserved"

def test_encrypted_restore_fails_with_wrong_key(tmp_path):
    source=tmp_path/"source.db";encrypted=tmp_path/"backup.ggb"
    with sqlite3.connect(source) as connection:connection.execute("CREATE TABLE evidence(value TEXT)")
    create_encrypted_backup(source,encrypted,backup_key())
    with pytest.raises(Exception):restore_encrypted_backup(encrypted,tmp_path/"bad.db",base64.urlsafe_b64encode(b"x"*32).decode(),confirm=True)

def test_restore_requires_confirmation(tmp_path):
    with pytest.raises(ValueError,match="confirmation"):restore_encrypted_backup(tmp_path/"missing",tmp_path/"target",backup_key())

def test_postgresql_migration_inventory_is_explicit(tmp_path):
    (tmp_path/"module.py").write_text("import sqlite3\nsqlite3.connect('x')\n",encoding="utf-8")
    result=inventory(tmp_path);assert not result["ready_for_postgresql"] and result["totals"]["direct_connect"]==1

def test_postgresql_url_validation():
    assert validate_postgresql_url("postgresql://greyguard:secret@postgres/greyguard")
    with pytest.raises(ValueError):validate_postgresql_url("sqlite:///greyguard.db")
