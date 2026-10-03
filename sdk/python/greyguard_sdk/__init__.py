"""Official Python client for the GreyGuard agent security gateway."""

from .client import GreyGuardClient, redact
from .errors import (
    AuthenticationError,
    AuthorizationError,
    GreyGuardError,
    RequestError,
    ScopeValidationError,
)
from .models import PolicyEvaluation, ToolRequest, ToolRequestResult

__version__ = "0.1.0"

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "GreyGuardClient",
    "GreyGuardError",
    "PolicyEvaluation",
    "RequestError",
    "ScopeValidationError",
    "ToolRequest",
    "ToolRequestResult",
    "redact",
]
