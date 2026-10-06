"""Validate GreyGuard's committed CycloneDX software bill of materials."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def verify(document: dict) -> dict:
    errors = []
    if document.get("bomFormat") != "CycloneDX":
        errors.append("bomFormat must be CycloneDX")
    components = document.get("components")
    if not isinstance(components, list) or not components:
        errors.append("components must be a non-empty list")
        components = []
    identities = []
    for index, component in enumerate(components):
        name, version = component.get("name"), component.get("version")
        if not name or not version:
            errors.append(f"component {index} is missing name or version")
        identities.append((component.get("type"), name, version, component.get("purl")))
    if len(identities) != len(set(identities)):
        errors.append("duplicate component identities detected")
    return {"passed": not errors, "component_count": len(components), "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sbom", default="artifacts/greyguard-sbom.cdx.json")
    parser.add_argument("--output", default="artifacts/sbom-verification.json")
    args = parser.parse_args()
    result = verify(json.loads((ROOT / args.sbom).read_text(encoding="utf-8")))
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(output)
    if not result["passed"]:
        raise SystemExit("SBOM verification failed: " + "; ".join(result["errors"]))


if __name__ == "__main__":
    main()
