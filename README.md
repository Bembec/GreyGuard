# GreyGuard

**Secure • Monitor • Control** — a security control plane for AI agents.

GreyGuard sits between AI agents and the actions they take. Every agent has a registered
identity, hashed credentials and explicit scopes. Each tool request receives an **ALLOW**,
**ASK**, **BLOCK** or **REFUSED** decision; risk accumulates per agent until it is suspended
automatically; humans approve sensitive actions; and every step leaves tamper-evident evidence.

GreyGuard defends and contains. It never surveils, exploits or retaliates: prohibited
behaviours exist only as blocked, simulated scenarios in the non-operational simulation lab.

## Repository layout

| Path | Contents |
|---|---|
| `backend/app` | FastAPI control plane: policy engine, identity, approvals, audit, integrations |
| `backend/tests` | Backend test suite (pytest) |
| `backend/migrations` | Alembic migrations |
| `frontend` | React + TypeScript administrator console (Vite, Vitest, Playwright) |
| `sdk/python`, `sdk/javascript` | Agent SDKs with redaction, scope checks and idempotent requests |
| `deployment` | Dockerfiles, nginx (with and without TLS), sandbox profiles, Kubernetes job template |
| `scripts` | Release gate, security review, production rehearsal, migration and backup tooling |
| `docs` | Architecture, security, operations and integration documentation |
| `artifacts` | Committed evidence: SBOM, API contract, rehearsal and security-review results |
| `scripts/legacy` | Obsolete generators kept for history — **never run them** |

## Development

Requirements: Python 3.12+, Node.js 22, Docker Desktop (for rehearsals and scans).

```bash
python -m pip install -r backend/requirements-dev.txt
uvicorn backend.app.api:app --reload          # API on http://localhost:8000

cd frontend
npm ci
npm run dev                                    # console on http://localhost:5173
```

Copy `deployment/environments/development.env.example` for local settings. Development uses
SQLite; production requires PostgreSQL.

## Testing and release gates

```bash
python -m pytest backend/tests -q              # backend suite
cd frontend && npm run check                   # lint, Vitest and production build
cd frontend && npm run test:e2e                # Playwright end-to-end tests
python scripts/rehearse_production.py          # full production stack on a clean machine
python scripts/run_final_security_review.py    # dependency, static, secret, SBOM and container gates
```

The security gate fails on any fixable Critical or High vulnerability. Upstream findings with
no fix receive a recorded 30-day exception (`docs/final-security-review.md`).

## Production deployment

Production runs with `docker-compose.production.yml`: PostgreSQL 17, a non-root backend and a
non-root nginx frontend with all Linux capabilities dropped, read-only filesystems and strict
security headers. Production refuses to start with development settings, wildcard origins or
the shared development PIN. See `docs/production-deployment.md` and `docs/operations-runbook.md`.

## API

Every route is available under the versioned prefix `/api/v1/...`. Unversioned routes keep
working and carry `Deprecation` and `Sunset` headers. `GET /api/version` reports supported
versions.

## Status

Phase A (pre-final hardening) and the Stage 1 security corrections are complete and evidenced
in `artifacts/`. The master roadmap records the item-by-item status of every section,
including known gaps. Notable work still to come:

- Enterprise single sign-on flow (OIDC providers can be configured; the sign-in flow is not built)
- Outbound delivery worker for SIEM exports, notifications and incident tickets (currently queued only)
- Branded application experience, commercial foundation, full documentation set and final acceptance

## Security

Please report vulnerabilities as described in `SECURITY.md`.
