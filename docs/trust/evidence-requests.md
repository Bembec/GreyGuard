# Customer evidence requests

## Process: pending

The project owner will define who approves an evidence request and when an NDA is required (decision T8). Until then, requests go to the project owner case by case [TC-ER-1].

## Evidence that exists today

| Evidence | What it shows |
|---|---|
| CycloneDX SBOM | Every Python and JavaScript dependency of a release |
| Signed release manifest | Ed25519 signature over a release's version, commit and artifacts |
| Final security review report | Dependency, static-analysis, secret and image scan results, with any accepted risks |
| Threat and vulnerability register | Controls, residual risk and review dates for 30 threats |
| Tenant-isolation acceptance suite | The route-generated cross-organization tests and their results |
| An organization's own export and deletion certificate | Available to that organization, as described in [Privacy, retention and deletion](privacy-retention-deletion.md) |

Each exists in the repository or is produced by its scripts [TC-ER-2]. An independent penetration-test report does **not** exist yet [TC-CERT-2].
