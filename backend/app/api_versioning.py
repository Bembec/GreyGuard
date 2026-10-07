"""Stable API-version metadata, compatibility endpoints and /api/v1 routing."""

from datetime import date

from fastapi import FastAPI
from starlette.datastructures import MutableHeaders


API_VERSION = "1"
LEGACY_SUNSET = date(2028, 1, 1)
VERSION_PREFIX = "/api/v1"
# Routes defined natively under /api/v1 are served as-is; every other /api/v1/... path
# is an alias of the matching unversioned route.
NATIVE_VERSIONED_PATHS = frozenset({"/api/v1/health"})
UNDEPRECATED_PATHS = frozenset({"/docs", "/openapi.json", "/redoc", "/api/version"})


def install_api_versioning(app: FastAPI) -> None:
    """Expose version discovery while preserving all existing route paths."""

    @app.get("/api/version", tags=["Platform"])
    def api_version():
        return {
            "current": API_VERSION,
            "supported": [API_VERSION],
            "versioned_prefix": VERSION_PREFIX,
            "legacy_unversioned_routes_supported": True,
            "legacy_sunset": LEGACY_SUNSET.isoformat(),
        }

    @app.get("/api/v1/health", tags=["Platform"])
    def versioned_health():
        return {"status": "healthy", "api_version": API_VERSION}


class ApiVersionMiddleware:
    """Map /api/v1/<route> onto <route> and label every response with its API version.

    SECURITY: this must be the OUTERMOST middleware. Rate limiting, login lockout and
    role checks match on exact paths such as /auth/login; rewriting here, before they
    run, guarantees a versioned path can never bypass them.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        original = scope["path"]
        versioned = original == VERSION_PREFIX or original.startswith(VERSION_PREFIX + "/")
        if versioned and original not in NATIVE_VERSIONED_PATHS:
            canonical = original[len(VERSION_PREFIX):] or "/"
            scope = dict(scope, path=canonical, raw_path=canonical.encode("utf-8"))

        async def send_with_version_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-GreyGuard-API-Version"] = API_VERSION
                if versioned:
                    headers["Vary"] = "Accept, X-GreyGuard-API-Version"
                elif original not in UNDEPRECATED_PATHS:
                    headers["Deprecation"] = "true"
                    headers["Sunset"] = LEGACY_SUNSET.strftime("%a, %d %b %Y 00:00:00 GMT")
                    headers["Link"] = f'<{VERSION_PREFIX}>; rel="successor-version"'
            await send(message)

        await self.app(scope, receive, send_with_version_headers)
