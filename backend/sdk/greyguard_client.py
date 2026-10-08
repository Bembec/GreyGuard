\
"""Credential-safe Python clients for the GreyGuard control plane.

This module intentionally covers both the agent and administrator surfaces
for GreyGuard's own examples, docs, and internal scripts. The separately
packaged, externally distributable agent-only SDK lives at
`sdk/python/greyguard_sdk` (see its README) and adds retry/idempotency
handling and scope validation that third-party agent integrators need;
this module stays admin-capable and dependency-free for in-repo use. The
two are not accidental duplicates of each other, but `GreyGuardAgentClient`
here and `greyguard_sdk.GreyGuardClient` do overlap on the agent-only
surface - keep safety-relevant behavior (such as honoring the server's
`Idempotency-Key` header on `/tool-requests`) in sync between them.
"""

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


JsonResponse = dict[str, Any] | list[Any]
Transport = Callable[[str, str, dict[str, str], dict[str, Any] | None, float], JsonResponse]


class GreyGuardClientError(Exception):
    """An error response returned by GreyGuard."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GreyGuardConnectionError(GreyGuardClientError):
    """GreyGuard could not be reached safely."""


def _decode(raw: bytes) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GreyGuardClientError("GreyGuard returned invalid JSON.") from error


def _default_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None,
    timeout: float,
) -> JsonResponse:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            result = _decode(response.read())
    except HTTPError as error:
        error_body = _decode(error.read())
        detail = error_body.get("detail") if isinstance(error_body, dict) else None
        raise GreyGuardClientError(
            str(detail or "GreyGuard rejected the request."), error.code
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise GreyGuardConnectionError("GreyGuard could not be reached.") from error
    if not isinstance(result, (dict, list)):
        raise GreyGuardClientError("GreyGuard returned an unsupported response.")
    return result


class _BaseClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        transport: Transport | None = None,
    ):
        self.base_url = str(base_url).strip().rstrip("/")
        if not self.base_url:
            raise ValueError("GreyGuard base URL is required.")
        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")
        self.timeout = float(timeout)
        self._transport = transport or _default_transport

    def _auth_headers(self) -> dict[str, str]:
        return {}

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> JsonResponse:
        url = self.base_url + "/" + path.lstrip("/")
        if query:
            clean = {key: value for key, value in query.items() if value is not None}
            if clean:
                url += "?" + urlencode(clean, doseq=True)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **self._auth_headers(),
            **(extra_headers or {}),
        }
        return self._transport(method.upper(), url, headers, payload, self.timeout)

    def health(self) -> dict[str, Any]:
        result = self._request("GET", "/health")
        if not isinstance(result, dict):
            raise GreyGuardClientError("Invalid health response.")
        return result

    def permissions(self) -> dict[str, Any]:
        result = self._request("GET", "/permissions")
        if not isinstance(result, dict):
            raise GreyGuardClientError("Invalid permissions response.")
        return result

    def tools(self) -> dict[str, Any]:
        result = self._request("GET", "/tools")
        if not isinstance(result, dict):
            raise GreyGuardClientError("Invalid tools response.")
        return result


class GreyGuardAgentClient(_BaseClient):
    """Client for one explicitly registered agent."""

    def __init__(
        self,
        base_url: str,
        agent_name: str,
        credential: str,
        timeout: float = 10.0,
        transport: Transport | None = None,
    ):
        super().__init__(base_url, timeout, transport)
        self.agent_name = str(agent_name).strip()
        self._credential = str(credential).strip()
        if not self.agent_name:
            raise ValueError("Agent name is required.")
        if not self._credential:
            raise ValueError("Agent credential is required.")

    def __repr__(self) -> str:
        return (
            f"GreyGuardAgentClient(base_url={self.base_url!r}, "
            f"agent_name={self.agent_name!r}, credential=<redacted>)"
        )

    def _auth_headers(self) -> dict[str, str]:
        return {"x-agent-name": self.agent_name, "x-agent-key": self._credential}

    def evaluate_action(self, action: str, approval: str | None = None) -> dict[str, Any]:
        if not str(action).strip():
            raise ValueError("Action is required.")
        payload: dict[str, Any] = {
            "agent_name": self.agent_name,
            "action": str(action).strip(),
        }
        if approval is not None:
            payload["approval"] = str(approval).strip().upper()
        result = self._request("POST", "/actions/evaluate", payload)
        if not isinstance(result, dict):
            raise GreyGuardClientError("Invalid evaluation response.")
        return result

    def request_tool(
        self,
        action: str,
        target: str = "",
        payload: dict[str, Any] | None = None,
        dry_run: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if not str(action).strip():
            raise ValueError("Tool action is required.")
        if idempotency_key is not None and not 8 <= len(idempotency_key) <= 128:
            raise ValueError("idempotency_key must be between 8 and 128 characters.")
        result = self._request(
            "POST",
            "/tool-requests",
            {
                "action": str(action).strip(),
                "target": str(target),
                "payload": payload or {},
                "dry_run": bool(dry_run),
            },
            extra_headers={"Idempotency-Key": idempotency_key} if idempotency_key else None,
        )
        if not isinstance(result, dict):
            raise GreyGuardClientError("Invalid tool-request response.")
        return result

    def get_tool_request(self, request_id: str) -> dict[str, Any]:
        if not str(request_id).strip():
            raise ValueError("Request ID is required.")
        result = self._request("GET", f"/tool-requests/{str(request_id).strip()}")
        if not isinstance(result, dict):
            raise GreyGuardClientError("Invalid tool-request evidence.")
        return result

    def wait_for_tool_request(
        self,
        request_id: str,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
    ) -> dict[str, Any]:
        if timeout <= 0 or poll_interval <= 0:
            raise ValueError("Timeout and poll interval must be greater than zero.")
        terminal = {"SUCCEEDED", "FAILED", "DENIED", "DRY_RUN", "BLOCKED", "REFUSED"}
        deadline = time.monotonic() + timeout
        while True:
            evidence = self.get_tool_request(request_id)
            if str(evidence.get("execution_status", "")).upper() in terminal:
                return evidence
            if time.monotonic() >= deadline:
                raise TimeoutError("Timed out waiting for the GreyGuard request.")
            time.sleep(poll_interval)

    def audit_events(self, limit: int = 20) -> list[dict[str, Any]]:
        result = self._request(
            "GET", f"/agents/{self.agent_name}/audit", query={"limit": limit}
        )
        if not isinstance(result, list):
            raise GreyGuardClientError("Invalid audit response.")
        return result

    def audit_summary(self) -> dict[str, Any]:
        result = self._request("GET", f"/agents/{self.agent_name}/summary")
        if not isinstance(result, dict):
            raise GreyGuardClientError("Invalid summary response.")
        return result


class GreyGuardAdminClient(_BaseClient):
    """Administrative client for GreyGuard governance."""

    def __init__(
        self,
        base_url: str,
        admin_pin: str,
        timeout: float = 10.0,
        transport: Transport | None = None,
    ):
        super().__init__(base_url, timeout, transport)
        self._admin_pin = str(admin_pin).strip()
        if not self._admin_pin:
            raise ValueError("Administrator PIN is required.")

    def __repr__(self) -> str:
        return f"GreyGuardAdminClient(base_url={self.base_url!r}, admin_pin=<redacted>)"

    def _auth_headers(self) -> dict[str, str]:
        return {"x-admin-pin": self._admin_pin}

    def _dict_result(self, method: str, path: str, payload=None, query=None):
        result = self._request(method, path, payload, query)
        if not isinstance(result, dict):
            raise GreyGuardClientError("GreyGuard returned an invalid response.")
        return result

    def list_agents(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/agents")
        if not isinstance(result, list):
            raise GreyGuardClientError("Invalid agent-list response.")
        return result

    def register_agent(self, agent_name: str, scopes: list[str]) -> dict[str, Any]:
        if not str(agent_name).strip():
            raise ValueError("Agent name is required.")
        return self._dict_result("POST", "/agents", {
            "agent_name": str(agent_name).strip(), "scopes": list(scopes)
        })

    def update_scopes(self, agent_name: str, scopes: list[str]) -> dict[str, Any]:
        return self._dict_result(
            "PUT", f"/agents/{str(agent_name).strip()}/scopes", {"scopes": list(scopes)}
        )

    def rotate_credential(self, agent_name: str) -> dict[str, Any]:
        return self._dict_result(
            "POST", f"/agents/{str(agent_name).strip()}/credential/rotate"
        )

    def revoke_credential(self, agent_name: str) -> dict[str, Any]:
        return self._dict_result(
            "POST", f"/agents/{str(agent_name).strip()}/credential/revoke"
        )

    def reset_agent(self, agent_name: str) -> dict[str, Any]:
        return self._dict_result("POST", f"/agents/{str(agent_name).strip()}/reset")

    def list_tool_requests(
        self,
        agent_name: str | None = None,
        approval_status: str | None = None,
        execution_status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return self._dict_result("GET", "/tool-requests", query={
            "agent_name": agent_name,
            "approval_status": approval_status,
            "execution_status": execution_status,
            "limit": limit,
        })

    def decide_tool_request(
        self,
        request_id: str,
        decision: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        normalized = str(decision).strip().upper()
        if normalized not in {"APPROVED", "DENIED"}:
            raise ValueError("Decision must be APPROVED or DENIED.")
        return self._dict_result(
            "POST",
            f"/tool-requests/{str(request_id).strip()}/decision",
            {"decision": normalized, "note": note},
        )

    def audit_events(
        self,
        event_type: str | None = None,
        agent_name: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        return self._dict_result("GET", "/audit-events", query={
            "event_type": event_type, "agent_name": agent_name, "limit": limit
        })

    def sandbox_resources(self) -> dict[str, Any]:
        return self._dict_result("GET", "/sandbox/resources")
