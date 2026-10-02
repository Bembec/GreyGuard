\
"""Safe dry-run example for one registered GreyGuard agent."""

import os

from backend.sdk import GreyGuardAgentClient


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def main():
    client = GreyGuardAgentClient(
        required("GREYGUARD_URL"),
        required("GREYGUARD_AGENT_NAME"),
        required("GREYGUARD_AGENT_KEY"),
    )
    result = client.request_tool("read_file", "public_report.txt", dry_run=True)
    print("Request ID:", result.get("request_id"))
    print("Policy decision:", result.get("policy_decision"))
    print("Execution status:", result.get("execution_status"))


if __name__ == "__main__":
    main()
