# Organization lifecycle

GreyGuard takes an organization from onboarding to deletion through `backend/app/org_lifecycle.py`. An org's status moves one way:

**ACTIVE → OFFBOARDING → DELETED**

An install operator can return an offboarding org to ACTIVE. Nothing can leave DELETED.

## Principles

These come from the commercial roadmap addendum.

- **Export is never withheld.** An org's owners can export everything the org owns at any point before deletion, including during restricted mode and offboarding. Evidence export is a mandatory protection (see [metering-and-entitlements.md](metering-and-entitlements.md)).
- **Offboarding is safe, not abrupt.** It stops everything that acts or sends data on the org's behalf. Members keep read access, and evidence stays available, until deletion.
- **Deletion is deliberate, complete and evidenced.** Only an install operator can delete an org, and only:
  - after a retention period;
  - with the org's slug typed as confirmation; and
  - never while a legal hold applies.

  Deletion removes every row in every org-scoped table and the org's files, and leaves a verifiable certificate.
- **Lifecycle records outlive the org.** The lifecycle log, the offboarding record and the deletion certificate are install-level tables, so deletion does not remove them.

## Onboarding

`POST /organizations/onboard` (install operator) does the following in one step:

1. creates a customer org, **without** the operator joining it;
2. invites the customer's first owner (`PLATFORM_ADMIN` / `OWNER`);
3. optionally assigns a plan, or a trial when `trial_days` is given.

The invitation token is returned once. Deliver it to the owner out of band.

`GET /organizations/{org_id}/lifecycle` (members and install operators) shows a readiness checklist. The backend computes each item from the org's real data; nobody ticks it by hand.

| Item | Done when |
|---|---|
| `owner_active` | An owner has joined. |
| `separation_of_duties` | There are at least two active members, so an approval can need a second person. |
| `auditor_assigned` | A member has the `AUDITOR` role. |
| `mfa_everyone` | Every active member has MFA enabled. |
| `plan_assigned` | The org has a plan other than Unassigned. |
| `policy_baseline` | The org has a published policy version. |
| `first_agent` | An agent is registered. |
| `integration` | A SIEM, incident-system or notification destination is configured. |
| `export_tested` | An evidence export has been taken. |

The Settings page shows the checklist to every member and the export button to owners.

## Export

`POST /organizations/{org_id}/export` (owner or install operator) returns one JSON bundle in the `greyguard-organization-export/1` format. It contains:

- the org and its members;
- every row of every org-scoped table with `org_id` equal to the org. The tenant guard rejects any query that lacks the predicate, so no other org's rows can appear;
- a manifest with each table's row count and SHA-256 digest, and a bundle digest over the manifest.

Credential material (`REDACTED_COLUMNS`, such as credential and key hashes, salts, tokens and MFA secrets) is replaced with `REDACTED`. A test requires every column in the schema whose name looks like a secret to be either in `REDACTED_COLUMNS` or in `EVIDENCE_COLUMNS` (non-secret digests and references). A new credential column therefore cannot reach an export without a decision.

Each export is recorded in the lifecycle log with its digest. The deletion certificate lists those digests.

## Offboarding

`POST /organizations/{org_id}/offboarding` (owner or install operator) takes a reason and a retention period of 0–365 days (default 30). It marks the org OFFBOARDING first, so nothing new can be added, and then closes its doors:

| Action | Effect |
|---|---|
| Agent credentials revoked | Every agent of the org stops authenticating. |
| Service accounts revoked | Every API key stops working. |
| Integrations disabled | SIEM, incident-system and notification destinations stop sending. |
| Report schedules disabled | No more scheduled reports. |
| Invitations revoked | Pending invitations stop working. Invitations to a non-active org cannot be accepted at all. |
| Billing cancelled | Any subscription is cancelled at the provider. |

Each action's result is recorded, including any error; the remaining actions still run.

While an org is offboarding:

- **New growth is refused.** Entitlements report `ORG_OFFBOARDING` as a restriction reason.
- **The org is read-only.** The RBAC middleware refuses every state-changing request from a session acting in the org (`403`, `"reason": "OFFBOARDING"`), except:
  - the org's own sessions, lifecycle and export routes;
  - compliance reports and alert handling;
  - the billing contact;
  - every emergency and revocation control: policy emergency controls, credential, secret, service-account and workload revocation, emergency isolation termination and emergency capability shutdown.

`DELETE /organizations/{org_id}/offboarding` (install operator) cancels offboarding and returns the org to ACTIVE. Revoked credentials stay revoked and disabled integrations stay disabled; they are reissued and re-enabled deliberately.

## Deletion

`POST /organizations/{org_id}/deletion` (install operator) with `{"confirm_slug": "<slug>"}` is refused unless all of the following are true:

- the org is OFFBOARDING;
- its retention period has passed;
- the slug matches exactly;
- it is not the default org;
- no active legal hold covers the org: the hold names one of its agents, or names no agent and so covers everything.

Deletion runs in two stages.

**In one database transaction:**

1. The org's audit events are sealed into the integrity chain and recorded as erasures (see [audit-integrity-and-retention.md](audit-integrity-and-retention.md)), so the install-wide chain still verifies afterwards.
2. Every org-scoped table is cleared of the org's rows. Foreign-key children go first (`CHILD_TABLES_FIRST`, which a test checks against the live schema).
3. Memberships and invitations are deleted.
4. Sessions acting in the org lose their active org.
5. The `organizations` row becomes a DELETED tombstone. Its slug is freed for reuse.

**After the transaction commits:**

- The org's isolated-workspace directory and quarantined files are removed.
- Its agents' runtime state is dropped.

A deletion certificate is recorded and returned. It contains:

- the rows deleted per table, and the total;
- the number of audit events erased;
- the number of files removed;
- the agents removed;
- the offboarding reason;
- the digests of the exports taken.

The certificate also carries its own SHA-256. `GET /organizations/{org_id}/deletion-certificate` (install operator) returns it with `verified`.

Administrator accounts are people, not org data, so deletion does not remove them. An account whose only org was deleted remains, with no membership.

## API

| Route | Who | Purpose |
|---|---|---|
| `POST /organizations/onboard` | install operator | Create an org, invite its owner, optionally assign a plan |
| `GET /organizations/{org_id}/lifecycle` | members, install operator | Status, offboarding record, readiness checklist and lifecycle log |
| `POST /organizations/{org_id}/export` | owner, install operator | Full data export |
| `POST /organizations/{org_id}/offboarding` | owner, install operator | Start offboarding |
| `DELETE /organizations/{org_id}/offboarding` | install operator | Cancel offboarding |
| `POST /organizations/{org_id}/deletion` | install operator | Delete an offboarded org |
| `GET /organizations/{org_id}/deletion-certificate` | install operator | The deletion certificate |

## Open decisions

1. **Retention default.** 30 days is a working value. It could depend on the plan (the Dedicated edition promises extended retention).
2. **Scheduled deletion.** Today an operator deletes an org explicitly once it is eligible. Whether deletion should run automatically at the end of retention is a policy decision.
3. **Export size.** The export is built in memory as one bundle. A very large org will need a streamed or chunked format.
4. **Orphaned accounts.** Whether an account left without any membership should be disabled automatically.
