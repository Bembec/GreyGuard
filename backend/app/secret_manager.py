"""Secret references, just-in-time retrieval, redaction, and revocation."""
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from .database import database_path

MASK = "[REDACTED]"

def utc_now(): return datetime.now(timezone.utc).isoformat()

def initialize_secret_manager():
    with sqlite3.connect(database_path) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS secret_references (
          secret_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
          provider TEXT NOT NULL, reference TEXT NOT NULL, status TEXT NOT NULL,
          created_by TEXT NOT NULL, created_at TEXT NOT NULL, rotated_at TEXT,
          revoked_at TEXT, last_accessed_at TEXT, access_count INTEGER NOT NULL DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS secret_events (
          event_id INTEGER PRIMARY KEY AUTOINCREMENT, secret_id TEXT NOT NULL,
          timestamp TEXT NOT NULL, actor TEXT NOT NULL, event_type TEXT NOT NULL,
          detail TEXT, FOREIGN KEY(secret_id) REFERENCES secret_references(secret_id))""")

def _public(row):
    return {k: row[k] for k in ("secret_id","name","provider","reference","status","created_by","created_at","rotated_at","revoked_at","last_accessed_at","access_count")}

def _event(c, secret_id, actor, kind, detail=""):
    c.execute("INSERT INTO secret_events(secret_id,timestamp,actor,event_type,detail) VALUES(?,?,?,?,?)",(secret_id,utc_now(),actor,kind,redact(detail)))

def list_secrets():
    initialize_secret_manager()
    with sqlite3.connect(database_path) as c:
        c.row_factory=sqlite3.Row
        return [_public(r) for r in c.execute("SELECT * FROM secret_references ORDER BY created_at DESC")]

def create_secret(name, reference, actor, provider="ENVIRONMENT"):
    initialize_secret_manager(); name=name.strip(); reference=reference.strip()
    if not name or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", reference):
        raise ValueError("A name and uppercase environment-variable reference are required.")
    secret_id="sec_"+uuid.uuid4().hex; now=utc_now()
    try:
        with sqlite3.connect(database_path) as c:
            c.execute("INSERT INTO secret_references VALUES(?,?,?,?,?,?,?,?,?,?,?)",(secret_id,name,provider,reference,"ACTIVE",actor,now,None,None,None,0))
            _event(c,secret_id,actor,"SECRET_REFERENCE_CREATED","Metadata only; no secret value stored.")
    except sqlite3.IntegrityError as e: raise ValueError("A secret reference with this name already exists.") from e
    return get_secret(secret_id)

def get_secret(secret_id):
    with sqlite3.connect(database_path) as c:
        c.row_factory=sqlite3.Row; row=c.execute("SELECT * FROM secret_references WHERE secret_id=?",(secret_id,)).fetchone()
    if not row: raise KeyError("Secret reference not found.")
    return _public(row)

def resolve_secret(secret_id, actor):
    secret=get_secret(secret_id)
    if secret["status"]!="ACTIVE": raise ValueError("Secret reference is revoked.")
    value=os.getenv(secret["reference"])
    if value is None: raise ValueError("Referenced environment secret is unavailable.")
    with sqlite3.connect(database_path) as c:
        c.execute("UPDATE secret_references SET last_accessed_at=?,access_count=access_count+1 WHERE secret_id=?",(utc_now(),secret_id)); _event(c,secret_id,actor,"SECRET_RESOLVED","Value retrieved just in time and not persisted.")
    return value

def rotate_secret(secret_id, reference, actor):
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}",reference): raise ValueError("Invalid environment-variable reference.")
    get_secret(secret_id)
    with sqlite3.connect(database_path) as c:
        c.execute("UPDATE secret_references SET reference=?,status='ACTIVE',rotated_at=?,revoked_at=NULL WHERE secret_id=?",(reference,utc_now(),secret_id)); _event(c,secret_id,actor,"SECRET_REFERENCE_ROTATED","Reference changed; value never entered GreyGuard storage.")
    return get_secret(secret_id)

def revoke_secret(secret_id, actor):
    get_secret(secret_id)
    with sqlite3.connect(database_path) as c:
        c.execute("UPDATE secret_references SET status='REVOKED',revoked_at=? WHERE secret_id=?",(utc_now(),secret_id)); _event(c,secret_id,actor,"SECRET_REVOKED","Emergency revocation completed.")
    return get_secret(secret_id)

def redact(value):
    text=str(value)
    for key,val in os.environ.items():
        if val and len(val)>=8 and any(x in key.upper() for x in ("SECRET","TOKEN","PASSWORD","KEY","PIN")): text=text.replace(val,MASK)
    text=re.sub(r"(?i)(password|token|secret|api[_-]?key)\s*[:=]\s*[^\s,;]+",r"\1="+MASK,text)
    return text
