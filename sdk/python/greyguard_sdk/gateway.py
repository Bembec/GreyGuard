"""Gateway-side verification of GreyGuard policy bundles.

A customer-hosted gateway fetches signed bundles from the control plane (GET /gateways/bundle)
and enforces them locally. This module verifies a bundle and makes the local decision, failing
closed: a bundle past its valid_until (the node's offline allowance) denies everything, because a
revocation or emergency stop issued since then may not have reached this node.

Requires the optional dependency: pip install "greyguard-sdk[gateway]".
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

BUNDLE_SCHEMA = "greyguard.gateway.bundle.v1"


class BundleError(ValueError):
    """A bundle that must not be used."""


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_bundle(bundle: dict[str, Any], public_key: str, *, now: datetime | None = None,
                  last_issued_at: str | None = None, expected_node_id: str | None = None) -> dict[str, Any]:
    """Return the bundle's document if it is authentic, current, newer than the last applied
    bundle and meant for this node. Raise BundleError otherwise."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as error:  # pragma: no cover - depends on the environment
        raise BundleError('Install the gateway extra: pip install "greyguard-sdk[gateway]"') from error
    document = bundle.get("document")
    if bundle.get("algorithm") != "Ed25519" or not isinstance(document, dict) or document.get("schema") != BUNDLE_SCHEMA:
        raise BundleError("Unsupported or malformed policy bundle.")
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    try:
        Ed25519PublicKey.from_public_bytes(_unb64(public_key)).verify(_unb64(str(bundle.get("signature", ""))), canonical)
    except (InvalidSignature, ValueError) as error:
        raise BundleError("Policy bundle signature is invalid.") from error
    if expected_node_id and document.get("node_id") != expected_node_id:
        raise BundleError("This bundle was issued to a different gateway node.")
    current = now or datetime.now(timezone.utc)
    if datetime.fromisoformat(document["valid_until"]) <= current:
        raise BundleError("Policy bundle has expired; refresh it before enforcing anything.")
    if last_issued_at and document["issued_at"] <= last_issued_at:
        raise BundleError("Policy bundle is not newer than the one already applied.")
    return document


def decide(document: dict[str, Any] | None, agent_name: str, action: str, *, now: datetime | None = None) -> str:
    """ALLOW, REQUIRE_APPROVAL or BLOCK for one agent action under a verified bundle. With no
    bundle, or an expired one, the answer is BLOCK."""
    current = now or datetime.now(timezone.utc)
    if not document or datetime.fromisoformat(document["valid_until"]) <= current:
        return "BLOCK"
    emergency = document.get("emergency", {})
    if (emergency.get("global_deny") or agent_name in emergency.get("disabled_agents", [])
            or action in emergency.get("disabled_tools", []) or agent_name in document.get("revoked_agents", [])):
        return "BLOCK"
    decision = document.get("policy", {}).get("permissions", {}).get(action, "BLOCK")
    return decision if decision in ("ALLOW", "REQUIRE_APPROVAL") else "BLOCK"
