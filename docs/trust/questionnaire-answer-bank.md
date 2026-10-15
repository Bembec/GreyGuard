# Security questionnaire answer bank

Short answers to the questions that buyer security questionnaires usually ask, grouped by control domain. Each answer cites the Trust Center statements it rests on, so it stays as accurate as the [source register](source-register.md). Per decision T4, a form-specific pack (CAIQ, SIG Lite or a buyer's own) is produced from this bank when a buyer asks for one. Nothing is copied into a form without re-checking the cited statements.

**Answer values.** *Yes*: provided as described. *Partial*: provided with the stated limits. *No*: not provided. *Customer*: the customer's or the operator's responsibility. *Owner to answer*: a business answer the project owner has not given yet. Every answer other than *Owner to answer* cites at least one statement.

## Governance and assurance

| # | Question | Answer | Detail | Statements |
|---|---|---|---|---|
| G1 | Do you hold SOC 2, ISO 27001 or similar? | No | None held or claimed; later, separately approved programmes. | [TC-CERT-1] |
| G2 | Has an independent penetration test been performed? | No | To be commissioned before the first paid pilot. | [TC-CERT-2] |
| G3 | Do you maintain a threat or risk register? | Yes | 30 threats with controls, residual risk, owner and review date. | [TC-ARCH-8] |
| G4 | Do you have documented information-security policies and a named security owner? | Owner to answer | | |
| G5 | Do you carry cyber insurance? | No | Not claimed. | [TC-CERT-1] |

## Personnel

| # | Question | Answer | Detail | Statements |
|---|---|---|---|---|
| P1 | Are staff background-checked, trained in security and bound by confidentiality? | Owner to answer | | |

## Data protection and cryptography

| # | Question | Answer | Detail | Statements |
|---|---|---|---|---|
| D1 | Is data encrypted in transit? | Partial | TLS 1.2/1.3 with HSTS at the operator's proxy, from a provided template; the shipped image itself serves HTTP on loopback only. Outbound deliveries are HTTPS-only. | [TC-DP-1] [TC-DP-3] |
| D2 | Is data encrypted at rest? | Customer | GreyGuard does not encrypt the live database; disk, volume or managed-database encryption is the operator's. | [TC-DP-4] |
| D3 | Are backups encrypted? | Customer | Production backups are verified but not encrypted by GreyGuard; the operator encrypts and access-controls them. | [TC-DP-5] |
| D4 | How are passwords and credentials stored? | Yes | PBKDF2-SHA256 (310,000 iterations) for passwords and agent keys; SHA-256 hashes for tokens. TOTP seeds are stored unencrypted and redacted from exports. | [TC-DP-6] [TC-DP-7] |
| D5 | How are third-party secrets handled? | Yes | Stored as references to a secret manager and resolved just in time; values are never stored. | [TC-DP-8] |
| D6 | Do you support customer-managed keys? | No | Not implemented or offered. | [TC-DP-9] |
| D7 | Are secrets kept out of logs and telemetry? | Yes | Redacted before logging, retention, display or export. | [TC-DP-10] |

## Identity and access

| # | Question | Answer | Detail | Statements |
|---|---|---|---|---|
| A1 | Do you support SSO? | Yes | OIDC with PKCE: Entra ID, Okta, Auth0 and compatible providers. | [TC-IAM-1] |
| A2 | Is MFA supported and enforced? | Partial | TOTP for every account, enforced once enabled; not enforced install-wide. | [TC-IAM-3] |
| A3 | Is access role-based? | Yes | Platform Administrator, Security Analyst, Auditor. | [TC-IAM-4] |
| A4 | How are sessions managed? | Yes | 15-minute access tokens; rotating 7-day refresh tokens with reuse detection. | [TC-IAM-2] |
| A5 | Is privileged access controlled? | Yes | Elevation needs a second administrator; break-glass is restricted, reasoned, expiring and recorded. | [TC-IAM-5] |
| A6 | How is one customer's data isolated from another's? | Yes | Every org-scoped query is guarded, and a route-generated acceptance suite tests every route. | [TC-IAM-7] [TC-IAM-8] |
| A7 | How are machine identities authenticated? | Yes | Hashed agent keys, or optional proxy-verified mTLS. | [TC-DP-6] [TC-IAM-6] |

## Application and infrastructure security

| # | Question | Answer | Detail | Statements |
|---|---|---|---|---|
| S1 | Describe the architecture and network segmentation. | Yes | Three containers; backend on an internal-only network, reachable only through the frontend. | [TC-ARCH-1] [TC-ARCH-3] |
| S2 | Are containers hardened? | Yes | Non-root users, all capabilities dropped, read-only root filesystems. | [TC-ARCH-2] |
| S3 | Are web security headers set? | Yes | CSP, frame, content-type, referrer and permissions policies. | [TC-DP-2] |
| S4 | Is server-side request forgery prevented? | Yes | HTTPS-only, address-pinned outbound requests; internal and metadata addresses refused. | [TC-DP-3] |
| S5 | Does the system fail safely? | Yes | Actions are denied when the database or the control plane is unavailable. | [TC-ARCH-5] [TC-ARCH-6] [TC-AV-3] |

## Secure development and vulnerability management

| # | Question | Answer | Detail | Statements |
|---|---|---|---|---|
| V1 | Is code tested and scanned before release? | Yes | Test suites and builds on every pull request; dependency, static, secret and vulnerability scans. | [TC-SDL-1] [TC-SDL-2] |
| V2 | Are those scans currently passing? | Partial | Three jobs failed on 2026-10-12. The causes are fixed and pass locally; confirmation on GitHub is pending. | [TC-SDL-3] |
| V3 | How are vulnerabilities in releases handled? | Yes | Fixable critical and high findings block release; unfixed ones expire after 30 days. | [TC-SDL-4] |
| V4 | Do you provide an SBOM and signed releases? | Yes | CycloneDX SBOM; Ed25519-signed release manifest; build provenance. | [TC-SDL-5] |
| V5 | Are dependencies kept up to date? | Yes | Dependabot update pull requests. | [TC-SDL-6] |
| V6 | Do you have a vulnerability-disclosure process? | Yes | Private reports via GitHub Security Advisories; security.txt pending a contact. | [TC-VD-1] [TC-VD-2] |

## Logging and incident response

| # | Question | Answer | Detail | Statements |
|---|---|---|---|---|
| L1 | Are security-relevant events logged and tamper-evident? | Yes | SHA-256 hash-chained audit evidence; erasures recorded. | [TC-PR-3] |
| L2 | Do you have an incident response plan? | Partial | An operations runbook covers readiness failures, evidence preservation, restore and rollback. There is no formal security-incident response plan. | [TC-IR-1] |
| L3 | Will you notify customers of a security incident, and within what time? | Owner to answer | Incident-notification terms are a legal document (T7). | |

## Availability and continuity

| # | Question | Answer | Detail | Statements |
|---|---|---|---|---|
| B1 | What is your uptime SLA? | No | No SLA is published. | [TC-AV-1] |
| B2 | Is the service highly available? | No | Single host; multi-host HA is remaining work. | [TC-AV-2] |
| B3 | What are your RPO and RTO? | No | None committed. | [TC-AV-1] |
| B4 | Are backups taken and restores tested? | Partial | Verified whole-install backups; the scripted DR drill covers only SQLite. | [TC-AV-4] [TC-AV-5] |
| B5 | Where is data stored? | Yes | In the install's region, without cross-region replication. | [TC-AV-7] |

## Privacy and data lifecycle

| # | Question | Answer | Detail | Statements |
|---|---|---|---|---|
| R1 | What product analytics do you collect? | Yes | Counts only, plus one fixed-path page-view count; no content; can be turned off. | [TC-PR-1] [TC-PR-2] |
| R2 | How long is data retained? | Yes | Audit evidence 365 days by default; legal holds supported. | [TC-PR-3] |
| R3 | Can we export our data? | Yes | At any time before deletion, with digests and redacted credentials. | [TC-PR-4] |
| R4 | How is data deleted at contract end? | Yes | Offboarding, then gated deletion with a verifiable certificate; backups age out. | [TC-PR-5] [TC-PR-6] |
| R5 | Will you sign a DPA? | Owner to answer | A legal document (T7). | |

## Third parties

| # | Question | Answer | Detail | Statements |
|---|---|---|---|---|
| T1 | Which subprocessors do you use? | Owner to answer | Hosted-offering vendors are not yet chosen (T6). The software itself has no built-in destination. | [TC-SUB-1] [TC-SUB-5] |
| T2 | Does the software send data to third parties? | No | Only to endpoints the operator or customer configures. | [TC-SUB-1] [TC-SUB-2] |
| T3 | Do you store payment card data? | No | No payment processor is integrated, and card data is never stored. | [TC-SUB-3] |
