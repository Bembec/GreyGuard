import asyncio
from backend.app.runtime_security import RuntimeSecurityMiddleware,readiness


def test_readiness_checks_database():
    assert readiness()["status"]=="ready"


def test_security_middleware_rejects_oversized_body():
    async def app(scope,receive,send): raise AssertionError("application must not run")
    sent=[]
    scope={"type":"http","headers":[(b"content-length",b"101")]}
    async def receive(): return {"type":"http.request","body":b""}
    async def send(message): sent.append(message)
    asyncio.run(RuntimeSecurityMiddleware(app,max_body_bytes=100)(scope,receive,send))
    assert sent[0]["status"]==413


def test_security_headers_are_added():
    async def app(scope,receive,send): await send({"type":"http.response.start","status":200,"headers":[]}); await send({"type":"http.response.body","body":b""})
    sent=[]
    async def receive(): return {"type":"http.request","body":b""}
    async def send(message): sent.append(message)
    asyncio.run(RuntimeSecurityMiddleware(app,production=True)({"type":"http","headers":[]},receive,send))
    headers=dict(sent[0]["headers"])
    assert headers[b"x-content-type-options"]==b"nosniff"
    assert b"strict-transport-security" in headers
