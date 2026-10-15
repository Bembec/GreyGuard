# Customer evidence requests

## Process

Decided by the project owner (T8, 2026-10-15) [TC-ER-1]:

1. **Public evidence needs no approval and no NDA.** That means the Trust Center content and anything already public.
2. **Non-public or sensitive evidence needs approval** from a Platform Administrator or the designated security owner before it is shared.
3. **An NDA is required** when the evidence exposes any of these:
   - detailed architecture;
   - penetration-test findings;
   - sensitive controls;
   - customer-related information.
4. **Everything is audited.** Each request, approval or refusal, and disclosure is recorded with:
   - who asked, for what, and when;
   - the classification (public or sensitive) and whether an NDA applied, with its reference;
   - who approved or refused it;
   - what was disclosed, to whom, and when.

The product has no evidence-request feature; this is an operating process [TC-ER-1]. **The audit record must not be kept in the public source repository,** because it contains customer-related information.

## Evidence that exists today

| Evidence | What it shows | Classification |
|---|---|---|
| Trust Center pages and questionnaire answers | Statements tied to evidence | Public |
| CycloneDX SBOM | Every Python and JavaScript dependency of a release | Public |
| Signed release manifest | Ed25519 signature over a release's version, commit and artifacts | Public |
| Tenant-isolation acceptance suite | The route-generated cross-organization tests and their results | Public (in the source repository) |
| Final security review report | Dependency, static-analysis, secret and image scan results, with any accepted risks | Sensitive: approval and NDA (sensitive controls) |
| Threat and vulnerability register records | Controls, residual risk and review dates for 30 threats | Sensitive: approval and NDA (detailed architecture, sensitive controls) |
| Penetration-test report | Does not exist yet | Sensitive: approval and NDA (findings) |
| An organization's own export and deletion certificate | Its own data, as described in [Privacy, retention and deletion](privacy-retention-deletion.md) | Customer-related: to that organization only |

Each exists in the repository or is produced by its scripts [TC-ER-2]. An independent penetration-test report does **not** exist yet [TC-CERT-2].
