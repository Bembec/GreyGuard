# Pre-final hardening part 2

GreyGuard publishes API version `1` at `/api/version` and provides the first
explicitly versioned probe at `/api/v1/health`. Existing routes remain functional
to avoid breaking the dashboard, SDKs, and current integrations. Responses from
legacy unversioned routes carry deprecation, sunset, and migration-link headers.

`scripts/export_api_contract.py` creates a deterministic inventory of public
operations. A retained contract can be supplied with `--compare`; removal of a
previous operation fails the command and therefore the release gate.

`scripts/run_release_gate.py` runs backend tests, exports the API contract and
SBOM, then runs frontend tests and the production build. Evidence is written to
`artifacts/release-gate.json`.

## Clean production rehearsal

1. Use a clean Docker project name and test-only secrets.
2. Validate Compose configuration before starting containers.
3. Build without relying on development servers.
4. Confirm backend readiness and frontend health through the published port.
5. Confirm containers run read-only, without extra Linux capabilities.
6. Stop the rehearsal and remove its volumes.

Never use production credentials in rehearsal evidence. Run `pip-audit`, Bandit,
`npm audit --audit-level=high`, the SBOM generator, secret scanning, and container
scanning before a public release. Findings require documented remediation or a
time-limited risk acceptance; a successful scanner invocation is not itself proof
that the application is secure.
