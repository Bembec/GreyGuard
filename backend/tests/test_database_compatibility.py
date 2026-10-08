import sqlite3
from backend.app import db_compat

def test_sqlite_remains_default_backend(tmp_path,monkeypatch):
 monkeypatch.delenv("GREYGUARD_DATABASE_URL",raising=False)
 with db_compat.connect(tmp_path/"compat.db") as connection:
  connection.execute("CREATE TABLE evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,value TEXT UNIQUE)")
  connection.execute("INSERT OR IGNORE INTO evidence(value) VALUES(?)",("preserved",))
  connection.execute("INSERT OR IGNORE INTO evidence(value) VALUES(?)",("preserved",))
  assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]==1
 assert db_compat.backend_name()=="sqlite"

def test_postgresql_translation_covers_supported_sqlite_dialect():
 sql=db_compat._translate("INSERT OR IGNORE INTO evidence(value) VALUES(?)")
 assert "ON CONFLICT DO NOTHING" in sql and "%s" in sql
 ddl=db_compat._translate("CREATE TABLE evidence(id INTEGER PRIMARY KEY AUTOINCREMENT,payload BLOB)")
 assert "BIGSERIAL PRIMARY KEY" in ddl and "BYTEA" in ddl
 assert "CITEXT NOT NULL UNIQUE" in db_compat._translate("CREATE TABLE users(email TEXT NOT NULL UNIQUE COLLATE NOCASE)")

def test_observability_upsert_translation_is_explicit():
 sql=db_compat._translate("INSERT OR REPLACE INTO observability_correlations VALUES(?,?,?)")
 assert "ON CONFLICT (request_id) DO UPDATE" in sql

def test_unbounded_offset_translation_is_postgresql_compatible():
 sql=db_compat._translate("SELECT span_id FROM observability_spans ORDER BY timestamp DESC LIMIT -1 OFFSET ?")
 assert "LIMIT -1" not in sql and "OFFSET %s" in sql

def test_alter_table_add_column_translation_used_by_workload_identities():
 # enterprise_identity.py migrates workload_identities with ALTER TABLE ... ADD COLUMN,
 # which is valid, unmodified PostgreSQL syntax - no special-casing should touch it.
 sql=db_compat._translate("ALTER TABLE workload_identities ADD COLUMN agent_name TEXT")
 assert sql=="ALTER TABLE workload_identities ADD COLUMN agent_name TEXT"

def test_foreign_key_clause_translation_used_by_identity_role_mappings():
 ddl=db_compat._translate(
  "CREATE TABLE identity_role_mappings (mapping_id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, "
  "FOREIGN KEY(provider_id) REFERENCES identity_providers(provider_id))"
 )
 assert "FOREIGN KEY(provider_id) REFERENCES identity_providers(provider_id)" in ddl

def test_executescript_style_multi_statement_block_translates_every_statement():
 # Mirrors enterprise_identity.py's initialize_enterprise_identity(), which runs several
 # CREATE TABLE statements (one with AUTOINCREMENT) through one executescript() call.
 # PostgresConnection.executescript splits on ';' and translates each piece independently -
 # confirm AUTOINCREMENT still translates correctly when it is not the first statement.
 script = """
 CREATE TABLE IF NOT EXISTS identity_providers (provider_id TEXT PRIMARY KEY);
 CREATE TABLE IF NOT EXISTS enterprise_identity_events (
   event_id INTEGER PRIMARY KEY AUTOINCREMENT, detail TEXT NOT NULL);
 """
 translated = [db_compat._translate(statement) for statement in script.split(";") if statement.strip()]
 assert any("BIGSERIAL PRIMARY KEY" in statement for statement in translated)
 assert all("AUTOINCREMENT" not in statement for statement in translated)
