"""Minimal GreyGuard SDK example with environment-managed credentials."""

import os

from greyguard_sdk import GreyGuardClient, ToolRequest


client = GreyGuardClient(
    base_url=os.environ.get("GREYGUARD_URL", "http://127.0.0.1:8000"),
    agent_name=os.environ["GREYGUARD_AGENT_NAME"],
    credential=os.environ["GREYGUARD_AGENT_KEY"],
    scopes={"read_file"},
)

result = client.submit(
    ToolRequest(
        action="read_file",
        target="public_report.txt",
    )
)
print(f"request={result.request_id} status={result.execution_status}")
