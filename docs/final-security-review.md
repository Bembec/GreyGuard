# Final dependency and security review

GreyGuard's final technical-hardening gate combines Python and frontend dependency
audits, high-severity static analysis, a tracked-file secret scan, CycloneDX SBOM
generation and validation, and critical/high vulnerability scans of both production
container images.

Run `python scripts/run_final_security_review.py` after a successful production
rehearsal has rebuilt the local images. Evidence is written under `artifacts/`.
The Python dependency audit resolves `backend/requirements.txt`; it intentionally
does not audit unrelated packages installed globally on an administrator's PC.
Docker Desktop must be signed in so Docker Scout can analyze the local images.

## Container policy

The gate fails for every Critical or High vulnerability for which an upstream fix
exists. Each upstream-unfixed Critical or High finding is retained in the full scan
report and written individually to `accepted_risks` in
`artifacts/final-security-review.json`. Such exceptions expire after 30 days and
must be reviewed after every base-image rebuild. They are not permanent waivers.

Compensating controls are minimal runtime images, least-privilege containers,
network isolation, read-only runtime controls where supported, continuous scanning,
and prompt rebuilds when an upstream fix becomes available. A finding immediately
becomes release-blocking once Docker Scout identifies a fixed version.

The frontend uses the current explicit `nginx:1.31.6-alpine3.24-slim` runtime
rather than the obsolete Alpine 3.21 image. This removes most inherited packages
and the fixable vulnerabilities reported during the October 2026 review.

