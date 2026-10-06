"""SQLite-compatible database boundary with PostgreSQL translation support."""
from __future__ import annotations

import os
import re
import sqlite3 as _sqlite
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

class PostgresConnection:
    def __init__(self,url: str):
        try:import psycopg
        except ImportError as error:raise RuntimeError("Install psycopg to use PostgreSQL.") from error
        self._psycopg=psycopg;self._connection=psycopg.connect(url.replace("postgresql+psycopg://","postgresql://"));self.row_factory=None
        self._connection.execute("CREATE EXTENSION IF NOT EXISTS citext");self._connection.commit()
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

