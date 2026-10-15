# Secure development

## Continuous checks

- **On every pull request and every push to `main`:** the full backend test suite, the frontend unit tests and build, and a build of the production container images [TC-SDL-1].
- **Security checks, on pull requests and weekly** [TC-SDL-2]:
  - dependency audits: `pip-audit` for Python, `npm audit` at high severity for the frontend;
  - static analysis: Bandit at medium severity and above, and CodeQL for Python and TypeScript;
  - secret scanning: Gitleaks;
  - vulnerability and secret scanning of the repository: Trivy, failing on high and critical findings;
  - a CycloneDX software bill of materials (SBOM);
  - browser end-to-end tests.

## Current status of those checks

**Stated plainly because a reviewer can check it.** The scheduled security run on 2026-10-12 failed in three jobs [TC-SDL-3]:

- **Bandit** reported 40 medium-severity "SQL built from strings" findings. Each was traced: the interpolated part is always a code constant or a fixed allowlist of table names, and every value is a bound parameter. Each is now marked with its reason, and a new unmarked case still fails the check.
- **Gitleaks** reported two findings: a deliberately fake token in a test of GreyGuard's own secret scanner, and a placeholder in the example environment file. Both are listed as false positives by fingerprint. No real secret was found.
- **Trivy** did not run, because the pinned action version no longer existed upstream. The action is now pinned to a commit SHA.

All five jobs pass locally after the fix. Passing on GitHub is to be confirmed by the next run, and this section is updated when it does.

## Release assurance

- **Final security review gate.** It combines dependency audits, static analysis, a secret scan, SBOM validation and a vulnerability scan of both production images. Any critical or high vulnerability with an upstream fix blocks release. An unfixed one is recorded individually as an accepted risk that expires after 30 days [TC-SDL-4].
- **Signed releases.** Releases are built only from protected version tags, with image build-provenance attestations. A release manifest is signed with Ed25519 and distributed with the SBOM and image digests [TC-SDL-5].
- **Dependency updates.** Dependabot opens update pull requests for Python, npm and GitHub Actions dependencies [TC-SDL-6].
- **Hardened containers.** Both production images run as non-root users with all capabilities dropped [TC-ARCH-2].

## Independent testing

**No independent penetration test has been performed.** The project owner has decided to commission one before the first paid pilot (decision T5) [TC-CERT-2].
