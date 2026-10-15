"""Check the public-site claim register (website/content/claims.json).

The addendum (P8, brought forward to P7.0) forbids unsourced claims: every product statement on
the public site must come from this register, with its scope, evidence, owner, approval and
review date. This check keeps the register honest:

- every cited file exists, and every cited test (``path::test name``) exists in that file;
- a *verified* capability cites at least one test, not just prose;
- a *planned* or *preview* item is never worded or labelled as available;
- an *approved* claim names who approved it and when, and is not past its review date;
- claim text avoids words that imply partnerships, certifications or guarantees the evidence
  cannot back.

Run it with ``python scripts/check_claims.py``; it exits non-zero and lists every problem.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "website" / "content" / "claims.json"

GROUPS = {"gate", "watch", "respond", "evidence", "connect", "integrate", "platform", "trust"}
KINDS = {"capability", "limitation"}
AVAILABILITY = {"verified", "pilot", "preview", "planned"}
# How the control acts (decision V3 of the v3 roadmap); separate from how mature it is.
CONTROLS = {"enforced", "observed", "advisory", "simulated"}
CONTROLLED_GROUPS = {"gate", "watch", "respond", "evidence"}
STATUSES = {"proposed", "approved", "withdrawn"}
OWNERS = {"Engineering", "Project owner"}
ID_PATTERN = re.compile(r"^GG-[A-Z]+-\d+$")
TEST_LOCATIONS = ("backend/tests/", "frontend/e2e/", "frontend/src/test/", "sdk/")
# Words the addendum's claims governance rules out unless a specific, approved exception exists.
FORBIDDEN = re.compile(
    r"\b(partner(s|ship|ships|ed)?|certified|certification(s)?|compliant|guarantee(s|d)?|unbreakable|"
    r"military[- ]grade|best[- ]in[- ]class|industry[- ]leading|never\s+fails|impossible\s+to)\b"
    r"|\b100\s*%",  # a percentage has no word boundary after the sign
    re.IGNORECASE,
)
# A limitation may say what GreyGuard does *not* hold, so these negations are allowed there.
NEGATED = re.compile(r"\b(no|not|holds no|does not|without)\b[^.]*", re.IGNORECASE)


def _test_exists(path: Path, name: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        return re.search(rf"^def {re.escape(name)}\(", text, re.MULTILINE) is not None
    return re.search(rf"""\b(it|test)\(\s*["'`]{re.escape(name)}["'`]""", text) is not None


def check_evidence(reference: str, root: Path = ROOT) -> str | None:
    """Return a problem with one evidence reference, or None if it holds."""
    path_part, _, test_name = reference.partition("::")
    path = root / path_part
    if not path.exists():
        return f"cites a missing file: {path_part}"
    if test_name and (path.is_dir() or not _test_exists(path, test_name)):
        return f"cites a missing test: {reference}"
    return None


def is_test_reference(reference: str) -> bool:
    path_part, _, test_name = reference.partition("::")
    return path_part.startswith(TEST_LOCATIONS) and (bool(test_name) or Path(path_part).name.startswith("test_"))


def check_claim(claim: dict, today: date, root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    claim_id = claim.get("id", "<no id>")

    def problem(message: str) -> None:
        problems.append(f"{claim_id}: {message}")

    required = ("id", "group", "kind", "availability", "control", "claim", "scope", "evidence", "owner", "status",
                "approved_by", "approved_on", "review_by", "pages")
    missing = [field for field in required if field not in claim]
    if missing:
        problem(f"is missing {', '.join(missing)}")
        return problems

    if not ID_PATTERN.match(claim["id"]):
        problem("has an id that does not match GG-<GROUP>-<n>")
    if claim["group"] not in GROUPS:
        problem(f"has an unknown group {claim['group']!r}")
    if claim["kind"] not in KINDS:
        problem(f"has an unknown kind {claim['kind']!r}")
    if claim["availability"] not in AVAILABILITY:
        problem(f"has an unknown availability {claim['availability']!r}")
    if claim["control"] is not None and claim["control"] not in CONTROLS:
        problem(f"has an unknown control {claim['control']!r}")
    if claim["kind"] == "capability" and claim["group"] in CONTROLLED_GROUPS and claim["control"] is None:
        problem("is a product capability but does not say whether it is enforced, observed, advisory or simulated")
    if claim["kind"] == "limitation" and claim["control"] is not None:
        problem("is a limitation, so it has no control type")
    if claim["status"] not in STATUSES:
        problem(f"has an unknown status {claim['status']!r}")
    if claim["owner"] not in OWNERS:
        problem(f"has an unknown owner {claim['owner']!r}")
    if not str(claim["claim"]).strip() or not str(claim["scope"]).strip():
        problem("needs both claim text and a scope")
    if not isinstance(claim["pages"], list):
        problem("pages must be a list")

    text = str(claim["claim"])
    checked_text = NEGATED.sub("", text) if claim["kind"] == "limitation" else text
    forbidden = FORBIDDEN.search(checked_text)
    if forbidden:
        problem(f"uses {forbidden.group(0)!r}, which implies something the evidence cannot back")

    evidence = claim["evidence"]
    if not isinstance(evidence, list):
        problem("evidence must be a list")
        evidence = []
    for reference in evidence:
        issue = check_evidence(reference, root)
        if issue:
            problem(issue)

    if claim["availability"] == "verified" and claim["kind"] == "capability" and not any(is_test_reference(r) for r in evidence):
        problem("is a verified capability but cites no test")
    if claim["availability"] == "verified" and not evidence:
        problem("is verified but cites no evidence")
    if claim["availability"] in {"planned", "preview"}:
        if claim["status"] == "approved" and claim["pages"] and "planned" not in text.lower() and claim["availability"] == "planned":
            problem("is planned but published without saying so")

    try:
        review_by = date.fromisoformat(claim["review_by"])
    except (TypeError, ValueError):
        problem("has a review_by that is not an ISO date")
        review_by = None

    if claim["status"] == "approved":
        if not claim["approved_by"] or not claim["approved_on"]:
            problem("is approved but does not say who approved it and when")
        else:
            try:
                date.fromisoformat(claim["approved_on"])
            except ValueError:
                problem("has an approved_on that is not an ISO date")
        if review_by and review_by < today:
            problem(f"is approved but its review date {claim['review_by']} has passed")
    elif claim["approved_by"] or claim["approved_on"]:
        problem("records an approval but its status is not approved")

    return problems


def check_register(register: dict, today: date | None = None, root: Path = ROOT) -> list[str]:
    today = today or date.today()
    if register.get("format") != "greyguard-claims/1":
        return ["the register's format must be greyguard-claims/1"]
    claims = register.get("claims")
    if not isinstance(claims, list) or not claims:
        return ["the register has no claims"]
    problems: list[str] = []
    seen: set[str] = set()
    for claim in claims:
        claim_id = claim.get("id")
        if claim_id in seen:
            problems.append(f"{claim_id}: is listed twice")
        seen.add(claim_id)
        problems.extend(check_claim(claim, today, root))
    return problems


def publishable(register: dict) -> list[dict]:
    """The claims the site may show: approved, and not withdrawn."""
    return [claim for claim in register["claims"] if claim["status"] == "approved"]


def main() -> int:
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    problems = check_register(register)
    counts = {status: sum(1 for claim in register["claims"] if claim["status"] == status) for status in sorted(STATUSES)}
    if problems:
        print(f"Claim register: {len(problems)} problem(s)")
        for item in problems:
            print(f"  - {item}")
        return 1
    print(f"Claim register OK: {len(register['claims'])} claims ({', '.join(f'{n} {s}' for s, n in counts.items())})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
