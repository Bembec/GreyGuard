# Deployment and operations — release and recovery controls

GreyGuard releases are built only from protected version tags. The release workflow publishes immutable image tags and GitHub build-provenance attestations for both backend and frontend images. Dependabot opens reviewed update pull requests for Python, npm, and GitHub Actions dependencies.

## Signed release evidence

Generate the SBOM first. Configure `GREYGUARD_RELEASE_SIGNING_KEY` as the URL-safe base64 encoding of a 32-byte Ed25519 private key stored outside the repository. Run `python scripts/create_release_manifest.py --version vX.Y.Z --commit FULL_GIT_SHA --verify`. Distribute the manifest, detached signature, SBOM, image digests, and provenance together. Never place the private signing key in CI logs or release artifacts.

## TLS and monitoring

`deployment/nginx-tls.conf` is a production template. Replace the example hostname and mount certificates from the approved certificate manager. It redirects HTTP to HTTPS, permits TLS 1.2/1.3, sets HSTS and security headers, and forwards the original protocol and client chain.

Run `python scripts/monitor_production.py --base-url https://greyguard.example.com/api` using a dedicated read-only `GREYGUARD_MONITOR_TOKEN`. Alert on any nonzero exit, repeated readiness failures, queue growth, authentication anomalies, audit-integrity failures, or high residual risks. Do not put monitoring tokens in command-line arguments.

## Disaster recovery

Run `python scripts/run_disaster_recovery_drill.py` during an approved exercise. The drill creates an encrypted backup, restores only to temporary storage, verifies integrity and table presence, reports an RTO rehearsal, and leaves the live database untouched. A real recovery additionally requires incident authorization, protected backup retrieval, secret rotation where indicated, post-restore application tests, and administrator notification.

## PostgreSQL completion gate

The operational controls in this package do not override the Part 1 migration gate. The production datastore remains SQLite until the dedicated compatibility package converts all direct SQLite calls, passes backend and cross-agent isolation tests against PostgreSQL, rehearses data migration, and proves rollback.
