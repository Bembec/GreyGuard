# GreyGuard Trust Center (source content)

**Status: internal source content, not published.** These pages are the reviewed source for a future public Trust Center. Publication waits for the separate public site (P7) and claim governance (P8), per P6 decision T2 in [`../roadmap/p6-decision-package.md`](../roadmap/p6-decision-package.md). Nothing here is a legal conclusion, a certification or a contractual commitment.

## Rules for this content

1. **Every statement carries an ID** such as `[TC-DP-4]`. The [source register](source-register.md) lists each ID with its evidence, an owner and the date it was last reviewed against that evidence.
2. **Evidence is a file or test in this repository.** A statement without evidence is not made. `backend/tests/test_trust_center.py` fails if a page uses an ID the register lacks, if the register lists an ID no page uses, or if a cited path does not exist.
3. **Gaps are stated, not hidden.** Where GreyGuard does not provide something, the page says so and says who is responsible instead.
4. **To change a statement, change the register first,** then the page, and re-review the evidence.

## Pages

| Page | Covers |
|---|---|
| [Security overview](security-overview.md) | Architecture, trust boundaries, data flow, deployment models |
| [Data protection](data-protection.md) | Encryption in transit and at rest, credentials, secrets, signing keys |
| [Identity and access](identity-and-access.md) | Administrator and agent authentication, roles, tenant isolation |
| [Secure development](secure-development.md) | CI, scanning, SBOM, signed releases, current pipeline status |
| [Availability and recovery](availability-and-recovery.md) | HA limits, failure modes, backups, disaster recovery |
| [Privacy, retention and deletion](privacy-retention-deletion.md) | Analytics, audit retention, export, offboarding, deletion |
| [Subprocessors and external services](subprocessors.md) | What the software contacts; hosted-service vendors |
| [Vulnerability disclosure](vulnerability-disclosure.md) | How to report a vulnerability; security.txt |
| [Certifications and assessments](certifications.md) | What is and is not held |
| [Customer evidence requests](evidence-requests.md) | What evidence exists and how requests are handled |
| [Source register](source-register.md) | Every statement, its evidence, owner and review date |

## Open owner decisions that these pages depend on

| Decision | Affects | Status |
|---|---|---|
| T3: monitored security contact | security.txt, vulnerability disclosure | Awaiting the project owner |
| T5: independent penetration test before the first paid pilot | Certifications and assessments | Approved; not yet commissioned |
| T6: hosting, email and support vendors for the hosted offering | Subprocessors | Awaiting the project owner |
| T7: legal documents by qualified counsel | Terms, Privacy Notice, DPA and others | Approved; counsel not yet engaged |
| T8: evidence-request approver and NDA rule | Customer evidence requests | Awaiting the project owner |
