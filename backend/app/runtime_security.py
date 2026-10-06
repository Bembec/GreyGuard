"""Production HTTP hardening and readiness checks."""
from __future__ import annotations
from . import db_compat as sqlite3
from starlette.responses import JSONResponse
from .database import database_path

SECURITY_HEADERS={
    "X-Content-Type-Options":"nosniff",
    "X-Frame-Options":"DENY",
    "Referrer-Policy":"no-referrer",
    "Permissions-Policy":"camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy":"same-origin",
    "Cross-Origin-Resource-Policy":"same-site",
    "Content-Security-Policy":"default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
}


class RuntimeSecurityMiddleware:
    def __init__(self, app, max_body_bytes=2_097_152, production=False):
        self.app=app; self.max_body_bytes=max_body_bytes; self.production=production

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http": return await self.app(scope,receive,send)
        headers=dict(scope.get("headers",[])); length=headers.get(b"content-length")
        if length:
            try: too_large=int(length)>self.max_body_bytes
            except ValueError: too_large=True
            if too_large: return await JSONResponse({"detail":"Request body exceeds the permitted size."},status_code=413)(scope,receive,send)
        async def secured(message):
            if message["type"]=="http.response.start":
                existing=list(message.get("headers",[]))
                existing.extend((name.lower().encode(),value.encode()) for name,value in SECURITY_HEADERS.items())
                if self.production: existing.append((b"strict-transport-security",b"max-age=31536000; includeSubDomains"))
                message["headers"]=existing
            await send(message)
        await self.app(scope,receive,secured)


def readiness():
    checks={"database":False}
    try:
        with sqlite3.connect(database_path) as connection:
            checks["database"]=connection.execute("SELECT 1").fetchone()[0]==1
    except sqlite3.Error:
        pass
    return {"status":"ready" if all(checks.values()) else "not_ready","checks":checks}
