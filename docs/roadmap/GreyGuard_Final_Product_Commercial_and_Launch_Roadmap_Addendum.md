# GreyGuard Final Product, Commercial and Launch Roadmap Addendum

## Purpose

This addendum closes the product, commercial, trust, deployment and launch gaps that are not fully covered by GreyGuard's engineering roadmap. It deliberately keeps GreyGuard narrower than Evravo: GreyGuard is the security control plane for AI agents, tools and consequential actions. It is not a general AI inventory, model-governance or regulatory-lifecycle platform.

Nothing here weakens the existing security roadmap. All existing backend controls, tests, routes, evidence, rollback requirements and prohibited-capability boundaries remain mandatory.

## Product boundary and positioning

GreyGuard registers and authenticates AI agents, restricts their permissions, evaluates tool requests, requires human approval where necessary, accumulates risk, suspends unsafe agents, coordinates defensive containment and preserves tamper-evident evidence.

The commercial message must be based on verified capabilities:

- Know which agent is acting.
- Control which tools, targets and data it may use.
- Require approval for consequential actions.
- Detect abnormal or prohibited requests.
- Contain unsafe agents and integrations.
- Prove what happened with verifiable evidence.

Every public claim must be labelled as enforced, observed, advisory, simulated, preview or planned. GreyGuard must never claim visibility or enforcement over an unconnected agent or environment.

## Working buyer-facing product groups

These are working labels subject to buyer testing and trademark review. They group existing capabilities for buyers; they do not replace internal modules or routes.

1. **GreyGuard Gate** — agent identity, scopes, tool gateway, ALLOW/ASK/BLOCK/REFUSED decisions, human approval, policy enforcement and emergency deny.
2. **GreyGuard Watch** — Live Operations, agent risk, alerts, telemetry, investigation, threat register and defensive integration health.
3. **GreyGuard Respond** — suspension, incident workflows, controlled isolation, credential revocation, integration disablement, recoverable containment and rollback.
4. **GreyGuard Evidence** — tamper-evident audit history, decision receipts, compliance reports, exports, retention, integrity verification and executive/auditor evidence.

Mandatory identity, authorization, redaction, evidence, emergency stop and basic recovery controls must exist in every edition. Billing or plan limits must never remove a protection required for safe operation.

## Environment and coverage model

GreyGuard must show coverage honestly by agent connection method:

- GreyGuard SDK-managed agents.
- Framework adapters such as LangChain, LangGraph, CrewAI and AutoGen where implemented.
- MCP-connected agents and servers.
- Generic API or webhook agents.
- Customer-hosted gateways or enforcement nodes.
- Monitor-only integrations.
- Unconnected or unsupported agents, explicitly shown as outside enforcement.

The UI and public material must distinguish registered, connected, observed, policy-enforced, tested and currently healthy. Registration alone must never be shown as runtime protection.

## Commercial editions

Names remain working labels until buyer validation.

### Foundation

For small teams starting controlled AI-agent adoption. Includes core agent registry, Gate controls, standard policies, approvals, basic Watch views, decision evidence, API/SDK access and business-hours documentation support. Target deployment: hosted or self-hosted starter profile.

### Enterprise

For organizations running production agents. Includes all verified product groups, enterprise SSO, advanced integrations, SIEM and incident delivery, extended reports, organization controls, priority support, customer-hosted enforcement nodes and defined response targets.

### Dedicated

For regulated or isolation-sensitive organizations. Includes Enterprise capabilities plus dedicated tenancy or customer-cloud deployment, selected region, customer-managed keys where verified, private connectivity, extended retention and separately agreed maintenance windows.

Edition rules:

- Meter agents, controlled requests, delivery volume, storage and integrations using documented units.
- Reviewers, auditors and read-only participants should not be priced in a way that discourages oversight.
- Enforce entitlements in the backend and workers, never only in the UI.
- On payment failure, preserve access to export, evidence, security controls and safe offboarding according to documented policy.
- Do not use "sovereign," "compliant" or certification labels until their exact conditions are independently verified.

## Final workstream order

### P0 — Finish current security milestones

Complete and independently review secure outbound delivery, enterprise OIDC, certificate-based agent authentication, credential history and artifact scanning. Finish the existing Stage 3 and operations corrections before presenting the platform as commercially ready.

Acceptance:

- Full tests pass.
- E2E covers every page.
- Production rehearsal and final security review pass.
- No security exception is disguised as a pass.
- Independent review is recorded for OIDC/JWT and other high-impact authentication logic.

### P1 — Professional authenticated product experience

Implement the approved branded shell, rich command centre, deep mega-menu and contextual navigation. Every page must be a useful operational workspace with real data, drill-downs, filters, history, related records, actions and complete loading/empty/error/permission/offline states.

Add:

- Splash/readiness screen.
- One-time first-installation wizard.
- Professional password, MFA and configured SSO login.
- Organization/user menu.
- Permission-aware navigation.
- Consistent design system across all pages.
- Mobile, tablet, keyboard and screen-reader support.
- PWA packaging and safe update/offline behavior.

