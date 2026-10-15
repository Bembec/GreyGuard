# Master Roadmap v3 — adoption record

**Status: adopted as the plan of record, 2026-10-15.** The project owner approved v3
(`GreyGuard_Master_Roadmap_v3.docx`, in this folder) with the engineering recommendations below
("go with what you think is best"). `addendum-reconciliation.md` remains the status matrix with its
evidence. This file records how v3 maps onto it, where v3's status section was out of date, and
the four decisions v3 left open.

## Corrections to v3 section 2 ("Where GreyGuard stands")

v3 reported some statuses second-hand. Checked against the repository on 2026-10-15:

| v3 says | Repository status |
|---|---|
| P0–P6 reported complete | P0, P1, P2, P3, P5 and P6 are verified, with evidence in the status matrix. P4's decisions are provisional: D3 (pilot fee), the D6 limit values and D10 (design partners) await the owner. |
| P7 nearly finished | P7.0 (claim register) and P7.1 (site skeleton) are verified. P7.2 is in progress (homepage built). P7.3–P7.5 and publishing remain. |
| P7.5 not started | Much of v3's P7.5 was built as P1.4 on 2026-10-15: domain workspaces, page tabs, the mega-menu, Ctrl+K page search, a Command Center on live data, and a shared page anatomy across 36 pages. P7.5 builds on P1.4 and does not redo it. |
| Known gap: outbound delivery worker never sends | Built and verified in P0 (`outbound_worker.py`, with SSRF protection and its tests). |
| Stage 2 every-page e2e: final run to confirm | Done: 64 browser tests and 724 backend tests pass. |
| NEW: what-if dry-run API | Partly exists: tool requests accept `dry_run`, and there are policy-simulation endpoints. |
| 30 threat assessments need human approval | Correct and still open; this is the owner's task. |

## The four decisions v3 left open

| # | Decision | Adopted | Why |
|---|---|---|---|
| V1 | Console navigation | **v3's seven task domains**: Command Center; Agents & Access; Policies & Approvals; Operations & Incidents; Evidence & Reports; Integrations; Organization & Administration. **Keep the sidebar** and its collapsed mega-menu. | Operators work by task. Gate, Watch, Respond and Evidence stay as the buyer-facing names on the website. Regrouping is mostly a change to `frontend/src/config/workspaces.ts`. |
| V2 | Light theme | **Dark-only for now.** Converge the console's colours onto design tokens within P7.5's design-quality batch, then reintroduce a light theme. Print-friendly reports and receipts come first. | P7.5 restyles pages anyway, so doing the colours now would touch about 40 stylesheets twice. |
| V3 | Claim labels | **Two fields per claim:** `availability` (verified, pilot, preview, planned), which exists today, and a new `control` field (enforced, observed, advisory, simulated). In-app data labels (live, simulated, sample, pilot, planned) stay a separate concept. | Maturity and control strength answer different buyer questions. |
| V4 | Fail-open agents | **Only together with monitor-only mode**: off by default, set per agent by an administrator, recorded in evidence, and reflected in the claims. Not built before monitor-only. | GreyGuard's core guarantee is that it fails closed. |

## Ordering adopted (v3 section 8)

1. Finish P7 (P7.2–P7.4) **without final screenshots or the product tour**. Those are captured after P7.5.
2. Audit every console page against the P7.5 page anatomy into a gap matrix. It builds on P1.4 and does not rewrite working pages blindly.
3. Implement P7.5 in small verified batches:
   - navigation (V1);
   - role-preset Command Center;
   - the rest of the universal page anatomy;
   - the Control Graph;
   - the investigation workspace;
   - decision explainability.
4. Security-sensitive NEW items each get their own design and independent review before they are built: step-up MFA, approval from email, Slack or Teams, fail-open and monitor-only, and MCP definition pinning.
5. P10's final acceptance gains v3's UX gate and its latency and fail-closed checks.

## Owner-held items v3 adds

- **Buyer interviews and design partners** (P4, starting now).
- **Five usability sessions** with real users.
- **A trademark search** for "GreyGuard" and the product-group names, before those names are published.
- **Logo vector masters:** see `docs/brand/logo-design-brief.md`.
- **Domain and email security** (SPF, DKIM, DMARC) before outreach starts.
- **Accounts for publishing the SDKs** to PyPI and npm.
- **GreyGuard's own incident-response and breach-notification plan**, with counsel.
- **Approval of the 30 threat assessments.**
