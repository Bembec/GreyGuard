"""Certificate-based agent authentication (optional mTLS).

GreyGuard's reverse proxy (nginx) is the TLS termination point and, when agent mTLS is enabled,
the sole verifier of the client certificate's chain and validity period -- see
docs/agent-certificate-authentication.md for the full nginx/header contract this module relies
on. This module never parses or validates a certificate chain itself: it trusts nginx's verdict
(forwarded via the X-SSL-Client-Verify header, which nginx unconditionally overwrites on every
proxied request) and independently re-derives the certificate's registered fingerprint from the
forwarded certificate text, matching it against a workload identity explicitly bound to a
registered agent.

This is strictly additive. An agent that never presents a certificate authenticates exactly as
it always has, through main.authenticate_agent (X-Agent-Name/X-Agent-Key). Nothing here can make
a key-based authentication succeed that would not have succeeded before, and this path is itself
disabled by default (GREYGUARD_TRUST_CLIENT_CERT_HEADERS) until an operator explicitly turns it
on alongside the matching nginx configuration.
"""
from __future__ import annotations

import os

from .enterprise_identity import (
    certificate_thumbprint,
    find_active_workload_identity_by_thumbprint,
    mark_workload_identity_authenticated,
)
from .main import (
    AgentAuthenticationError,
    get_agent_identity,
    normalize_agent_name,
    normalize_action,
    public_identity,
    record_authentication_event,
)

VERIFIED_STATUS = "SUCCESS"


def trust_enabled() -> bool:
    return os.environ.get("GREYGUARD_TRUST_CLIENT_CERT_HEADERS", "false").strip().lower() == "true"


def certificate_was_presented(verify_header: str | None) -> bool:
    """True whenever the proxy forwarded any client-certificate verdict at all, including a
    failed one. Callers use this to decide whether to attempt certificate authentication at all
    rather than silently falling back to key-based auth: a client that presented a certificate
    and failed verification must not be quietly retried against X-Agent-Key as if nothing
    happened, but a client that never presented one (the overwhelming majority of existing
    agents, always) must fall back exactly as it did before this feature existed.
    """
    return bool(verify_header) and verify_header.strip().upper() != "NONE"


def _fail(claimed_agent_name, action, reason) -> None:
    """Record the specific reason as evidence, but raise a uniform message - mirroring
    main.authentication_failed's own "do not tell the caller which check failed" convention."""
    normalized_claim = normalize_agent_name(claimed_agent_name) if claimed_agent_name else None
    record_authentication_event(
        claimed_agent_name=normalized_claim,
        authenticated_agent_name=None,
        action=action,
        outcome="CERTIFICATE_AUTHENTICATION_FAILED",
        reason=reason,
    )
    raise AgentAuthenticationError("Agent certificate authentication failed.")


def authenticate_agent_by_certificate(verify_header, client_cert_pem, claimed_agent_name=None, action=None) -> dict:
    """Authenticate an agent from a proxy-verified client certificate.

    Returns the same public-identity shape as main.authenticate_agent, so callers (and the
    scope-enforcement step that follows) treat a certificate-authenticated agent identically to
    a key-authenticated one.
    """
    if not trust_enabled():
        _fail(claimed_agent_name, action, "Certificate authentication is not enabled on this deployment.")

    if not verify_header or verify_header.strip().upper() != VERIFIED_STATUS:
        _fail(claimed_agent_name, action, f"Reverse proxy did not report a verified client certificate (status: {verify_header or 'none'}).")

    if not client_cert_pem or "BEGIN CERTIFICATE" not in client_cert_pem:
        _fail(claimed_agent_name, action, "Reverse proxy reported a verified certificate but forwarded no certificate text.")

    thumbprint = certificate_thumbprint(client_cert_pem)
    workload = find_active_workload_identity_by_thumbprint(thumbprint)
    if workload is None:
        _fail(claimed_agent_name, action, "Certificate does not match an active, agent-bound registered workload identity.")

    bound_agent_name = workload["agent_name"]

    if claimed_agent_name and normalize_agent_name(claimed_agent_name) != bound_agent_name:
        _fail(claimed_agent_name, action, "Claimed agent name does not match the certificate's bound agent.")

    identity = get_agent_identity(bound_agent_name)
    if identity is None or identity["credential_status"] != "ACTIVE":
        _fail(bound_agent_name, action, "Certificate-bound agent identity is revoked or missing.")

    mark_workload_identity_authenticated(workload["workload_id"])
    record_authentication_event(
        claimed_agent_name=bound_agent_name,
        authenticated_agent_name=bound_agent_name,
        action=action,
        outcome="CERTIFICATE_AUTHENTICATED",
        reason=f"Agent certificate verified by reverse proxy (workload {workload['workload_id']}).",
    )
    return public_identity(identity)


def authenticate_and_authorize_agent_by_certificate(verify_header, client_cert_pem, action, claimed_agent_name=None) -> dict:
    from .main import enforce_agent_scope  # local import: enforce_agent_scope records evidence via main itself

    identity = authenticate_agent_by_certificate(
        verify_header, client_cert_pem, claimed_agent_name, normalize_action(action),
    )
    normalized_action = enforce_agent_scope(identity, action)
    return {"identity": identity, "action": normalized_action}