The authenticated application and the public commercial website are separate products with separate routes and security boundaries.

### P2 — Tenant and commercial platform foundation

Implement the previously agreed Phase C requirements after a complete baseline Alembic migration:

- Organizations and default migration for existing records.
- Strict tenant isolation in APIs, workers, queues, exports, caches and evidence.
- Members, invitations, owners and billing administrators.
- Plans, entitlements, trials, usage meters and hard/soft limits.
- Backend-enforced restrictions with auditable overrides.
- Billing-event evidence.
- Organization export, deletion, onboarding and offboarding.
- Self-hosted licence leases with grace and recovery rules.
- Provider-neutral billing interface; GreyGuard stores no card data.
- Cross-tenant isolation and billing-failure safety tests.

### P3 — Deployment packages and service reliability

Define supported commercial deployment models:

1. Hosted GreyGuard control plane.
2. Hybrid hosted control plane with customer-hosted gateway/enforcement worker.
3. Dedicated hosted tenant.
4. Customer-managed/self-hosted deployment with a verified licence and update path.

For each model document data boundaries, customer responsibilities, secrets, backups, telemetry, upgrades, rollback, deletion and support.

Add:

- Node/gateway enrollment and workload identity.
- Signed versioned policy/configuration distribution.
- Bounded offline policy use and revocation freshness.
- High availability and failure-mode matrix.
- Load, connection and queue benchmarks.
- Regional data-placement matrix.
- Customer-managed keys and private connectivity only after verified implementation.
- Public status page for operated services.
- Severity definitions, escalation route, maintenance notices and measured response targets.
- API/SDK compatibility matrix and deprecation policy.

Do not promise an SLA until measured operation supports it. A denied security decision is not a service outage.

### P4 — Buyer validation, packaging and pricing

Before fixing prices or expanding scope:

- Interview representative CISOs, AI platform owners, security operations leaders, developers and procurement stakeholders.
- Identify the economic buyer, technical evaluator, governance approver and daily operator.
- Recruit two to four design partners under written terms where possible.
- Test the product-group names, main problem, buying trigger, deployment preference and willingness to pay.
- Define a fixed-scope 60–90 day paid-pilot template with systems/agents covered, data terms, integrations, support hours, success criteria, exclusions and conversion decision.
- Maintain a cost model covering hosting, storage, delivery traffic, support, legal, audit, penetration testing, insurance and third-party licences.
- Treat all initial prices and capacity assumptions as hypotheses until validated.

Recommended pricing hypothesis: annual organization subscription with bands for actively governed agents and controlled-request volume; optional advanced response, evidence retention and dedicated deployment capacity.

### P5 — Customer onboarding and success

Create a repeatable customer lifecycle:

- Security and architecture discovery.
- Deployment-boundary agreement.
- Agent and integration inventory.
- Data-classification and retention decisions.
- Administrator, approver, analyst and auditor training.
- Policy-baseline workshop.
- Integration and recovery validation.
- Pilot success review.
- Production activation approval.
- Adoption and support reviews.
- Export, credential revocation, data deletion and offboarding.

Maintain implementation checklists, responsibility matrix, training material, support policy, version policy and escalation contacts. Product analytics must exclude prompts, secrets and sensitive payloads and must be disableable where required.

### P6 — Vendor trust and procurement readiness

Build a GreyGuard Trust Center whose content reflects evidence that actually exists:

- Security overview and architecture.
- Data-flow and deployment boundaries.
- Encryption and key-management summary.
- Authentication, authorization and tenant-isolation description.
- Secure development and vulnerability-management policy.
- Penetration-test summary when completed.
- Availability, backup and disaster-recovery information.
- Privacy, retention and deletion practices.
- Subprocessor register.
- Responsible-disclosure policy and `security.txt`.
- Current certifications and audits, with honest status.
- Standard security-questionnaire responses such as SIG Lite or CAIQ where appropriate.
- Customer evidence-request process under access control and NDA where necessary.

Prepare legal/procurement foundations with qualified advisers: Terms, Privacy Notice, Data Processing Agreement, subprocessors, Acceptable Use, support terms, pilot agreement, order form, licensing terms and incident-notification responsibilities. Do not treat roadmap text as legal advice.

SOC 2, ISO 27001, cyber insurance, regional hosting and public-sector authorizations are later gated programmes, not launch claims.

### P7 — Separate public commercial website

Create a public website separate from the administrator application and its infrastructure. The site should explain GreyGuard's agent-security focus and route qualified visitors to proof, documentation, a guided tour or demo request.

Required navigation:

- Platform.
- Agent environments/frameworks.
- Use cases.
- Integrations.
- Proof and Trust.
- Resources.
- Company.
- Sign in to the separate application.

Every product page must state:

