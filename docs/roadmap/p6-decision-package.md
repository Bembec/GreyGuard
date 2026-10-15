# P6 decision package — Vendor trust and procurement readiness

**Status: prepared for approval; not started.** The addendum requires Michael's approval before each major workstream begins, and before any legal or compliance claim is made. This package scopes P6 against the evidence that exists in this repository today, so that the approval covers a defined piece of work. Nothing here is published, and nothing here is a legal conclusion.

## Decision record

| # | Decision | Recommendation | Why |
|---|---|---|---|
| T1 | Start P6 now | **Yes, engineering-scoped only** (sections 2 and 3). | P1–P5 are verified. The remaining P4 items (D3 fee, D6 values, D10 candidates) don't block trust content. |
| T2 | Where the Trust Center lives | **Source content in this repository now; publish it with the P7 public site.** | P7 is gated and deferred. Writing the content first lets every statement be reviewed against evidence before anything is public. |
| T3 | `security.txt` contact | **Owner to supply** a monitored security contact (a mailbox or the GitHub Security Advisories URL). | RFC 9116 requires a `Contact` and an `Expires`. I will not invent an address. |
| T4 | Questionnaire format | **Build an evidence-linked answer bank first**, then map it to CAIQ or SIG Lite when a buyer asks for one. | Answers keyed to repository evidence stay accurate as the product changes; a form-specific pack can be produced from them. |
| T5 | Independent penetration test | **Owner decision: commission one before the first paid pilot.** | None has been done. The threat register says it doesn't replace one (`docs/threat-and-vulnerability-register.md`). The Trust Center will say "not yet performed" until a report exists. |
| T6 | Subprocessor register | **Owner to supply** the hosting, email and support vendors for the hosted offering (D9). | These are business choices that haven't been made. Engineering can list what the software itself contacts. Customer-configured destinations (SIEM, ticketing, chat) are the customer's own systems, not GreyGuard subprocessors. |
| T7 | Legal documents | **Qualified counsel**, tracked in a legal-document register (owner, reviewer, status). | Terms, Privacy Notice, DPA, AUP, support terms, pilot agreement, order form, licensing and incident-notification terms are explicitly outside engineering in the addendum. |
| T8 | Customer evidence requests | **Owner to define** who approves a request and when an NDA is required. Engineering documents the process and what evidence exists. | It is a commercial and legal process, not a product feature. |

## 1. Trust Center items against the evidence that exists

| Addendum item | Evidence today | Status |
|---|---|---|
| Security overview and architecture | `docs/final-security-review.md`, `assurance/threat-model.md`, `docs/deployment-models.md` | **Ready to assemble** |
| Data flow and deployment boundaries | `docs/deployment-models.md`, `docs/gateway-distribution.md`, `docs/controlled-execution-isolation.md` | **Ready to assemble**; needs one data-flow diagram |
| Encryption and key management | TLS (`deployment/nginx-tls.conf`); AES-256-GCM encrypted backups with an externally held key (`docs/deployment-operations-part1.md`); secret-manager integrations (`docs/secret-management-integrations.md`) | **Partial.** In the docs I checked, encryption of live data at rest is not provided by GreyGuard itself and depends on the host's disk or database. It must be stated that way. |
| Authentication, authorization, tenant isolation | `docs/enterprise-identity.md`, `docs/enterprise-session-security.md`, `docs/agent-certificate-authentication.md`; P2 tenant-scoping sweep and acceptance suite | **Ready to assemble** |
| Secure development and vulnerability management | `docs/supply-chain-security.md` (pip-audit, npm audit, Bandit, CodeQL, Gitleaks, Trivy, CycloneDX SBOM, release-blocking findings), `SECURITY.md` | **Ready to assemble** |
| Penetration-test summary | None | **Not performed** (T5) |
| Availability, backup and disaster recovery | `docs/reliability.md` (single host, **not HA**), `docs/deployment-operations-part2.md` (DR drill), `assurance/recovery-exercises.md`, status page | **Ready to assemble, with honest limits.** No HA and no committed RPO/RTO figures. |
| Privacy, retention and deletion | `docs/audit-integrity-and-retention.md`, `docs/organization-lifecycle.md` (ACTIVE → OFFBOARDING → DELETED, export never withheld), `docs/product-analytics.md` (counts only, opt-out deletes) | **Ready to assemble**; the Privacy Notice itself is legal (T7) |
| Subprocessor register | None | **Blocked on T6** |
| Responsible disclosure and `security.txt` | `SECURITY.md` (private GitHub advisories, 5-business-day acknowledgement) | **Small build, blocked on T3** |
| Certifications and audits | None. SOC 2, ISO 27001 and insurance are later gated programmes per the addendum. | **State "none held" honestly** |
| Questionnaire responses | Source material above | **Build per T4** |
| Customer evidence-request process | None | **Blocked on T8** |

## 2. Proposed engineering scope, if approved

1. **Trust Center source content** (`docs/trust/`): one page per item in section 1. Every statement cites its source file or test, and every gap is stated plainly.
2. **Trust Center source register:** each public statement, its evidence, an owner and a last-reviewed date (also a P10 item). Content is updated only by changing the register.
3. **`security.txt`** served at `/.well-known/security.txt` by the frontend nginx, with a test that it is present, unexpired and in the right format. Requires T3.
4. **Questionnaire answer bank:** short, evidence-linked answers grouped by common control domains, each with a "not provided / customer responsibility" option rather than an overstatement.
5. **Legal-document register:** names and status only (all "not started" until counsel engages), with no drafted legal text.
6. **Data-flow diagram** for the hosted deployment boundary.

Verification follows the usual bar for anything that touches code (nginx config and its test). Content is reviewed against its cited sources before commit.

## 3. Explicitly out of scope

- Publishing anything (P7) and any public claim (P8 claim governance).
- Legal drafting, certification work, insurance and regional hosting.
- Inventing vendors, contacts, figures (RPO, RTO, uptime) or test results.
