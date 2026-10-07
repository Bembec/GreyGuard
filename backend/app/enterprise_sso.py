"""Enterprise OIDC sign-in: Authorization Code flow with PKCE.

Builds the actual sign-in flow on top of the identity-provider configuration and role-mapping
storage already in enterprise_identity.py (which deliberately never stores a client secret -
every provider here is treated as a public client authenticated by PKCE, not a client secret).

Security properties, each with the specific requirement it satisfies:

- The signing algorithm is never taken from the token alone: only RS256/ES256 are ever permitted
  (ALLOWED_ALGORITHMS), and the matched JWK's key type is cross-checked against it before the key
  is used, closing the classic alg/key-type confusion hole (e.g. a token claiming RS256 but
  pointing at an EC key, or any token claiming "none" or an HMAC algorithm).
- Every discovery/JWKS/token-endpoint call goes through outbound_delivery, so it inherits HTTPS
  enforcement, SSRF/DNS-rebinding protection, no-redirect-following, and bounded timeouts for
  free; there is no separate network path in this module.
- state/nonce/PKCE verifier are stored server-side keyed by state, single-use (claimed
  atomically, mirroring the queue "claim" pattern elsewhere in this codebase) and short-lived
  (LOGIN_ATTEMPT_TTL_SECONDS).
- The redirect_uri is never accepted from the caller; it is always the one fixed,
  operator-configured value (GREYGUARD_SSO_REDIRECT_URI), closing the open-redirect-via-
  redirect_uri class of attack entirely rather than trying to validate an attacker-supplied one.
- No ID token, access token, authorization code, client secret, state, nonce, or PKCE verifier
  value is ever written to the evidence table or included in any exception message raised here.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import jwt

from . import db_compat as sqlite3
from .admin_auth import issue_sso_session, provision_sso_administrator
from .database import database_path
from .enterprise_identity import initialize_enterprise_identity, list_providers, list_role_mappings
from .outbound_delivery import (
    DeliveryError,
    PermanentDeliveryError,
    SSRFBlocked,
    fetch_json,
    record_evidence,
    send_form_urlencoded,
)

ALLOWED_ALGORITHMS = {"RS256", "ES256"}
ALGORITHM_KEY_TYPES = {"RS256": "RSA", "ES256": "EC"}
CLOCK_SKEW_SECONDS = 60
LOGIN_ATTEMPT_TTL_SECONDS = 600
JWKS_CACHE_TTL_SECONDS = 600
DISCOVERY_CACHE_TTL_SECONDS = 3600


class SSOError(Exception):
    """A sign-in attempt was rejected for a reason safe to show the administrator."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def initialize_enterprise_sso() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS oidc_login_attempts(
            state TEXT PRIMARY KEY, provider_id TEXT NOT NULL, nonce TEXT NOT NULL,
            code_verifier TEXT NOT NULL, redirect_uri TEXT NOT NULL,
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL, consumed_at TEXT)""")


# -- bounded, process-local caches for discovery documents and JWKS ----------

_discovery_cache: dict[str, tuple[float, dict]] = {}
_jwks_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def _redirect_uri() -> str:
    value = os.environ.get("GREYGUARD_SSO_REDIRECT_URI", "").strip()
    if not value.startswith("https://") and not value.startswith("http://localhost"):
        raise SSOError("Enterprise SSO is not configured: GREYGUARD_SSO_REDIRECT_URI must be set to an HTTPS callback URL.")
    return value


def _provider_or_fail(provider_id: str) -> dict:
    initialize_enterprise_identity()
    provider = next((item for item in list_providers() if item["provider_id"] == provider_id), None)
    if not provider or not provider["enabled"]:
        raise SSOError("Identity provider is not available.")
    return provider


def _get_discovery(provider: dict, *, force_refresh: bool = False) -> dict:
    key = provider["provider_id"]
    now = time.monotonic()
    if not force_refresh:
        with _cache_lock:
            cached = _discovery_cache.get(key)
        if cached and now - cached[0] < DISCOVERY_CACHE_TTL_SECONDS:
            return cached[1]
    try:
        document = fetch_json(provider["discovery_url"])
    except (DeliveryError, PermanentDeliveryError, SSRFBlocked) as error:
        raise SSOError("Identity provider discovery could not be retrieved.") from error
    for field in ("authorization_endpoint", "token_endpoint", "jwks_uri", "issuer"):
        if not isinstance(document.get(field), str) or not document[field].startswith("https://"):
            raise SSOError("Identity provider discovery document is missing a required HTTPS endpoint.")
    if document["issuer"].rstrip("/") != provider["issuer"].rstrip("/"):
        raise SSOError("Identity provider discovery document issuer does not match the configured issuer.")
    with _cache_lock:
        _discovery_cache[key] = (now, document)
    return document


def _get_jwks(provider: dict, *, force_refresh: bool = False) -> dict:
    key = provider["provider_id"]
    now = time.monotonic()
    if not force_refresh:
        with _cache_lock:
            cached = _jwks_cache.get(key)
        if cached and now - cached[0] < JWKS_CACHE_TTL_SECONDS:
            return cached[1]
    discovery = _get_discovery(provider)
    try:
        jwks = fetch_json(discovery["jwks_uri"])
    except (DeliveryError, PermanentDeliveryError, SSRFBlocked) as error:
        raise SSOError("Identity provider signing keys could not be retrieved.") from error
    if not isinstance(jwks.get("keys"), list):
        raise SSOError("Identity provider JWKS response is malformed.")
    with _cache_lock:
        _jwks_cache[key] = (now, jwks)
    return jwks


def _find_jwk(jwks: dict, kid: str | None) -> dict | None:
    keys = jwks.get("keys", [])
    if kid is not None:
        matches = [key for key in keys if key.get("kid") == kid]
    else:
        # No kid in the token header: only safe to proceed if there is exactly one candidate.
        matches = keys
    if len(matches) == 0:
        return None
    if len(matches) > 1:
        raise SSOError("Identity provider signing keys are ambiguous for this token.")
    return matches[0]


def _verify_id_token(id_token: str, provider: dict, expected_nonce: str) -> dict:
    try:
        header = jwt.get_unverified_header(id_token)
    except jwt.InvalidTokenError as error:
        raise SSOError("Identity provider token is malformed.") from error

    alg = header.get("alg")
    if alg not in ALLOWED_ALGORITHMS:
        # Covers "none", HS256, and anything else: the algorithm is validated against this
        # fixed allow-list, never trusted from the token, and HS256/none are always rejected.
        raise SSOError("Identity provider token uses an unsupported signing algorithm.")

    kid = header.get("kid")
    jwks = _get_jwks(provider)
    jwk = _find_jwk(jwks, kid)
    if jwk is None:
        # One controlled refresh to tolerate legitimate key rotation, then fail closed.
        jwks = _get_jwks(provider, force_refresh=True)
        jwk = _find_jwk(jwks, kid)
    if jwk is None:
        raise SSOError("Identity provider signing key is unknown.")

    if jwk.get("kty") != ALGORITHM_KEY_TYPES[alg]:
        raise SSOError("Identity provider signing key type does not match the token's algorithm.")
    if jwk.get("alg") and jwk["alg"] != alg:
        raise SSOError("Identity provider signing key algorithm does not match the token header.")

    try:
        public_key = jwt.PyJWK.from_dict(jwk, algorithm=alg).key
    except (jwt.InvalidKeyError, ValueError, KeyError, TypeError) as error:
        raise SSOError("Identity provider signing key could not be parsed.") from error

    try:
        claims = jwt.decode(
            id_token,
            key=public_key,
            algorithms=[alg],  # the single algorithm this function already validated above
            issuer=provider["issuer"],
            audience=provider["client_id"],
            leeway=CLOCK_SKEW_SECONDS,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError as error:
        raise SSOError("Identity provider token has expired.") from error
    except jwt.ImmatureSignatureError as error:
        raise SSOError("Identity provider token is not yet valid.") from error
    except jwt.InvalidTokenError as error:
        raise SSOError("Identity provider token failed verification.") from error

    audience_claim = claims.get("aud")
    if isinstance(audience_claim, list) and len(audience_claim) > 1:
        if claims.get("azp") != provider["client_id"]:
            raise SSOError("Identity provider token has multiple audiences without a matching azp claim.")

    token_nonce = claims.get("nonce")
    if not isinstance(token_nonce, str) or not hmac.compare_digest(token_nonce, expected_nonce):
        raise SSOError("Identity provider token nonce does not match this sign-in attempt.")

    return claims


def _check_domain_allowed(provider: dict, email: str) -> None:
    allowed = provider.get("allowed_domains") or []
    if not allowed:
        return
    domain = email.rsplit("@", 1)[-1].lower()
    if domain not in allowed:
        raise SSOError("This email domain is not permitted to sign in through this identity provider.")


def _resolve_role(provider_id: str, claims: dict) -> str:
    mappings = sorted(
        (mapping for mapping in list_role_mappings() if mapping["provider_id"] == provider_id),
        key=lambda mapping: mapping["priority"],
    )
    for mapping in mappings:
        claim_value = claims.get(mapping["claim_name"])
        values = claim_value if isinstance(claim_value, list) else [claim_value]
        if mapping["claim_value"] in {str(value) for value in values if value is not None}:
            return mapping["greyguard_role"]
    raise SSOError("This identity does not map to any configured GreyGuard role.")


def _generate_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def list_enabled_providers_for_login() -> list[dict]:
    """Public, pre-authentication listing: only what a login page needs to show an SSO button."""
    initialize_enterprise_identity()
    return [{"provider_id": item["provider_id"], "name": item["name"]} for item in list_providers() if item["enabled"]]


def begin_login(provider_id: str) -> dict:
    initialize_enterprise_sso()
    provider = _provider_or_fail(provider_id)
    redirect_uri = _redirect_uri()
    discovery = _get_discovery(provider)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = _generate_pkce()
    now = _utc_now()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO oidc_login_attempts VALUES(?,?,?,?,?,?,?,NULL)",
            (state, provider_id, nonce, verifier, redirect_uri, now.isoformat(),
             (now + timedelta(seconds=LOGIN_ATTEMPT_TTL_SECONDS)).isoformat()),
        )
    record_evidence("ENTERPRISE_SSO", provider_id, "LOGIN_BEGIN")
    query = urlencode({
        "response_type": "code",
        "client_id": provider["client_id"],
        "redirect_uri": redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return {"authorization_url": f"{discovery['authorization_endpoint']}?{query}"}


def _consume_login_attempt(state: str) -> dict:
    now = _utc_now().isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM oidc_login_attempts WHERE state=?", (state,)).fetchone()
        if not row:
            raise SSOError("Sign-in request is invalid or has expired.")
        # Atomic single-use claim: only the first caller for a given state can ever succeed here,
        # even under concurrent/replayed callback requests.
        changed = connection.execute(
            "UPDATE oidc_login_attempts SET consumed_at=? WHERE state=? AND consumed_at IS NULL",
            (now, state),
        ).rowcount
        if not changed:
            raise SSOError("Sign-in request has already been used.")
        if row["expires_at"] <= now:
            raise SSOError("Sign-in request has expired.")
    return dict(row)


def complete_login(state: str, code: str, device_name: str = "Unknown device", ip_address: str = "") -> dict:
    """Exchange the authorization code, verify the ID token, and issue a GreyGuard session.

    Never raises anything other than SSOError to the caller; the original cause is chained for
    server-side diagnostics but every message surfaced here is deliberately generic enough to be
    shown to the person signing in without leaking provider-internal detail.
    """
    initialize_enterprise_sso()
    provider_id_for_evidence = "unknown"
    try:
        attempt = _consume_login_attempt(state)
        provider_id_for_evidence = attempt["provider_id"]
        provider = _provider_or_fail(attempt["provider_id"])
        discovery = _get_discovery(provider)

        try:
            token_response = send_form_urlencoded(discovery["token_endpoint"], {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": attempt["redirect_uri"],
                "client_id": provider["client_id"],
                "code_verifier": attempt["code_verifier"],
            })
        except (DeliveryError, PermanentDeliveryError, SSRFBlocked) as error:
            raise SSOError("Identity provider token exchange failed.") from error

        try:
            token_body = json.loads(token_response["body"])
        except ValueError as error:
            raise SSOError("Identity provider token response was not valid JSON.") from error

        id_token = token_body.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise SSOError("Identity provider did not return an ID token.")

        claims = _verify_id_token(id_token, provider, attempt["nonce"])

        email = claims.get("email")
        if not isinstance(email, str) or "@" not in email:
            raise SSOError("Identity provider token did not include a usable email claim.")
        if claims.get("email_verified") is False:
            raise SSOError("Identity provider reports this email address is not verified.")

        _check_domain_allowed(provider, email)
        role = _resolve_role(provider["provider_id"], claims)
        display_name = claims.get("name") if isinstance(claims.get("name"), str) else email

        provision_sso_administrator(email, display_name, role, provider["provider_id"])
        session = issue_sso_session(email, device_name, ip_address)
    except SSOError as error:
        record_evidence("ENTERPRISE_SSO", provider_id_for_evidence, "LOGIN_FAILURE", detail={"error": str(error)})
        raise
    except ValueError as error:
        # provision_sso_administrator/issue_sso_session raise plain ValueError for "the matched
        # local account isn't ACTIVE" - surfaced as the same generic failure, not a stack trace.
        record_evidence("ENTERPRISE_SSO", provider_id_for_evidence, "LOGIN_FAILURE", detail={"error": str(error)})
        raise SSOError("Administrator authentication failed.") from error

    record_evidence("ENTERPRISE_SSO", provider["provider_id"], "LOGIN_SUCCESS")
    return session