- Buyer problem.
- How the control works.
- Supported agent environments.
- Real or clearly synthetic product visual.
- Evidence created.
- Integration/deployment path.
- Coverage boundaries and limitations.
- Availability: verified, pilot, preview or planned.
- Relevant documentation and next action.

Suggested homepage sequence:

1. Clear GreyGuard outcome and original brand visual.
2. Threats buyers recognize: overprivileged agents, approval bypass, unsafe tool calls, prompt-influenced actions, credential exposure and untraceable decisions.
3. Gate, Watch, Respond and Evidence product groups.
4. How a request moves from authenticated agent through policy, approval, execution boundary and evidence.
5. Where GreyGuard connects: SDK, API, MCP, framework adapters, gateway and monitor-only.
6. Honest coverage view showing connected, enforced and unsupported scope.
7. Safe synthetic proof experiences.
8. Security architecture and recognized-framework mappings with limitations.
9. Trust Center and current assurance status.
10. Design-partner or demo call to action.

The rich reference navigation can inspire information depth, but GreyGuard must use its own brand, layout, language and artwork.

Website requirements:

- Static-first/CDN architecture where practical.
- Separate deployment from the product application.
- CSP, HSTS and security headers.
- No exposed CMS administration surface.
- Spam and abuse controls on forms.
- Dependency/secret scanning and penetration-test scope.
- WCAG 2.2 AA and accessibility statement.
- Good mobile Core Web Vitals.
- Privacy-respecting analytics and consent withdrawal.
- GDPR/KVKK-compatible consent where applicable.
- Privacy, Terms, Cookies, Accessibility, Responsible Disclosure, Subprocessors and Status links.
- English first with localization-ready structure.
- Search metadata, sitemap, canonical URLs, structured data only where accurate and tested redirects.

### P8 — Proof, demonstrations and claims governance

Create memorable proof experiences only from verified capabilities and synthetic isolated data:

- Decision receipt explorer.
- Agent request and human-approval walkthrough.
- Safe prohibited-action simulation showing BLOCK/REFUSED, risk and evidence.
- Policy-change and rollback demonstration.
- Agent suspension and recoverable containment demonstration.
- Coverage and limitations page.
- GreyGuard's own internal security/control profile where honest and useful.

Maintain a public claim register:

- Claim text.
- Scope.
- Supporting test/evidence.
- Owner.
- Approval date.
- Expiry/review date.
- Pages using it.

No fabricated customers, testimonials, partner logos, analyst recognition, certifications, metrics or unsourced comparisons. A working connector does not imply a partnership. Marketing copy must be checked against the verified release before publication.

### P9 — Sales, pilot and partner enablement

Create only after the application and proof path are stable:

- Pitch deck.
- One-page datasheet for each product group.
- Architecture/security whitepaper.
- Demo script and synthetic sandbox.
- Pilot playbook and success-criteria template.
- Security-questionnaire response pack.
- Pricing sheet and ROI hypothesis.
- Objection-handling notes.
- Customer responsibility matrix.

Use a professional founder-led sales path: discovery, tailored demonstration, technical/security evaluation, paid pilot, then annual agreement. Potential future partners include security advisers, MSSPs, incident-response providers, agent-framework/gateway vendors, cloud marketplaces and regional resellers. Do not announce a formal partner without written agreement.

### P10 — Documentation and final acceptance

Extend Sections 19 and 20 with:

- Buyer-facing product and edition guide.
- Coverage matrix by connection method.
- Commercial deployment responsibility matrix.
- Support, severity and maintenance policy.
- Tenant-isolation design and test evidence.
- Metering and entitlement specification.
- Customer onboarding/offboarding runbook.
- Trust Center source register.
- Claim register.
- Pilot guide.
- Public website operations and publishing runbook.
- Legal-document register with owner/reviewer/status, without inventing legal conclusions.
- Complete source-code/security PDF and final presentation.

Final acceptance additionally requires:

- Every advertised capability maps to a verified release and evidence.
- Every plan restriction is tested server-side and cannot remove mandatory security.
- Cross-tenant tests pass across APIs, workers, queues, exports and reports.
- Billing/trial expiry preserves safe evidence access and offboarding.
- All public demos are synthetic and isolated.
- Accessibility and mobile acceptance cover both application and public website.
- Backup, restore, upgrade, rollback and tenant deletion rehearsals pass.
- Independent security review is completed.
- Required legal, privacy and procurement material has qualified review before paid customer data is accepted.
- Release is tagged, signed, frozen and accompanied by matching documentation.

## Claude implementation instruction

Treat this addendum as a roadmap extension, not authorization to build everything in one uncontrolled change. Reconcile it against the current repository and mark every item as Verified, In progress, Planned, Deferred or Not applicable with evidence. Do not duplicate features already completed. Work in the P0–P10 dependency order. Stop for Michael's approval before beginning each major workstream, changing dependencies, performing real-data migrations, publishing a website, pushing commits, tagging a release or making legal/compliance claims.

