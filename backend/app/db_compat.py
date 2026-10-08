"""SQLite-compatible database boundary with PostgreSQL translation support."""
from __future__ import annotations

import os
import re
import sqlite3 as _sqlite
import threading
from pathlib import Path
from typing import Any

Row = _sqlite.Row
Connection = Any
Error = _sqlite.Error
IntegrityError = _sqlite.IntegrityError

class CompatRow:
    def __init__(self,values,names):self._values=tuple(values);self._names=tuple(names);self._map=dict(zip(self._names,self._values))
    def __getitem__(self,key):return self._map[key] if isinstance(key,str) else self._values[key]
    def __iter__(self):return iter(self._values)
    def __len__(self):return len(self._values)
    def keys(self):return self._names

class VirtualCursor:
    def __init__(self,rows=(),rowcount=0,lastrowid=None):self._rows=list(rows);self.rowcount=rowcount;self.lastrowid=lastrowid
    def fetchone(self):return self._rows.pop(0) if self._rows else None
    def fetchall(self):rows=self._rows;self._rows=[];return rows
    def __iter__(self):return iter(self.fetchall())

def _qmarks(sql: str) -> str:
    output=[];quote=None
    for char in sql:
        if char in ("'",'"'):
            if quote==char:quote=None
            elif quote is None:quote=char
        output.append("%s" if char=="?" and quote is None else char)
    return "".join(output)

def _translate(sql: str) -> str:
    statement=sql.strip().rstrip(";")
    statement=re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT","BIGSERIAL PRIMARY KEY",statement,flags=re.I)
    statement=re.sub(r"\bBLOB\b","BYTEA",statement,flags=re.I)
    statement=re.sub(r"\bTEXT(\s+NOT\s+NULL)?(\s+UNIQUE)?\s+COLLATE\s+NOCASE",r"CITEXT\1\2",statement,flags=re.I)
    statement=re.sub(r"\s+COLLATE\s+NOCASE", "", statement, flags=re.I)
    statement=re.sub(r"\bLIMIT\s+-1\s+OFFSET\b", "OFFSET", statement, flags=re.I)
    if re.match(r"INSERT\s+OR\s+REPLACE\s+INTO\s+observability_correlations",statement,re.I):
        statement=re.sub(r"INSERT\s+OR\s+REPLACE","INSERT",statement,count=1,flags=re.I)
        statement += " ON CONFLICT (request_id) DO UPDATE SET correlation_id=EXCLUDED.correlation_id,created_at=EXCLUDED.created_at"
    elif re.match(r"INSERT\s+OR\s+IGNORE\s+INTO",statement,re.I):
        statement=re.sub(r"INSERT\s+OR\s+IGNORE","INSERT",statement,count=1,flags=re.I)
        statement += " ON CONFLICT DO NOTHING"
    if re.match(r"INSERT\s+INTO\s+alert_notes\b",statement,re.I) and "RETURNING" not in statement.upper():
        statement += " RETURNING id"
    return _qmarks(statement)

class Cursor:
    def __init__(self,cursor,lastrowid=None):self._cursor=cursor;self.rowcount=cursor.rowcount;self.lastrowid=lastrowid
    def _row(self,value):
        if value is None:return None
        names=[item.name if hasattr(item,"name") else item[0] for item in self._cursor.description or ()]
        return CompatRow(value,names)
    def fetchone(self):return self._row(self._cursor.fetchone())
    def fetchall(self):return [self._row(value) for value in self._cursor.fetchall()]
    def __iter__(self):
        while True:
            value=self.fetchone()
            if value is None:break
            yield value

# PostgreSQL advisory-lock keys. They must differ: the extension lock is taken
# on ordinary connections while a worker may already hold the startup lock.
STARTUP_LOCK_KEY = 4747110001
EXTENSION_LOCK_KEY = 4747110002
_extensions_ready = False
_extensions_guard = threading.Lock()


def _postgres_url():
    url = os.environ.get("GREYGUARD_DATABASE_URL", "").strip()
    if url.startswith(("postgresql://", "postgresql+psycopg://")):
        return url.replace("postgresql+psycopg://", "postgresql://")
    return None


def _ensure_extensions(connection, psycopg):
    """Create required extensions once per process, safely across concurrent workers."""
    global _extensions_ready
    if _extensions_ready:
        return
    with _extensions_guard:
        if _extensions_ready:
            return
        try:
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (EXTENSION_LOCK_KEY,))
            connection.execute("CREATE EXTENSION IF NOT EXISTS citext")
            connection.commit()
        except psycopg.errors.UniqueViolation:
            # Another process created it between the check and the insert.
            connection.rollback()
        _extensions_ready = True


