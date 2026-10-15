# Privacy, retention and deletion

The Privacy Notice and Data Processing Agreement are legal documents for qualified counsel (decision T7). This page describes only what the software does.

## Product analytics

- **Counts only.** Adoption figures are computed from data the product already holds [TC-PR-1].
- **One kind of collection.** The only thing collected for analytics is a daily page-view count per organization and fixed navigation path. It carries no user, session or IP address, and the browser sends nothing when Do Not Track is set [TC-PR-1].
- **Never collected:** prompts, request targets and payloads, tool results, secrets and credentials. A test checks that adoption output contains none of them [TC-PR-1].
- **Opt-out.** Analytics can be turned off for the whole install, or by an organization's owners, which also deletes the counts already collected [TC-PR-2].

## Audit evidence

- **Retention.** Audit retention defaults to 365 days, and deleting expired events needs explicit confirmation. Active legal holds block retention deletion [TC-PR-3].
- **Integrity.** Every event is sealed into a SHA-256 hash chain, and an authorized deletion is recorded as an erasure so the chain still verifies [TC-PR-3].

## Export, offboarding and deletion

- **Export is never withheld.** An organization's owners can export everything it owns at any time before deletion, including during offboarding. The export carries per-table digests, and credential material is redacted [TC-PR-4].
- **Offboarding.** It revokes agent credentials, service accounts and gateway nodes, disables integrations and report schedules, and cancels billing. Members keep read access to evidence [TC-PR-5].
- **Deletion.** Only an install operator can delete an organization, and only after its retention period (0 to 365 days, default 30), with its slug typed as confirmation, and never while a legal hold applies. Deletion removes every organization-scoped row and the organization's files, and produces a verifiable deletion certificate [TC-PR-5].
- **Backups.** Deleted data remains in existing backups until those backups age out [TC-PR-6].
