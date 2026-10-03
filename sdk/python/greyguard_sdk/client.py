"""Dependency-free, security-conscious GreyGuard API client."""

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterable
from typing import Any

from .errors import (
    AuthenticationError,
    AuthorizationError,
    RequestError,
    ScopeValidationError,
)
from .models import PolicyEvaluation, ToolRequest, ToolRequestResult

Transport = Callable[
    [str, str, dict[str, str], bytes | None, float],
    tuple[int, dict[str, Any]],
]

_SENSITIVE_KEYS = (
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
    "x-agent-key",
    "api_key",
)
_RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})


def redact(value: Any) -> Any:
    """Return a recursively redacted copy suitable for logs."""

    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if any(marker in str(key).lower() for marker in _SENSITIVE_KEYS)
                else redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


class GreyGuardClient:
    """Authenticate an agent and submit policy-controlled actions."""

    def __init__(
        self,
        base_url: str,
        agent_name: str,
        credential: str,
        *,
        scopes: Iterable[str] | None = None,
        timeout: float = 10.0,
        max_retries: int = 2,
        transport: Transport | None = None,
    ):
        if not base_url.strip():
            raise ValueError("base_url is required")
        if not agent_name.strip():
            raise ValueError("agent_name is required")
        if not credential:
            raise ValueError("credential is required")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        self.base_url = base_url.rstrip("/")
        self.agent_name = agent_name
        self._credential = credential
        self.scopes = frozenset(scopes) if scopes is not None else None
        self.timeout = timeout
        self.max_retries = max_retries
        self._transport = transport or self._urlopen_transport

    def __repr__(self) -> str:
        return (
            "GreyGuardClient("
            f"base_url={self.base_url!r}, "
            f"agent_name={self.agent_name!r}, "
            "credential='[REDACTED]')"
        )

    def evaluate(self, action: str) -> PolicyEvaluation:
        """Evaluate one action. This call is deliberately not retried."""

        self._validate_scope(action)
        payload = self._request(
            "POST",
            "/actions/evaluate",
            {"action": action},
            retryable=False,
        )
        return PolicyEvaluation.from_dict(payload)

    def submit(
        self,
        request: ToolRequest,
        *,
        idempotency_key: str | None = None,
    ) -> ToolRequestResult:
        """Submit a tool request with safe, idempotent transient retries."""

        self._validate_scope(request.action)
        key = idempotency_key or str(uuid.uuid4())
        if not 8 <= len(key) <= 128:
            raise ValueError(
                "idempotency_key must be between 8 and 128 characters"
            )
        payload = self._request(
            "POST",
            "/tool-requests",
            {
                "action": request.action,
                "target": request.target,
                "payload": request.payload,
                "dry_run": request.dry_run,
            },
            extra_headers={"Idempotency-Key": key},
            retryable=True,
        )
        return ToolRequestResult.from_dict(payload)

    def get_request(self, request_id: str) -> ToolRequestResult:
        """Retrieve one agent-owned request."""

        encoded = urllib.parse.quote(request_id, safe="")
        payload = self._request(
            "GET",
            f"/tool-requests/{encoded}",
            None,
            retryable=True,
        )
        return ToolRequestResult.from_dict(payload)

    def _validate_scope(self, action: str) -> None:
        if self.scopes is not None and action not in self.scopes:
            raise ScopeValidationError(
                f"Action {action!r} is outside this client's declared scopes."
            )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        retryable: bool,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Agent-Name": self.agent_name,
            "X-Agent-Key": self._credential,
        }
        headers.update(extra_headers or {})
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        attempts = self.max_retries + 1 if retryable else 1

        for attempt in range(attempts):
            try:
                status, response = self._transport(
                    method,
                    f"{self.base_url}{path}",
                    headers,
                    body,
                    self.timeout,
                )
            except (OSError, TimeoutError, socket.timeout) as error:
                if attempt + 1 < attempts:
                    self._backoff(attempt)
                    continue
                raise RequestError("GreyGuard is unavailable.") from error

            if 200 <= status < 300:
                return response
            if status in _RETRYABLE_STATUS_CODES and attempt + 1 < attempts:
                self._backoff(attempt)
                continue
            self._raise_for_status(status, response)

        raise RequestError("GreyGuard request failed after retries.")

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(0.2 * (2**attempt))

    @staticmethod
    def _raise_for_status(status: int, response: dict[str, Any]) -> None:
        detail = response.get("detail", "GreyGuard rejected the request.")
        if status == 401:
            raise AuthenticationError(str(detail))
        if status == 403:
            raise AuthorizationError(str(detail))
        raise RequestError(str(detail), status_code=status, details=response)

    @staticmethod
    def _urlopen_transport(method, url, headers, body, timeout):
        request = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                return response.status, json.loads(raw or b"{}")
        except urllib.error.HTTPError as error:
            raw = error.read()
            try:
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                payload = {"detail": "GreyGuard returned an invalid response."}
            return error.code, payload
