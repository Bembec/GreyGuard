"""Stable API-version metadata and compatibility endpoints."""

from datetime import date

from fastapi import FastAPI


API_VERSION = "1"
LEGACY_SUNSET = date(2028, 1, 1)


def install_api_versioning(app: FastAPI) -> None:
    """Expose version discovery while preserving all existing route paths."""

    @app.get("/api/version", tags=["Platform"])
    def api_version():
        return {
            "current": API_VERSION,
            "supported": [API_VERSION],
            "legacy_unversioned_routes_supported": True,
            "legacy_sunset": LEGACY_SUNSET.isoformat(),
        }

    @app.get("/api/v1/health", tags=["Platform"])
    def versioned_health():
        return {"status": "healthy", "api_version": API_VERSION}

    @app.middleware("http")
    async def api_version_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-GreyGuard-API-Version"] = API_VERSION
        if request.url.path.startswith("/api/v1/"):
            response.headers["Vary"] = "Accept, X-GreyGuard-API-Version"
        elif request.url.path not in {"/docs", "/openapi.json", "/redoc"}:
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = LEGACY_SUNSET.strftime("%a, %d %b %Y 00:00:00 GMT")
            response.headers["Link"] = '</api/version>; rel="deprecation"'
        return response

