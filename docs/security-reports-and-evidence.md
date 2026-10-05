# Security reports and evidence

GreyGuard Roadmap Section 11 Part 1 expands immutable compliance snapshots into portable security reports.

## Export formats

- JSON preserves the complete structured report and integrity result.
- CSV provides review-friendly rows and prefixes values beginning with `=`, `+`, `-`, or `@` to prevent spreadsheet formula injection.
- Printable HTML escapes report-controlled text and includes print styling.
- PDF is generated locally from stored evidence without loading remote content.

## Evidence categories

Every snapshot exposes an agent security assessment, risk timeline, decision statistics, approval evidence, containment evidence, authentication evidence, and policy-version evidence. Reports remain point-in-time records protected by their existing SHA-256 fingerprint.

## Authorization and rollback

All report routes require an authenticated GreyGuard administrator. Unknown report identifiers fail without creating files. Integrity is recalculated whenever a report is opened. To roll back, restore the previous API, compliance-report module, page, and tests; existing immutable report rows remain available.
