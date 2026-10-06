"""Fail when tracked source files contain recognizable production secrets."""

import argparse
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "github-token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "stripe-live-key": re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b"),
}
TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".yml", ".yaml",
    ".toml", ".ini", ".md", ".txt", ".conf", ".env", ".example",
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    return [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]


def scan(paths: list[Path]) -> list[dict]:
    findings = []
    for path in paths:
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            if "nosecret" in line.lower():
                continue
            for rule, pattern in PATTERNS.items():
                if pattern.search(line):
                    try:
                        display_path = str(path.relative_to(ROOT))
                    except ValueError:
                        display_path = str(path)
                    findings.append(
                        {"rule": rule, "path": display_path, "line": number}
                    )
    return findings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/secret-scan.json")
    args = parser.parse_args()
    findings = scan(tracked_files())
    evidence = {"scanner": "greyguard-tracked-secret-scan", "findings": findings, "passed": not findings}
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(output)
    if findings:
        raise SystemExit(f"Secret scan detected {len(findings)} potential secret(s).")


if __name__ == "__main__":
    main()
