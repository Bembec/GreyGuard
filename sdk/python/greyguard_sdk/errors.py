"""Typed exceptions raised by the GreyGuard Python SDK."""


class GreyGuardError(Exception):
    """Base class for all SDK errors."""


class AuthenticationError(GreyGuardError):
    """The supplied agent identity or credential was rejected."""


class AuthorizationError(GreyGuardError):
    """The authenticated agent is not authorized for the action."""


class RequestError(GreyGuardError):
    """GreyGuard could not complete an API request."""

    def __init__(self, message, *, status_code=None, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


class ScopeValidationError(GreyGuardError):
    """Local scope validation rejected an action before transmission."""
