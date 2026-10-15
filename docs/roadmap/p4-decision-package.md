# P4 decision package: buyer, pilot, packaging and pricing

## Decision record

| # | Decision | Status | As recorded |
|---|---|---|---|
| D1 | Target buyer | **Approved (provisional)** | Organizations of 500–5,000 employees, regulated or audit-heavy, moving agents with real tool access into production. Economic buyer: the CISO. |
| D2 | Pilot model | **Approved (provisional)** | Paid, 90 days, Enterprise TRIAL, hosted, fixed scope as in section 2. |
| D3 | Pilot fee | **Pending** | To be set after cost modelling and buyer interviews. No fee or price field exists in code or documents, and none will be added before then. |
| D4 | SSO | **Approved (provisional)** | Included in every edition; not gated. |
| D5 | Editions | **Approved (provisional)** | Foundation, Enterprise and Dedicated remain working labels for interviews. |
| D6 | Provisional limits | **Partly decided** | Request and delivery volumes are **monitored soft limits that can never interrupt security operations**, and this is now enforced in code (`MONITORED_ONLY_METERS`). Agent and integration capacity **rules** are built: only active agents and enabled integrations count, archiving frees capacity without deleting anything, plans are explicit, and Dedicated limits come from the contract. The limit **values** are **neither changed nor confirmed**; their values and basis are shown in [section 4](#4-provisional-limits) for your review. |
| D7 | Pricing metric | **Approved (provisional)** | An annual subscription banded by governed agents. No figures until interviews and the cost model. |
| D8 | Trials | **Approved (provisional)** | No self-serve trial at launch; sales-assisted pilots only. |
| D9 | Deployment lead | **Approved as the working direction, with conditions** | Hosted-first, **subject to verified** infrastructure cost, capacity, backup, recovery and support readiness. Customer-hosted gateways stay **pilot-only until packaged**. Dedicated and self-hosted come later. |
| D10 | Design partners | **Objective approved; candidates pending** | Recruit 2–4 under written terms. Candidates will be selected once suitable design partners are identified. |
| D11 | Proceed to P5 | **Approved; P5 delivered and approved** | Getting Started, pilot tracking and counts-only adoption analytics (commit `f15bfbe`). No prices, payment credentials or live billing. |

### Conditions D9 still needs evidence for

| Condition | Evidence so far | Still needed |
|---|---|---|
| Capacity | Measured throughput on one 4-vCPU process (`docs/reliability.md`); multiple processes safe. | Measurement on the intended hosting size; a multi-replica test. |
| Backup and recovery | Verified PostgreSQL backup and restore tooling (`postgres_backup_ops.py`); a disaster-recovery drill script. | A timed restore drill on the hosting platform; recovery objectives agreed. |
| Infrastructure cost | None. | A cost model from real hosting quotes and accounts. |
| Support readiness | Severity definitions, the status page, the incident workflow. | Named people, hours and an on-call arrangement. |

**Status: provisional decisions recorded on 2026-10-15** (see [Decision record](#decision-record)). Every decision is provisional and evidence-driven: it stands until buyer interviews, the cost model or operating data contradict it. Nothing here is validated with buyers yet. Every number below is either a measured technical fact (labelled *measured*) or a working value already in code that this package proposes to keep or change (labelled *working value*). **No price appears anywhere, in this document or in code**, and none will until interviews and the cost model support one.

Once you decide, the code side is a data change, not a rewrite. Plans and limits live only in `PLANS` in `backend/app/entitlements.py`, and onboarding defaults live in `org_lifecycle.onboard()`.

---

## 1. Target buyer

### Recommendation

**Organizations with 500–5,000 employees that are moving AI agents with real tool access (write, send, execute, spend) from experiments into production.** Start with regulated or audit-heavy sectors: financial services, healthcare, B2B SaaS that sells to enterprises, and the public-sector supply chain.

### Why this segment

GreyGuard's strongest verified capabilities are the ones these buyers are asked about in audits and customer questionnaires:

- approvals for consequential actions;
- tamper-evident evidence;
- emergency stop;
- tenant-isolated, exportable records.

Smaller companies rarely face those questions yet. The largest enterprises have sales cycles too long for a first product.

### Buying committee

| Role | Typical title | What they need to see |
|---|---|---|
| Economic buyer | CISO / Head of Security | Risk reduced and evidenced; no new blind spot; cost within the security budget. |
| Technical evaluator | AI/ML platform lead, staff engineer | SDK fit, latency, failure behaviour (fails closed), deployment model. |
| Governance approver | Risk, compliance, internal audit | Evidence export, integrity verification, retention, legal holds. |
| Daily operator | SecOps analyst, platform on-call | Alerts, approvals queue, investigations, SIEM delivery. |

### Buying trigger to test

One of the following:

- the first agent is about to get write or send access in production;
- an auditor or customer questionnaire asks how AI agent actions are controlled;
- an incident or near miss involving an agent.

### Alternatives considered

- **Developer-led self-serve (SMB).** Not first: there is no self-serve signup (org creation is install-operator-only by design), and the support load per dollar is high.
- **Very large enterprises first.** Not first: cycles of 9–18 months, and a demand for customer-managed keys and private connectivity, which are not built.
- **MSSPs as the first channel.** Later: the roadmap says partners come after the proof path is stable (P9).

## 2. Pilot model

### Recommendation

**A fixed-scope, paid, 90-day pilot on the Enterprise plan, hosted, sales-assisted.** This is the roadmap's "60–90 day paid pilot" at its upper bound, because a buyer needs time to put real agents through approvals and an audit-style evidence review.

| Element | Proposed template |
|---|---|
| Scope | Up to 5 production-candidate agents; 1–2 integrations (SIEM and one notification or incident system); hosted deployment. |
| Product setup | Org onboarded by an install operator on **Enterprise, status TRIAL, 90 days** (the existing `trial_days` maximum). Restricted mode after expiry pauses growth but never enforcement or evidence. |
| Data terms | **[legal, P6]** A pilot agreement and DPA. GreyGuard stores redacted request evidence; no card data. |
| Support | Business hours, named contact, weekly check-in. **[commercial: hours and time zone]** |
| Success criteria | All measured in the product, agreed before start: <ul><li>readiness checklist complete (9/9);</li><li>agents routed through GreyGuard for real work for 4 or more weeks;</li><li>at least one held action approved or rejected by a human;</li><li>an emergency global deny exercised;</li><li>an evidence export accepted by the customer's governance approver;</li><li>no enforcement incident (SEV1/SEV2) caused by GreyGuard.</li></ul> |
| Exclusions | Customer-managed keys, private connectivity, custom development, self-hosted, a gateway runtime package (not built), and an SLA (not yet measured). |
| Conversion decision | At day 75: convert to an annual Enterprise agreement, extend once by up to 30 days, or offboard (export, revoke, delete) with the certificate. |
| Pilot fee | Required (it filters for real intent). **[decision: amount, and whether it is credited to year one]** |

## 3. Plan tiers

### Recommendation

**Keep the three editions, with their current working names, as the packaging hypothesis to test in interviews.** What each includes in the product today:

| | Foundation | Enterprise | Dedicated |
|---|---|---|---|
| Who | Small teams starting controlled agent adoption | Production agents | Regulated or isolation-sensitive organizations |
| Always included (never gated) | Agent identity, authorization, redaction, evidence, emergency stop, basic recovery, evidence export, offboarding | Same | Same |
| SIEM export, incident integrations, scheduled reports | No | Yes | Yes |
| Customer-hosted gateway nodes | No | Yes | Yes |
| Deployment | Hosted | Hosted or hybrid | A separate install (region choice) or self-hosted |
| Not offered yet | — | — | Customer-managed keys, private connectivity (not built or verified) |

**Open packaging question: enterprise SSO.** The addendum lists SSO under Enterprise, but the code does not gate it today; every edition gets it. I recommend **keeping SSO in all editions**. Gating it weakens customers' security posture, and buyers increasingly object to an "SSO tax". This is your call (Decision D4).

## 4. Provisional limits

### The current values and their basis (for D6)

These are the values in `PLANS` today, unchanged since the entitlements engine was built (P2.3, commit `0317feb`):

| Meter | Foundation (soft / hard) | Enterprise (soft / hard) | Dedicated | Enforced where |
|---|---|---|---|---|
| Agents | 20 / 25 | 200 / 250 | Unlimited | Agent registration only. Existing agents are never affected. |
| Integrations (SIEM, incident system and notification destinations) | 3 / 5 | 50 / 100 | Unlimited | Creating a *new* destination only. Updating one is not growth. |
| Controlled requests per month | 50,000 / none | 1,000,000 / none | Unlimited | **Never.** Reported only. |
| Deliveries per month | 10,000 / none | 250,000 / none | Unlimited | **Never.** Reported only. |
| Members | — | — | — | Never metered, so oversight is never discouraged. |

Every org starts **Unassigned**, which enforces nothing, until an install operator assigns a plan.

**The operational basis, stated plainly.** These numbers were chosen as round placeholders that separate a small team from a production estate. They were **not** derived from customer data, cost or measured capacity, because none of those existed when they were set. What can be said about them now:

- **They are far below technical capacity.** One process measured about 16 controlled requests per second, about 41 million a month at full load. No placeholder is close to a technical limit, so the limits are a commercial choice, not a safety one.
- **The hard limits protect only growth.** A plan reaching its agent or integration hard limit refuses *new* agents or *new* destinations, nothing else. In restricted mode (expired trial, overdue payment, lapsed licence or offboarding), growth pauses, while enforcement, evidence, export, emergency controls and offboarding continue.
- **Operators can override per org.** Overrides need a reason, can expire and are audited.

**What would give them a basis:**

- the number of agents and integrations pilot organizations actually run (adoption analytics, P5);
- interview answers on agent counts;
- the per-org hosting cost from the cost model.

Until then I recommend leaving them as they are and labelling them provisional, which is what the code and the docs already do. **No change is made without your decision.**

## 5. Pricing structure (no figures)

### Recommendation

**An annual organization subscription, banded by actively governed agents**, which the `agents` and `active_agents` meters already count. Controlled-request volume is reported, not billed, in year one. Dedicated deployment and extended retention are priced separately.

This is the roadmap's own hypothesis. No figure is proposed. Numbers come from two sources:

1. **Willingness-to-pay interviews** with the committee in section 1 (4–6 organizations; questions in Annex A).
2. **A cost model per hosted org.** Inputs to gather:
   - hosting and PostgreSQL;
   - storage growth (evidence per request);
   - delivery traffic;
   - support hours;
   - legal, penetration testing, audit and insurance (amortised);
   - third-party licences.

   The figures I can supply are measurements from the codebase: throughput per vCPU, storage per request (to be measured). Costs need your accounts.

Nothing is hard-coded. Billing is provider-neutral and mock-only, and plans carry no prices.

## 6. Trial structure

### Recommendation

**No self-serve trial at launch. Sales-assisted pilots only** (section 2):

- a self-serve trial needs public signup, which the product deliberately doesn't have;
- each early customer needs a named relationship anyway.

What changes in code after approval:

- `POST /organizations/onboard` already takes a plan and `trial_days` (1–90). Make **Enterprise TRIAL, 90 days** the documented default for pilots. No code change is required; adopting it is an operating decision.
- Keep "Unassigned" (nothing enforced) only for the default org and internal orgs.

**Alternative.** A 30-day Foundation self-serve trial later (P7/P9), once public signup exists.

## 7. Hosted versus self-hosted

### Recommendation

**Lead with hosted. Offer hybrid only to pilots with engineering capacity. Defer self-hosted and Dedicated until after the first conversions.**

| Model | Ready? | Proposed position |
|---|---|---|
| Hosted | Yes. Tenant isolation verified (P2.6); multi-worker safe; status page. | Default for every pilot. |
| Hybrid (customer gateway) | Partly. Signed distribution, bounded offline use and SDK verification exist; **no packaged gateway runtime**. | Only with a customer that can integrate `greyguard_sdk.gateway`, or after a gateway package is built. |
| Dedicated | Technically yes (a separate install), but operationally heavy. | After 2 or more hosted conversions; priced separately. |
| Self-hosted | Licence leases, signed releases and the documented update path exist. | Only for a design partner that requires it, under a named support arrangement. |

## 8. Decisions requested

Each decision has a recommendation; reply with the number and *approve*, or with your alternative.

| # | Decision | Recommendation | Alternatives |
|---|---|---|---|
| D1 | Target buyer and segment | 500–5,000 employees, regulated or audit-heavy, agents moving to production. Economic buyer: the CISO. | Developer-led SMB; large enterprise first. |
| D2 | Pilot model | Paid, 90 days, Enterprise TRIAL, hosted, fixed scope as in section 2. | 60 days; free pilot; hybrid-first. |
| D3 | Pilot fee | Required. Amount set by you; credited to year one if converted. | No fee; not credited. |
| D4 | SSO in Foundation | Include in all editions (do not gate). | Gate to Enterprise, as in the addendum. |
| D5 | Editions | Keep Foundation, Enterprise and Dedicated as working labels for interviews. | Two editions only (merge Dedicated into Enterprise options). |
| D6 | Provisional limits | Keep the current working values for pilots; requests and deliveries soft only. | Change any values now; hard-limit requests. |
| D7 | Pricing metric | Annual subscription banded by governed agents; no figures until interviews and the cost model. | Request-volume pricing; per-seat (not recommended; discourages oversight). |
| D8 | Trials | No self-serve trial at launch; sales-assisted pilots only. | A 30-day Foundation self-serve trial (needs public signup). |
| D9 | Deployment lead | Hosted first; hybrid with capable pilots; Dedicated and self-hosted later. | Offer self-hosted from day one. |
| D10 | Design partners | Recruit 2–4 under written terms. **You name the candidates.** | — |
| D11 | Proceed to P5 on approval | Build the product onboarding experience and documentation to the approved model. | Pause after P4. |

## What happens after approval

1. **Record the decisions** in this file and in the status matrix.
2. **Configure, don't hard-code.** Only approved, non-price values change in `PLANS`. Onboarding defaults follow D2 and D8.
3. **Start P5.** Build the onboarding experience: a guided first-run path in the product driven by the readiness checklist, and an operator pilot setup. Add the supporting documentation, and the privacy-safe adoption analytics already drafted (held in a git stash until approval).

---

## Annex A: interview guide (30 minutes, per role)

1. Which AI agents do you run or plan to run, and what can they *do* (write, send, execute, spend)?
2. What happens today when an agent does something it shouldn't? Who finds out, and how?
3. Who must approve putting an agent into production? What evidence do they ask for?
4. Have auditors, customers or regulators asked about agent controls? What did you show them?
5. Hosted, in your cloud, or on-premises: what would security and legal accept?
6. What would make you stop using a control like this? (Latency, false blocks, an outage.)
7. Is there a budget line this would come from? Who signs?
8. For a tool that does this, which of these is a no-brainer, worth a business case, or too expensive? Show ranges only in interviews; never in the product.
9. Would you run a 90-day paid pilot with success criteria agreed up front?
