"""Secret references, just-in-time retrieval, redaction, and revocation."""
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from .database import database_path
from .secret_providers import resolve as resolve_provider_secret, validate_reference

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
        columns={row[1] for row in c.execute("PRAGMA table_info(secret_references)")}
        if "rotation_interval_days" not in columns: c.execute("ALTER TABLE secret_references ADD COLUMN rotation_interval_days INTEGER")
        if "next_rotation_at" not in columns: c.execute("ALTER TABLE secret_references ADD COLUMN next_rotation_at TEXT")

def _public(row):
    return {k: row[k] for k in ("secret_id","name","provider","reference","status","created_by","created_at","rotated_at","revoked_at","last_accessed_at","access_count","rotation_interval_days","next_rotation_at")}

def _event(c, secret_id, actor, kind, detail=""):
    c.execute("INSERT INTO secret_events(secret_id,timestamp,actor,event_type,detail) VALUES(?,?,?,?,?)",(secret_id,utc_now(),actor,kind,redact(detail)))

def list_secrets():
    initialize_secret_manager()
    with sqlite3.connect(database_path) as c:
        c.row_factory=sqlite3.Row
        return [_public(r) for r in c.execute("SELECT * FROM secret_references ORDER BY created_at DESC")]

def create_secret(name, reference, actor, provider="ENVIRONMENT", rotation_interval_days=None):
    initialize_secret_manager(); name=name.strip(); reference=reference.strip()
    provider=provider.upper()
    if not name: raise ValueError("A secret name is required.")
    validate_reference(provider,reference)
    if rotation_interval_days is not None and not 1 <= rotation_interval_days <= 365:
        raise ValueError("Rotation interval must be from 1 to 365 days.")
    secret_id="sec_"+uuid.uuid4().hex; now=utc_now()
    next_rotation=(datetime.now(timezone.utc)+timedelta(days=rotation_interval_days)).isoformat() if rotation_interval_days else None
    try:
        with sqlite3.connect(database_path) as c:
            c.execute("""INSERT INTO secret_references
            (secret_id,name,provider,reference,status,created_by,created_at,rotated_at,revoked_at,last_accessed_at,access_count,rotation_interval_days,next_rotation_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",(secret_id,name,provider,reference,"ACTIVE",actor,now,None,None,None,0,rotation_interval_days,next_rotation))
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
    value=resolve_provider_secret(secret["provider"],secret["reference"])
    with sqlite3.connect(database_path) as c:
        c.execute("UPDATE secret_references SET last_accessed_at=?,access_count=access_count+1 WHERE secret_id=?",(utc_now(),secret_id)); _event(c,secret_id,actor,"SECRET_RESOLVED","Value retrieved just in time and not persisted.")
    return value

def rotate_secret(secret_id, reference, actor):
    secret=get_secret(secret_id); validate_reference(secret["provider"],reference)
    next_rotation=(datetime.now(timezone.utc)+timedelta(days=secret["rotation_interval_days"])).isoformat() if secret["rotation_interval_days"] else None
    with sqlite3.connect(database_path) as c:
        c.execute("UPDATE secret_references SET reference=?,status='ACTIVE',rotated_at=?,revoked_at=NULL,next_rotation_at=? WHERE secret_id=?",(reference,utc_now(),next_rotation,secret_id)); _event(c,secret_id,actor,"SECRET_REFERENCE_ROTATED","Reference changed; value never entered GreyGuard storage.")
    return get_secret(secret_id)

def revoke_secret(secret_id, actor):
    get_secret(secret_id)
    with sqlite3.connect(database_path) as c:
        c.execute("UPDATE secret_references SET status='REVOKED',revoked_at=? WHERE secret_id=?",(utc_now(),secret_id)); _event(c,secret_id,actor,"SECRET_REVOKED","Emergency revocation completed.")
    return get_secret(secret_id)

def emergency_revoke_all(actor, provider=None):
    initialize_secret_manager(); now=utc_now(); provider=provider.upper() if provider else None
    with sqlite3.connect(database_path) as c:
        c.row_factory=sqlite3.Row
        query="SELECT secret_id FROM secret_references WHERE status='ACTIVE'"; params=[]
        if provider: query+=" AND provider=?"; params.append(provider)
        rows=c.execute(query,params).fetchall()
        for row in rows:
            c.execute("UPDATE secret_references SET status='REVOKED',revoked_at=? WHERE secret_id=?",(now,row["secret_id"])); _event(c,row["secret_id"],actor,"EMERGENCY_SECRET_REVOCATION","Provider scope revoked immediately.")
    return {"revoked":len(rows),"provider":provider or "ALL","values_exposed":False}

def secret_events(secret_id=None, limit=200):
    initialize_secret_manager()
    with sqlite3.connect(database_path) as c:
        c.row_factory=sqlite3.Row
        if secret_id:
            rows=c.execute("SELECT * FROM secret_events WHERE secret_id=? ORDER BY event_id DESC LIMIT ?",(secret_id,limit)).fetchall()
        else:
            rows=c.execute("SELECT * FROM secret_events ORDER BY event_id DESC LIMIT ?",(limit,)).fetchall()
    return [dict(row) for row in rows]

def redact(value):
    text=str(value)
    for key,val in os.environ.items():
        if val and len(val)>=8 and any(x in key.upper() for x in ("SECRET","TOKEN","PASSWORD","KEY","PIN")): text=text.replace(val,MASK)
    text=re.sub(r"(?i)(password|token|secret|api[_-]?key)\s*[:=]\s*[^\s,;]+",r"\1="+MASK,text)
    return text

class SecretRedactionMiddleware:
    """Redact configured secret values from non-streaming textual responses."""
    def __init__(self,app): self.app=app
    async def __call__(self,scope,receive,send):
        if scope["type"]!="http": return await self.app(scope,receive,send)
        start=None; chunks=[]; passthrough=False
        async def capture(message):
            nonlocal start,passthrough
            if message["type"]=="http.response.start":
                start=message
                headers=dict(message.get("headers",[]))
                content_type=headers.get(b"content-type",b"").lower()
                textual=any(kind in content_type for kind in (b"text/",b"json",b"xml",b"javascript"))
                passthrough=(b"text/event-stream" in content_type) or not textual
                if passthrough: await send(message)
            elif message["type"]=="http.response.body":
                if passthrough: await send(message); return
                chunks.append(message.get("body",b""))
                if not message.get("more_body",False):
                    body=redact(b"".join(chunks).decode("utf-8",errors="replace")).encode()
                    headers=[(k,v) for k,v in start.get("headers",[]) if k.lower()!=b"content-length"]
                    headers.append((b"content-length",str(len(body)).encode())); start["headers"]=headers
                    await send(start); await send({"type":"http.response.body","body":body,"more_body":False})
        await self.app(scope,receive,capture)
