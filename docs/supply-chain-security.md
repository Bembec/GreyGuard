# Supply-chain and release assurance

GreyGuard Section 12 Part 2 adds browser smoke tests, dependency auditing, static analysis, secret scanning, container scanning, SBOM generation, threat and abuse-case reviews, and operational recovery exercises.

CI uses pip-audit and npm audit for dependency findings, Bandit and CodeQL for static analysis, Gitleaks for committed-secret detection, Trivy for container/filesystem findings, and a CycloneDX JSON inventory generated from locked Python and JavaScript dependencies. High or critical findings block release unless an owner records a time-limited, reviewed exception.

Run `python scripts/generate_sbom.py`, `python scripts/run_operational_assurance.py`, and from `frontend`, `npm run build` followed by `npm run test:e2e`. The E2E suite uses synthetic unauthenticated routes and never production credentials.

Backup restoration, kill-switch, and disaster-recovery exercises must occur in a test environment. Preserve evidence and document recovery time, recovery point, failures, owners, and corrective actions.