class initialization_lock:
    """Serialize schema initialization across all backend workers.

    Every `initialize_*()` function across backend/app runs inside this lock (see
    api.py's lifespan()). Several of them check a column's presence via
    PRAGMA table_info before an ALTER TABLE ADD COLUMN - a check-then-act race if
    two worker processes run it concurrently against the same database: both see
    the column missing, both issue the ALTER, and the second raises "duplicate
    column name", crashing that worker's startup (and, since uvicorn treats a
    worker startup failure as fatal to the whole process group, the entire
    container - reproduced directly against deployment/backend.Dockerfile's own
    `--workers 2` default with a SQLite backend).

    PostgreSQL gets real protection via a session-level advisory lock. SQLite has
    no equivalent primitive, so this uses SQLite's own cross-platform file
    locking instead: a dedicated lock file, held under a BEGIN EXCLUSIVE
    transaction for the duration of initialization, so a second worker's same
    attempt blocks (up to `timeout`) until the first one finishes rather than
    racing it.
    """

    def __init__(self):
        self._connection = None
        self._is_postgres = False

    def __enter__(self):
        url = _postgres_url()
        if url:
            import psycopg
            self._connection = psycopg.connect(url, autocommit=True)
            self._connection.execute("SELECT pg_advisory_lock(%s)", (STARTUP_LOCK_KEY,))
            self._is_postgres = True
        else:
            from .paths import data_directory
            lock_path = data_directory() / ".initialization.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = _sqlite.connect(lock_path, timeout=60)
            self._connection.execute("BEGIN EXCLUSIVE")
        return self

    def __exit__(self, *_exc):
        if self._connection is not None:
            try:
                if self._is_postgres:
                    self._connection.execute("SELECT pg_advisory_unlock(%s)", (STARTUP_LOCK_KEY,))
                else:
                    self._connection.commit()
            finally:
                self._connection.close()
                self._connection = None
        return False


class PostgresConnection:
    def __init__(self,url: str):
        try:import psycopg
        except ImportError as error:raise RuntimeError("Install psycopg to use PostgreSQL.") from error
        self._psycopg=psycopg;self._connection=psycopg.connect(url.replace("postgresql+psycopg://","postgresql://"));self.row_factory=None
        _ensure_extensions(self._connection,psycopg)
    def __enter__(self):return self
    def __exit__(self,error_type,error,_trace):
        if error_type:self._connection.rollback()
        else:self._connection.commit()
        self.close()
    def execute(self,sql,parameters=()):
        normalized=sql.strip()
        if re.match(r"PRAGMA\s+foreign_keys",normalized,re.I):return VirtualCursor()
        match=re.match(r"PRAGMA\s+table_info\(([^)]+)\)",normalized,re.I)
        if match:
            cursor=self._connection.execute("SELECT ordinal_position-1,column_name,data_type,CASE WHEN is_nullable='NO' THEN 1 ELSE 0 END,column_default,0 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",(match.group(1).strip("'\""),))
            return Cursor(cursor)
        if "FROM sqlite_master" in normalized:
            normalized=re.sub(r"SELECT\s+name\s+FROM\s+sqlite_master\s+WHERE\s+type\s*=\s*['\"]table['\"]","SELECT tablename AS name FROM pg_tables WHERE schemaname='public'",normalized,flags=re.I)
        translated=_translate(normalized)
        try:
            cursor=self._connection.execute(translated,parameters)
            lastrowid=None
            if " RETURNING ID" in translated.upper():
                row=cursor.fetchone();lastrowid=row[0] if row else None
            return Cursor(cursor,lastrowid)
        except self._psycopg.IntegrityError as error:
            raise IntegrityError(str(error)) from error
        except self._psycopg.Error as error:
            raise Error(str(error)) from error
    def executemany(self,sql,parameters):
        try:
            cursor=self._connection.cursor();cursor.executemany(_translate(sql),parameters);return Cursor(cursor)
        except self._psycopg.IntegrityError as error:raise IntegrityError(str(error)) from error
        except self._psycopg.Error as error:raise Error(str(error)) from error
    def executescript(self,script):
        for statement in script.split(";"):
            if statement.strip():self.execute(statement)
        return VirtualCursor()
    def commit(self):self._connection.commit()
    def rollback(self):self._connection.rollback()
    def close(self):self._connection.close()

def connect(database=None,*args,**kwargs):
    url=os.environ.get("GREYGUARD_DATABASE_URL","").strip()
    if url.startswith(("postgresql://","postgresql+psycopg://")):return PostgresConnection(url)
    if os.environ.get("GREYGUARD_ENV","").strip().lower()=="production":
        raise RuntimeError("Production requires GREYGUARD_DATABASE_URL with PostgreSQL.")
    return _sqlite.connect(Path(database) if isinstance(database,Path) else database,*args,**kwargs)

def backend_name() -> str:
    return "postgresql" if os.environ.get("GREYGUARD_DATABASE_URL","").startswith("postgresql") else "sqlite"

