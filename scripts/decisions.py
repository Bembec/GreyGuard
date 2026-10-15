"""GreyGuard's deferred-decision registry: validate it, render the founder register, and gate launch.

config/decisions.json records every founder, brand, commercial, legal and operational decision
that is still open, with the safe behaviour the product uses until it is made and where the final
value is configured. Approved public values live in that file. Deployment-specific values and
secrets stay in environment variables, and this script reports only whether they are set, never
their values.

    python scripts/decisions.py check                        # validate the registry
    python scripts/decisions.py render                       # rewrite docs/roadmap/FOUNDER_DECISIONS_REQUIRED.md
    python scripts/decisions.py readiness --target preview   # report; never fails
    python scripts/decisions.py readiness --target production [--json]

Readiness tiers: BLOCKING_FOR_PRODUCTION, REQUIRED_BEFORE_PUBLIC_LAUNCH, OPTIONAL_POST_LAUNCH, and
COMPLETED once a decision is made. "production" fails while any blocking item is open;
"public-launch" also fails on items required before public launch; "development" and "preview"
always pass, so open decisions never stop development.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "decisions.json"
BRAND_MANIFEST = ROOT / "config" / "brand-assets.json"
CLAIMS = ROOT / "website" / "content" / "claims.json"
FOUNDER_DOC = ROOT / "docs" / "roadmap" / "FOUNDER_DECISIONS_REQUIRED.md"

BLOCKING = "BLOCKING_FOR_PRODUCTION"
REQUIRED = "REQUIRED_BEFORE_PUBLIC_LAUNCH"
OPTIONAL = "OPTIONAL_POST_LAUNCH"
COMPLETED = "COMPLETED"
IMPACTS = (BLOCKING, REQUIRED, OPTIONAL)
CATEGORIES = ("brand", "commercial", "company", "legal", "operations")
STATUSES = ("open", "in_progress", "decided")
VALUE_TYPES = ("string", "text", "list", "boolean", "email", "https_url", "url_or_mailto", "assets", "status", "approval", "reference", "claims", "env_present")
# Computed decisions: their state comes from another source, never from a value typed in here.
COMPUTED = ("claims", "env_present")
FIELDS = ("id", "category", "question", "status", "launch_impact", "value_type", "value", "temporary_behaviour", "configured_in",
          "professional_review", "owner", "decided_on", "evidence", "remediation")
OPTIONAL_FIELDS = ("env",)
ID_PATTERN = re.compile(r"^(BRAND|COM|CO|LEG|OPS)-([0-9]{2}|NAME)$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Nothing secret may ever be recorded here: the registry is public, version-controlled content.
SECRET_KEY = re.compile(r"(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential)", re.IGNORECASE)
SECRET_VALUE = re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|\bgga_[A-Za-z0-9_-]{8,}|\bsk_(live|test)_[A-Za-z0-9]{8,}|\bAKIA[0-9A-Z]{16}\b|://[^/\s:@]+:[^/\s@]+@)")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_value(value_type: str, value) -> bool:
    if value_type in ("string", "text", "status", "approval"):
        return isinstance(value, str) and bool(value.strip())
    if value_type == "list":
        return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type == "email":
        return isinstance(value, str) and bool(EMAIL.match(value))
    if value_type == "https_url":
        return isinstance(value, str) and value.startswith("https://") and "@" not in value.split("/", 3)[2]
    if value_type == "url_or_mailto":
        return isinstance(value, str) and (_valid_value("https_url", value) or bool(re.match(r"^mailto:[^@\s]+@[^@\s]+\.[^@\s]+$", value)))
    if value_type == "assets":
        return value == "final"
    if value_type == "reference":
        return isinstance(value, str) and bool(ID_PATTERN.match(value))
    return value is None  # computed types never hold a value


def _scan_for_secrets(node, path: str, problems: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if SECRET_KEY.search(key):
                problems.append(f"{path}.{key}: a field that looks like a secret has no place in public configuration")
            _scan_for_secrets(value, f"{path}.{key}", problems)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _scan_for_secrets(value, f"{path}[{index}]", problems)
    elif isinstance(node, str) and SECRET_VALUE.search(node):
        problems.append(f"{path}: contains something that looks like a secret or embedded credential")


def check_registry(registry: dict) -> list[str]:
    problems: list[str] = []
    if registry.get("format") != "greyguard-decisions/1":
        return ["the registry's format must be greyguard-decisions/1"]
    decisions = registry.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        return ["the registry has no decisions"]
    _scan_for_secrets(registry, "decisions.json", problems)
    ids = [item.get("id") for item in decisions]
    for item in decisions:
        did = item.get("id", "<no id>")

        def problem(message: str) -> None:
            problems.append(f"{did}: {message}")

        missing = [field for field in FIELDS if field not in item]
        if missing:
            problem(f"is missing {', '.join(missing)}")
            continue
        extra = [field for field in item if field not in FIELDS + OPTIONAL_FIELDS]
        if extra:
            problem(f"has unknown fields {', '.join(extra)}")
        if not ID_PATTERN.match(did):
            problem("has an id that does not match <BRAND|COM|CO|LEG|OPS>-<nn>")
        if ids.count(did) > 1:
            problem("is listed twice")
        if item["category"] not in CATEGORIES:
            problem(f"has an unknown category {item['category']!r}")
        if item["status"] not in STATUSES:
            problem(f"has an unknown status {item['status']!r}")
        if item["launch_impact"] not in IMPACTS:
            problem(f"has an unknown launch_impact {item['launch_impact']!r}")
        if item["value_type"] not in VALUE_TYPES:
            problem(f"has an unknown value_type {item['value_type']!r}")
            continue
        for field in ("question", "configured_in", "owner", "remediation"):
            if not isinstance(item[field], str) or not item[field].strip():
                problem(f"needs a non-empty {field}")
        if item["value_type"] in COMPUTED:
            if item["value"] is not None or item["status"] == "decided":
                problem("is computed from another source, so it holds no value and is never marked decided here")
            if item["value_type"] == "env_present" and not item.get("env"):
                problem("lists no environment variables to check")
            continue
        if item["status"] == "decided":
            if not _valid_value(item["value_type"], item["value"]):
                problem(f"is decided but its value is not a valid {item['value_type']}")
            if not item["decided_on"] or not item["evidence"]:
                problem("is decided but does not record decided_on and evidence")
            else:
                try:
                    date.fromisoformat(item["decided_on"])
                except ValueError:
                    problem("has a decided_on that is not an ISO date")
            if item["value_type"] == "reference" and item["value"] not in ids:
                problem(f"refers to unknown decision {item['value']}")
        else:
            if item["value"] is not None:
                problem("is not decided, so it must not carry a value the product could mistake for approved")
            if item["decided_on"] or item["evidence"]:
                problem("is not decided but records a decision date or evidence")
            if not item["temporary_behaviour"].strip():
                problem("is open, so it must say what the product does until it is decided")
    return problems


def _claims_state() -> tuple[bool, str]:
    claims = load(CLAIMS)["claims"]
    pending = [claim["id"] for claim in claims if claim["status"] == "proposed"]
    if not pending:
        return True, "every claim is approved or withdrawn"
    return False, f"{len(pending)} of {len(claims)} claims are still proposed ({', '.join(pending[:5])}{'…' if len(pending) > 5 else ''})"


def _brand_frozen(decisions: dict) -> bool:
    freeze = decisions.get("BRAND-06")
    return bool(freeze and freeze["status"] == "decided" and freeze["value"] is True)


def readiness(registry: dict, environ: dict | None = None) -> list[dict]:
    """One row per decision: its tier, whether it is met, and how to resolve it."""
    env = os.environ if environ is None else environ
    decisions = {item["id"]: item for item in registry["decisions"]}
    frozen = _brand_frozen(decisions)
    rows = []
    for item in registry["decisions"]:
        impact = item["launch_impact"]
        if item["value_type"] == "assets" and frozen:
            impact = BLOCKING
        detail = ""
        if item["value_type"] == "claims":
            met, detail = _claims_state()
        elif item["value_type"] == "env_present":
            names = [name.strip() for name in item["env"].split(",") if name.strip()]
            unset = [name for name in names if not env.get(name, "").strip()]
            met = not unset
            detail = "all set" if met else "not set: " + ", ".join(unset)
        else:
            met = item["status"] == "decided" and _valid_value(item["value_type"], item["value"])
            if met and item.get("env"):
                configured = env.get(item["env"], "").strip()
                if configured != item["value"]:
                    met = False
                    detail = f"{item['env']} must equal the decided value"
        rows.append({
            "id": item["id"], "category": item["category"], "question": item["question"],
            "tier": COMPLETED if met else impact, "met": met, "detail": detail,
            "temporary_behaviour": item["temporary_behaviour"], "remediation": item["remediation"],
        })
    return rows


def gate(rows: list[dict], target: str) -> list[dict]:
    """The unmet rows that stop this target. Development and preview are never stopped."""
    stopping = {"production": (BLOCKING,), "public-launch": (BLOCKING, REQUIRED)}.get(target, ())
    return [row for row in rows if not row["met"] and row["tier"] in stopping]


def render_founder_doc(registry: dict) -> str:
    lines = [
        "# Founder decisions required",
        "",
        "<!-- Generated from config/decisions.json by `python scripts/decisions.py render`. Do not edit by hand:",
        "     change the registry and re-render. backend/tests/test_decision_registry.py keeps the two in step. -->",
        "",
        "Every decision GreyGuard needs from its owner or a professional adviser, what the product does safely until",
        "it is made, and where the final value goes. Engineering does not guess these. When a decision is made, record",
        "it in `config/decisions.json` (value, status `decided`, date and evidence) and re-render this file.",
        "",
        "Readiness: `python scripts/decisions.py readiness --target production` lists exactly what blocks a production",
        "publication, with how to resolve each item. Development and preview builds never require these decisions.",
        "",
    ]
    titles = {"brand": "Brand", "commercial": "Commercial", "company": "Public company information", "legal": "Legal and trust", "operations": "Operations"}
    for category in CATEGORIES:
        items = [item for item in registry["decisions"] if item["category"] == category]
        lines += [f"## {titles[category]}", "",
                  "| ID | Decision required | Safe behaviour until decided | Configured in | Blocks public launch | Professional review | Owner | Status | Decided | Evidence |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for item in items:
            blocks = {BLOCKING: "Yes — blocks production", REQUIRED: "Yes — before public launch", OPTIONAL: "No"}[item["launch_impact"]]
            if item["value_type"] == "assets":
                blocks += " (blocks production once the brand is frozen, BRAND-06)"
            status = "Computed" if item["value_type"] in COMPUTED else item["status"].replace("_", " ").capitalize()
            cells = [item["id"], item["question"], item["temporary_behaviour"] or "—", f"`{item['configured_in']}`" + (f", env `{item['env']}`" if item.get("env") else ""),
                     blocks, item["professional_review"] or "—", item["owner"], status, item["decided_on"] or "—", item["evidence"] or "—"]
            lines.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in cells) + " |")
        lines.append("")
    return "\n".join(lines)


def _print_report(rows: list[dict], target: str, stopping: list[dict]) -> None:
    order = {BLOCKING: 0, REQUIRED: 1, OPTIONAL: 2, COMPLETED: 3}
    print(f"Launch readiness for target: {target}")
    for tier in (BLOCKING, REQUIRED, OPTIONAL, COMPLETED):
        group = [row for row in rows if row["tier"] == tier]
        print(f"\n{tier} ({len(group)})")
        for row in sorted(group, key=lambda r: (order[r["tier"]], r["id"])):
            line = f"  - {row['id']}: {row['question']}"
            if row["detail"]:
                line += f" [{row['detail']}]"
            print(line)
            if not row["met"]:
                print(f"      until then: {row['temporary_behaviour'] or '—'}")
                print(f"      to resolve: {row['remediation']}")
    if stopping:
        print(f"\nNot ready for {target}: {len(stopping)} item(s) must be resolved: {', '.join(row['id'] for row in stopping)}")
    else:
        print(f"\nNothing stops target {target}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("render")
    ready = sub.add_parser("readiness")
    ready.add_argument("--target", choices=("development", "preview", "production", "public-launch"), default="preview")
    ready.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    registry = load(REGISTRY)
    problems = check_registry(registry)
    if problems:
        print(f"Decision registry: {len(problems)} problem(s)")
        for item in problems:
            print(f"  - {item}")
        return 1
    if args.command == "check":
        open_count = sum(1 for item in registry["decisions"] if item["status"] != "decided")
        print(f"Decision registry OK: {len(registry['decisions'])} decisions ({open_count} not yet decided)")
        return 0
    if args.command == "render":
        FOUNDER_DOC.write_text(render_founder_doc(registry), encoding="utf-8")
        print(f"Wrote {FOUNDER_DOC.relative_to(ROOT)}")
        return 0
    rows = readiness(registry)
    stopping = gate(rows, args.target)
    if args.json:
        print(json.dumps({"target": args.target, "ready": not stopping, "stopping": [row["id"] for row in stopping], "items": rows}, indent=2, ensure_ascii=False))
    else:
        _print_report(rows, args.target, stopping)
    return 1 if stopping else 0


if __name__ == "__main__":
    sys.exit(main())
