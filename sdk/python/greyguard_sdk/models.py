"""Typed request and response models for GreyGuard agents."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolRequest:
    """A controlled action an agent wants GreyGuard to execute."""

    action: str
    target: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False


@dataclass(frozen=True)
class PolicyEvaluation:
    """GreyGuard's policy decision for an action."""

    action: str
    policy_decision: str
    approval: str | None
    risk_score: int | float | None
    raw: dict[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        return cls(
            action=str(value.get("action", "")),
            policy_decision=str(value.get("policy_decision", "UNKNOWN")),
            approval=value.get("approval"),
            risk_score=value.get("risk_score"),
            raw=value,
        )


@dataclass(frozen=True)
class ToolRequestResult:
    """The persisted state of a controlled tool request."""

    request_id: str
    action: str
    approval_status: str | None
    execution_status: str | None
    policy_decision: str | None
    raw: dict[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: dict[str, Any]):
        request = value.get("request", value)
        return cls(
            request_id=str(request.get("request_id", "")),
            action=str(request.get("action", "")),
            approval_status=request.get("approval_status", request.get("approval")),
            execution_status=request.get("execution_status"),
            policy_decision=request.get("policy_decision"),
            raw=value,
        )
