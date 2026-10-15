# GreyGuard public website (P7)

The public commercial site is a separate product from the administrator console. It will be built
and deployed separately (decision W2 in [`docs/roadmap/p7-decision-package.md`](../docs/roadmap/p7-decision-package.md)),
and imports nothing from `frontend/` or `backend/`. Only its content lives here today. The site
build arrives in P7.1.

## Claims: the one rule

Every statement the site makes about what GreyGuard does comes from
[`content/claims.json`](content/claims.json), the claim register. The site never hard-codes a
product claim in page copy.

Each claim records:

| Field | Meaning |
|---|---|
| `id` | `GG-<GROUP>-<n>`, stable once published |
| `group` | `gate`, `watch`, `respond`, `evidence`, `connect`, `platform` or `trust` |
| `kind` | `capability` (what GreyGuard does) or `limitation` (what it does not do, or where coverage ends) |
| `availability` | `verified`, `pilot`, `preview` or `planned`. The site shows this label beside the claim. |
| `claim` | The exact sentence the site may use |
| `scope` | What the claim covers and what it does not |
| `evidence` | Files, or `file::test name`, that prove it |
| `owner` | `Engineering` keeps it true to the code; `Project owner` holds the business decision |
| `status` | `proposed`, `approved` or `withdrawn`. Only `approved` claims are published. |
| `approved_by`, `approved_on` | Who approved it and when. The project owner approves every published claim. |
| `review_by` | Re-check date. An approved claim past this date blocks publication. |
| `pages` | The site pages that use it, filled in as pages are written |

`python scripts/check_claims.py` checks the register, and `backend/tests/test_claim_register.py`
runs that check in CI. A verified capability must cite a test, not just prose. Every cited file
and test must exist. Claim text may not imply a partnership, certification or guarantee.

## Approving claims

Approval is the project owner's decision. To approve a claim, set `status` to `approved` and fill
in `approved_by` and `approved_on`. Withdraw a claim that is no longer true rather than deleting
it, so the history of what was said stays visible.
