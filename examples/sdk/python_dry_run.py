"""Submit a credential-safe GreyGuard dry run from Python."""

import os

from greyguard_sdk import GreyGuardClient, ToolRequest


def required_environment(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name} before running this example.")
    return value


client = GreyGuardClient(
    base_url=os.environ.get("GREYGUARD_URL", "http://127.0.0.1:8000"),
    agent_name=required_environment("GREYGUARD_AGENT_NAME"),
    credential=required_environment("GREYGUARD_AGENT_KEY"),
    scopes={"read_file"},
)

result = client.submit(
    ToolRequest(
        action="read_file",
        target="public_report.txt",
        dry_run=True,
    )
)

print(
    f"request={result.request_id} "
    f"approval={result.approval_status} "
    f"execution={result.execution_status}"
)
