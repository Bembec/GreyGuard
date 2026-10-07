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


## Docker Scout default-policy findings (accepted, documented)

GreyGuard's release gate fails on fixable Critical and High vulnerabilities. Docker Scout's
default policy set also reports two findings that are reviewed and accepted rather than fixed:

| Finding | Decision | Reason |
|---|---|---|
| Copyleft-licensed packages (GPL/LGPL/MPL) | Accepted | These are unmodified Alpine and Debian operating-system packages (for example busybox, musl utilities and CA certificates) inside the container base images. GreyGuard does not link to or modify them, and the official images are distributed under these terms by their maintainers. Reviewed with each base-image upgrade. |
| Missing supply-chain attestations on local images | Accepted for local builds | Provenance and SBOM attestations are attached by the signed release workflow when images are pushed to a registry. Locally built rehearsal images cannot carry registry attestations. The committed CycloneDX SBOM and signed release manifest provide the equivalent evidence. |

The former "image runs as root" finding is resolved: the frontend now runs as the unprivileged
`nginx` user with all Linux capabilities dropped, and the backend runs as the `greyguard` user.
