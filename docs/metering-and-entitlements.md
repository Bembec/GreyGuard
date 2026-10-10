# Metering and entitlement specification

GreyGuard enforces plans, trials and usage limits in the backend (`backend/app/entitlements.py`), never only in the user interface. This document is the specification that module implements. It also lists the commercial decisions that are still open.

## Principles

These come from the commercial roadmap addendum.

- **Backend enforcement.** Every restriction is checked by the API, so a modified or bypassed UI cannot get past it.
- **Plans never remove protection.** Some capabilities are included in every edition, whatever the plan, status or overrides:
  - agent identity
  - authorization
  - redaction
  - evidence
  - emergency stop
  - basic recovery
  - evidence export
  - offboarding

  The engine refuses to treat any of them as a gated feature, and overrides cannot target them. A test asserts that the gated features and the mandatory protections never overlap.
- **Oversight is never discouraged.** Members are not metered, including reviewers, auditors and read-only participants.
- **Failure is safe.** When a trial expires or an account is suspended, the org enters *restricted mode*:
  - **Paused:** new growth, meaning new agents and new gated configuration.
  - **Still enforced:** existing agents, exactly as before.
  - **Still available:** evidence, exports, emergency controls, credential revocation and offboarding.
- **Exceptions are explicit.** Install operators can grant overrides. Each override requires a reason, can carry an expiry, can be revoked, and is recorded in the entitlement event log.

## Plans

An org with no assigned plan is **Unassigned**: nothing is enforced, which matches GreyGuard's behaviour before plans existed. Every existing org and every new org starts this way. Only install operators assign plans (`PUT /entitlements/{org_id}`). An org can never assign its own.

| Plan | Gated features | Agents (soft / hard) | Integrations (soft / hard) |
|---|---|---|---|
| Unassigned | all | unlimited | unlimited |
| Foundation | none | 20 / 25 | 3 / 5 |
| Enterprise | all | 200 / 250 | 50 / 100 |
| Dedicated | all | unlimited | unlimited |

The gated features are SIEM export, incident-system integrations and scheduled reports.

Monthly controlled requests and deliveries are metered on every plan, but no plan sets a hard limit for them. They are reported against soft limits only:

- **Foundation:** 50,000 requests, 10,000 deliveries.
- **Enterprise:** 1,000,000 requests, 250,000 deliveries.

**All limits above are working values, not decided prices.** They live only in `PLANS` in `entitlements.py`, so changing them is a data change.

## Statuses

| Status | Meaning |
|---|---|
| ACTIVE | Plan in force. |
| TRIAL | Plan in force until `trial_ends_at` (1–90 days); it becomes EXPIRED the moment it ends. |
| EXPIRED | Restricted mode. |
| SUSPENDED | Restricted mode (for example, after a payment failure). |

## Meters

| Meter | Unit | Source |
|---|---|---|
| `agents` | registered agent identities | `agent_identities` |
| `controlled_requests_monthly` | tool requests evaluated this UTC month | `tool_requests` |
| `deliveries_monthly` | successful outbound deliveries this UTC month | `outbound_delivery_evidence` |
| `integrations` | configured SIEM, incident-system and notification destinations | the three destination tables |

Storage is not metered yet. Meters never fall back to zero when a table is missing, because a meter that silently under-counts would let an org past a hard limit.

## Enforcement points

| Action | Check |
|---|---|
| Register an agent | `agents` capacity |
| Create a SIEM export destination | `siem_export` feature, then `integrations` capacity |
| Create an incident-system destination | `incident_integrations` feature, then `integrations` capacity |
| Create a notification destination | `integrations` capacity |
| Create a report schedule | `scheduled_reports` feature |

Updating an existing destination, matched by name within the org, never counts as growth. A refused action returns `403` with `"reason": "ENTITLEMENT"` and a message saying what the plan allows.

## API

| Route | Who | Purpose |
|---|---|---|
| `GET /entitlements` | any administrator | Their org's plan, status, features, limits, usage and active overrides |
| `GET /entitlements/{org_id}` | install operator | The same, plus the audited history |
| `PUT /entitlements/{org_id}` | install operator | Assign a plan and status (and a trial length) |
| `POST /entitlements/{org_id}/overrides` | install operator | Add an override: `feature:<name>` → true/false, or `limit:<meter>:soft\|hard` → integer or null (unlimited) |
| `DELETE /entitlements/{org_id}/overrides/{id}` | install operator | Revoke an override |

The Settings page shows every administrator their org's plan, usage and always-included protections, read-only.

## Open commercial decisions

The engine is complete, but these decisions belong to the business and are not made in code:

1. **Limits.** The real numbers for each plan, including whether any plan should ever hard-limit controlled requests or deliveries.
2. **Defaults.** Whether new orgs should start on a trial automatically, and on which plan and length. Today every org starts Unassigned.
3. **Storage.** Whether storage should be metered, and in what unit.
4. **Payment-failure behaviour beyond restricted mode.** For example, whether existing agents should ever stop. The current rule is that they never do.
5. **Billing link.** How plan status connects to the provider-neutral billing interface (P2.4).
