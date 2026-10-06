"""Export a deterministic public API contract and detect removed operations."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.api import app


METHODS = {"get", "post", "put", "patch", "delete"}


def contract() -> dict:
    schema = app.openapi()
    operations = []
    for path, path_item in sorted(schema.get("paths", {}).items()):
        for method in sorted(METHODS.intersection(path_item)):
            operation = path_item[method]
            operations.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId"),
                }
            )
    encoded = json.dumps(operations, separators=(",", ":"), sort_keys=True).encode()
    return {
        "api_version": "1",
        "operations": operations,
        "operation_count": len(operations),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def removed_operations(previous: dict, current: dict) -> list[dict]:
    active = {(item["method"], item["path"]) for item in current["operations"]}
    return [
        item
        for item in previous.get("operations", [])
        if (item["method"], item["path"]) not in active
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/api-contract.json")
    parser.add_argument("--compare")
    args = parser.parse_args()
    current = contract()
    if args.compare:
        previous = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        removed = removed_operations(previous, current)
        current["removed_operations"] = removed
        if removed:
            raise SystemExit("Breaking API change detected: operations were removed")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
