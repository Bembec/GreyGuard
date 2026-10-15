# Customer lifecycle: onboarding, success and offboarding

This is the repeatable path a customer takes, from first conversation to offboarding. Each stage names its exit criteria and the product evidence that shows it is met, so progress is checked against the system rather than asserted.

Values the business must still decide are marked **[commercial team]**. They are deliberately not invented here: contacts, hours and response times.

## Stages

| # | Stage | Exit criteria | Evidence in the product |
|---|---|---|---|
| 1 | Security and architecture discovery | Agents, tools and data the customer wants governed are listed; deployment model chosen ([deployment-models.md](deployment-models.md)). | None (pre-sales). |
| 2 | Deployment-boundary agreement | Data boundary, customer responsibilities and region agreed in writing. | None (contractual). |
| 3 | Org creation | Org onboarded by an install operator; owner invitation accepted. | `POST /organizations/onboard`; checklist item `owner_active`. |
| 4 | Agent and integration inventory | First agents registered with least-privilege scopes; SIEM, incident or notification destination configured. | Checklist items `first_agent` and `integration`; `GET /entitlements` usage. |
| 5 | Data classification and retention decisions | Retention period and evidence export cadence chosen; legal holds understood. | Audit retention settings; checklist item `export_tested`. |
| 6 | Role training | Administrators, approvers, analysts and auditors trained (see [Training](#training)). | Checklist items `separation_of_duties`, `auditor_assigned` and `mfa_everyone`. |
| 7 | Policy-baseline workshop | A reviewed policy published through four-eyes approval. | Checklist item `policy_baseline`; policy history. |
| 8 | Integration and recovery validation | Each of the following run once, with the evidence kept: <ul><li>an evidence export;</li><li>a test delivery to each destination;</li><li>an emergency global deny, switched on and off again;</li><li>an agent credential rotation;</li><li>an agent reset.</li></ul> | Delivery evidence, audit log, credential history. |
| 9 | Pilot success review | The six pilot criteria reviewed at day 75. | The Getting Started pilot panel (`GET /organizations/{org_id}/pilot`) and the adoption summary. |
| 10 | Production activation approval | Pilot converted; customer sign-off recorded. | The pilot decision `CONVERT` (Enterprise ACTIVE); the entitlement and lifecycle history. |
| 11 | Adoption and support reviews | Held periodically **[commercial team: cadence per edition]**. | Adoption summary trend. |
| 12 | Offboarding | Export taken and delivered, credentials revoked, then deletion after retention. | Offboarding record, export digests, deletion certificate ([organization-lifecycle.md](organization-lifecycle.md)). |

## In the product

- **Getting Started** (`/getting-started`, every member) turns the readiness checklist into steps. Each step says why it matters and who does it, and links to the page where it is done. The backend decides whether a step is complete; nobody ticks it by hand.
- **Pilots** follow provisional P4 decision D2. An install operator onboards a pilot with `POST /organizations/onboard` and `"pilot": true`, or starts one later with `POST /organizations/{org_id}/pilot`. The org then runs on Enterprise, in TRIAL status, for 90 days, with the conversion decision due at day 75. Getting Started shows the pilot's six success criteria:
  - four are measured from product data: readiness complete, four or more weeks of real use, a human approval decision, the emergency global deny exercised;
  - two are confirmed by an operator with a note: the governance approver accepted an evidence export, and no SEV1/SEV2 incident was caused by GreyGuard.

  The operator records the outcome on the same page or through `POST /organizations/{org_id}/pilot/decision`:
  - **Convert:** the org moves to Enterprise ACTIVE.
  - **Extend:** once, by up to 30 days, decided near the end of the pilot.
  - **Offboard:** the org starts offboarding.

  **No fee, price or payment detail is stored.** The pilot fee is an open decision (P4 D3).

Stages 3 to 10 map onto the readiness checklist that `GET /organizations/{org_id}/lifecycle` computes. The Settings page shows the checklist to every member.

## Responsibility matrix

R = responsible, A = accountable, C = consulted, I = informed.

| Activity | Customer owner | Customer security / admins | GreyGuard customer success | GreyGuard operations |
|---|---|---|---|---|
| Deployment model and boundary | A | C | R | C |
| Org creation and owner invitation | I | I | C | R/A |
| Agent registration and scopes | A | R | C | — |
| Policy baseline | A | R | C | — |
| Integrations and their secrets | A | R | C | — |
| Plan assignment | C | I | R | A |
| Incident response for the operated service | I | I | C | R/A |
| Incident response for the customer's agents | A | R | C | I |
| Backups and restore (hosted, dedicated) | I | I | I | R/A |
| Backups and restore (self-hosted) | A | R | C | C |
| Offboarding and deletion | A | R | C | R (deletion) |

## Training

One short module per role. Each ends with the trainee doing the action in the product, not just reading about it.

| Role | Covers | Practised by |
|---|---|---|
| Administrator (owner / PLATFORM_ADMIN) | Org, members and MFA; agents and scopes; integrations; emergency controls; export and offboarding. | Inviting an auditor; registering and rotating an agent; switching emergency global deny on and off. |
| Approver | The approval queue; four-eyes rules; expiring approval links. | Approving and rejecting a held request. |
| Analyst (SECURITY_ANALYST) | Alerts, investigations, request evidence, live operations. | Investigating a blocked request end to end. |
| Auditor | The audit log; integrity verification; compliance reports and their exports. | Generating and verifying a compliance report. |

The material is drawn from the existing documentation, starting from [docs/sdk/quickstart.md](sdk/quickstart.md) and [operations-runbook.md](operations-runbook.md). **[commercial team: delivery format and certification, if any]**.

## Support policy

| Item | Policy |
|---|---|
| Severity definitions | SEV1–SEV4, as published by `GET /status/severities` and the status page. A denied security decision is not an incident. |
| Channels and hours | **[commercial team, per edition]**. |
| Response targets | **Measured, not promised.** `GET /status/history` reports median time to acknowledge and resolve per severity. Targets are set only once measured operation supports them. |
| Escalation contacts | **[commercial team]**. Kept in the customer's onboarding record, not in this repository. |
| Versions supported | The current release and the previous minor release **[commercial team to confirm]**. API compatibility follows [api-compatibility.md](api-compatibility.md). |
| Maintenance notices | Published on the status page in advance (`POST /status/maintenance`). |

## Adoption analytics

Customer success needs to know whether an org is actually using what it bought, without ever seeing what its agents did. `GET /organizations/{org_id}/adoption` gives an install operator, or the org's owners, a summary built only from counts and feature names. It is described in [product-analytics.md](product-analytics.md), which states exactly what is and is not collected and how to turn it off.
