# Report governance

GreyGuard Section 11 Part 2 adds signed report manifests, independent export checksums, report scheduling, compliance-control mappings, retention visibility, administrator-action reports, and structured incident postmortems.

Set `GREYGUARD_REPORT_SIGNING_KEY` to a randomly generated value of at least 32 characters through the production secret mechanism. The key is never returned to the frontend. Manifests use HMAC-SHA256 and include the immutable evidence hash plus SHA-256 checksums for JSON, CSV, HTML, and PDF exports.

Only Platform Administrators may create or disable schedules. Disabling preserves schedule evidence. The scheduler records intent and next-run time; production automation must invoke the approved report-generation endpoint under a scoped service identity.

Mappings currently cover NIST CSF 2.0, ISO 27001:2022, and SOC 2 evidence references. They support evidence organization and do not claim certification.

Postmortem templates contain impact, timeline, root cause, effective controls, gaps, corrective actions, evidence references, owner, and review date. Retention reports are observational and never delete evidence automatically.

Rollback restores the previous API and Compliance Reports page, disables schedules, preserves existing reports and postmortem evidence, and rotates the report-signing key if exposure is suspected.
