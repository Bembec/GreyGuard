import json
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from backend.app import admin_auth, enterprise_identity, enterprise_sso
from backend.app import outbound_delivery as od

ISSUER = "https://idp.example.test"
CLIENT_ID = "greyguard-client"
REDIRECT_URI = "https://console.example.test/auth/sso/callback"


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    path = tmp_path / "sso.db"
    monkeypatch.setattr(admin_auth, "database_path", path)
    monkeypatch.setattr(enterprise_identity, "database_path", path)
    monkeypatch.setattr(enterprise_sso, "database_path", path)
    monkeypatch.setattr(od, "database_path", path)
    monkeypatch.setenv("GREYGUARD_SSO_REDIRECT_URI", REDIRECT_URI)
    admin_auth.initialize_admin_auth()
    enterprise_identity.initialize_enterprise_identity()
    enterprise_sso.initialize_enterprise_sso()
    enterprise_sso._discovery_cache.clear()
    enterprise_sso._jwks_cache.clear()
    owner = admin_auth.create_administrator("owner@example.com", "Owner", "PLATFORM_ADMIN", "StrongPassword123!")
    provider = enterprise_identity.save_provider(owner["admin_id"], "Test IdP", ISSUER, CLIENT_ID, ["example.com"])
    enterprise_identity.add_role_mapping(owner["admin_id"], provider["provider_id"], "groups", "security-team", "SECURITY_ANALYST")
    return provider


def _rsa_keypair(kid="rsa-key-1"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(key.public_key()))
    jwk["kid"] = kid
    return key, jwk


def _ec_keypair(kid="ec-key-1"):
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(ECAlgorithm(ECAlgorithm.SHA256).to_jwk(key.public_key()))
    jwk["kid"] = kid
    return key, jwk


def _claims(**overrides):
    now = int(time.time())
    base = {
        "iss": ISSUER, "aud": CLIENT_ID, "sub": "user-1", "email": "person@example.com",
        "email_verified": True, "name": "Example Person", "groups": ["security-team"],
        "iat": now, "exp": now + 300,
    }
    base.update(overrides)
    return base


def _sign(key, alg, kid, claims, header_overrides=None):
    headers = {"kid": kid}
    if header_overrides:
        headers.update(header_overrides)
    return jwt.encode(claims, key, algorithm=alg, headers=headers)


def _discovery_document(**overrides):
    document = {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "jwks_uri": f"{ISSUER}/jwks",
    }
    document.update(overrides)
    return document


def _install_fetch_json(monkeypatch, jwks_sequence, discovery=None):
    """Simulates the IdP's discovery + JWKS endpoints. `jwks_sequence` may hold more than one
    JWKS document to simulate key rotation: each call to the jwks_uri pops the next one, the
    last one is reused for any further call."""
    document = discovery or _discovery_document()
    remaining = list(jwks_sequence)

    def _fetch(url, **_kwargs):
        if url == document.get("discovery_url_marker"):
            pass
        if url.endswith("/.well-known/openid-configuration"):
            return document
        if url == document["jwks_uri"]:
            if len(remaining) > 1:
                return remaining.pop(0)
            return remaining[0]
        raise AssertionError(f"unexpected fetch_json call: {url}")

    monkeypatch.setattr(enterprise_sso, "fetch_json", _fetch)
    return document


def _install_token_response(monkeypatch, id_token, status_code=200):
    def _send(url, fields, **_kwargs):
        assert url == f"{ISSUER}/token"
        assert fields["grant_type"] == "authorization_code"
        assert "code_verifier" in fields and fields["code_verifier"]
        body = json.dumps({"id_token": id_token, "token_type": "Bearer"}).encode()
        return {"status_code": status_code, "body": body}

    monkeypatch.setattr(enterprise_sso, "send_form_urlencoded", _send)


def _begin(monkeypatch, provider, jwks_sequence, discovery=None):
    _install_fetch_json(monkeypatch, jwks_sequence, discovery)
    result = enterprise_sso.begin_login(provider["provider_id"])
    query = parse_qs(urlsplit(result["authorization_url"]).query)
    return {"authorization_url": result["authorization_url"], "state": query["state"][0], "nonce": query["nonce"][0]}


# -- begin_login ---------------------------------------------------------

def test_begin_login_builds_pkce_authorization_url(isolated, monkeypatch):
    begin = _begin(monkeypatch, isolated, [{"keys": []}])
    assert begin["authorization_url"].startswith(f"{ISSUER}/authorize?")
    query = parse_qs(urlsplit(begin["authorization_url"]).query)
    assert query["response_type"] == ["code"]
    assert query["client_id"] == [CLIENT_ID]
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["code_challenge"][0]) > 20
    assert len(query["state"][0]) > 20
    assert len(query["nonce"][0]) > 20
    with sqlite3.connect(enterprise_sso.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM oidc_login_attempts").fetchone()[0] == 1


def test_begin_login_requires_redirect_uri_configuration(isolated, monkeypatch):
    monkeypatch.delenv("GREYGUARD_SSO_REDIRECT_URI", raising=False)
    with pytest.raises(enterprise_sso.SSOError, match="GREYGUARD_SSO_REDIRECT_URI"):
        enterprise_sso.begin_login(isolated["provider_id"])


def test_begin_login_rejects_disabled_provider(isolated, monkeypatch):
    enterprise_identity.save_provider("owner@example.com", "Test IdP", ISSUER, CLIENT_ID, ["example.com"], enabled=False)
    with pytest.raises(enterprise_sso.SSOError, match="not available"):
        enterprise_sso.begin_login(isolated["provider_id"])


def test_begin_login_rejects_unknown_provider(isolated):
    with pytest.raises(enterprise_sso.SSOError):
        enterprise_sso.begin_login("idp_does_not_exist")


# -- successful sign-in ---------------------------------------------------

def test_complete_login_rs256_happy_path(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"]))
    _install_token_response(monkeypatch, token)
    session = enterprise_sso.complete_login(begin["state"], "authcode-1")
    assert session["administrator"]["email"] == "person@example.com"
    assert session["administrator"]["role"] == "SECURITY_ANALYST"
    assert session["access_token"].startswith("gga_")


def test_complete_login_es256_happy_path(isolated, monkeypatch):
    key, jwk = _ec_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "ES256", jwk["kid"], _claims(nonce=begin["nonce"]))
    _install_token_response(monkeypatch, token)
    session = enterprise_sso.complete_login(begin["state"], "authcode-1")
    assert session["administrator"]["role"] == "SECURITY_ANALYST"


def test_complete_login_jit_provisions_new_administrator(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"], sub="new-user", email="new.person@example.com"))
    _install_token_response(monkeypatch, token)
    assert admin_auth.get_administrator_by_email("new.person@example.com") is None
    enterprise_sso.complete_login(begin["state"], "authcode-1")
    provisioned = admin_auth.get_administrator_by_email("new.person@example.com")
    assert provisioned is not None
    assert provisioned["sso_provider_id"] == isolated["provider_id"]


def test_complete_login_records_success_evidence_without_secrets(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"]))
    _install_token_response(monkeypatch, token)
    enterprise_sso.complete_login(begin["state"], "super-secret-auth-code")
    with sqlite3.connect(enterprise_sso.database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute("SELECT * FROM outbound_delivery_evidence")]
    assert any(row["event"] == "LOGIN_SUCCESS" for row in rows)
    # SSO login evidence is install-level: no org is resolvable during the handshake.
    assert all(row["org_id"] is None for row in rows)
    blob = json.dumps(rows)
    assert "super-secret-auth-code" not in blob
    assert begin["nonce"] not in blob
    assert token not in blob


# -- single-use / expiry of the login attempt -----------------------------

def test_state_is_single_use(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"]))
    _install_token_response(monkeypatch, token)
    enterprise_sso.complete_login(begin["state"], "authcode-1")
    with pytest.raises(enterprise_sso.SSOError, match="already been used"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_unknown_state_is_rejected(isolated):
    with pytest.raises(enterprise_sso.SSOError, match="invalid or has expired"):
        enterprise_sso.complete_login("not-a-real-state", "authcode-1")


def test_expired_login_attempt_is_rejected(isolated, monkeypatch):
    begin = _begin(monkeypatch, isolated, [{"keys": []}])
    with sqlite3.connect(enterprise_sso.database_path) as connection:
        connection.execute("UPDATE oidc_login_attempts SET expires_at='2000-01-01T00:00:00+00:00' WHERE state=?", (begin["state"],))
    with pytest.raises(enterprise_sso.SSOError, match="expired"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


# -- tampered / malformed tokens -------------------------------------------

def test_tampered_signature_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"]))
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-4]}AAAA"
    _install_token_response(monkeypatch, tampered)
    with pytest.raises(enterprise_sso.SSOError, match="failed verification"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_none_algorithm_is_rejected(isolated, monkeypatch):
    begin = _begin(monkeypatch, isolated, [{"keys": []}])
    forged = jwt.encode(_claims(nonce=begin["nonce"]), key="", algorithm="none")
    _install_token_response(monkeypatch, forged)
    with pytest.raises(enterprise_sso.SSOError, match="unsupported signing algorithm"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_hs256_algorithm_confusion_is_rejected(isolated, monkeypatch):
    _, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    # The classic attack shape: an attacker who can see the provider's public key tries to get it
    # accepted as an HMAC secret by claiming alg=HS256. PyJWT's own encode() refuses to build a
    # token with a JWK-shaped string as the HMAC key (it has the identical defense built in), so
    # this uses a plain extracted value (the modulus) as the "secret" to reach our code path -
    # the point under test is that enterprise_sso rejects the HS256 header before any key or
    # signature is even considered, regardless of what secret was used to sign it.
    forged = jwt.encode(_claims(nonce=begin["nonce"]), key=jwk["n"], algorithm="HS256", headers={"kid": jwk["kid"]})
    _install_token_response(monkeypatch, forged)
    with pytest.raises(enterprise_sso.SSOError, match="unsupported signing algorithm"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_wrong_key_type_for_algorithm_is_rejected(isolated, monkeypatch):
    _, ec_jwk = _ec_keypair(kid="shared-kid")
    rsa_key, rsa_jwk = _rsa_keypair(kid="shared-kid")
    # The JWKS entry under this kid is an EC key, but the token header claims RS256.
    begin = _begin(monkeypatch, isolated, [{"keys": [ec_jwk]}])
    token = _sign(rsa_key, "RS256", "shared-kid", _claims(nonce=begin["nonce"]))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="key type does not match"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_unknown_kid_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", "a-kid-not-in-jwks", _claims(nonce=begin["nonce"]))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="signing key is unknown"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_ambiguous_kid_is_rejected(isolated, monkeypatch):
    key, jwk1 = _rsa_keypair(kid="dup")
    _, jwk2 = _rsa_keypair(kid="dup")
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk1, jwk2]}])
    token = _sign(key, "RS256", "dup", _claims(nonce=begin["nonce"]))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="ambiguous"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_malformed_jwk_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    broken_jwk = {"kty": "RSA", "kid": jwk["kid"]}  # missing n/e
    begin = _begin(monkeypatch, isolated, [{"keys": [broken_jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"]))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="could not be parsed"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


# -- claim validation -------------------------------------------------------

def test_expired_token_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    past = int(time.time()) - 3600
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"], iat=past - 10, exp=past))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="expired"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_future_issued_token_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    future = int(time.time()) + 3600
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"], iat=future, exp=future + 300))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="not yet valid"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_wrong_issuer_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"], iss="https://attacker.example"))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="failed verification"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_wrong_audience_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"], aud="some-other-client"))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="failed verification"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_missing_required_claim_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    claims = _claims(nonce=begin["nonce"])
    del claims["sub"]
    token = _sign(key, "RS256", jwk["kid"], claims)
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="failed verification"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_nonce_mismatch_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce="a-different-nonce-entirely"))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="nonce does not match"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_multiple_audiences_without_matching_azp_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"], aud=[CLIENT_ID, "other-client"], azp="other-client"))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="azp"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_multiple_audiences_with_matching_azp_is_accepted(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"], aud=[CLIENT_ID, "other-client"], azp=CLIENT_ID))
    _install_token_response(monkeypatch, token)
    session = enterprise_sso.complete_login(begin["state"], "authcode-1")
    assert session["administrator"]["email"] == "person@example.com"


def test_unverified_email_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"], email_verified=False))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="not verified"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_disallowed_email_domain_is_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"], email="person@not-allowed.test"))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="domain is not permitted"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_unmapped_claims_are_rejected(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"], groups=["no-such-group"]))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError, match="does not map to any configured"):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


def test_suspended_existing_administrator_cannot_sso(isolated, monkeypatch):
    key, jwk = _rsa_keypair()
    admin_auth.create_administrator("person@example.com", "Person", "SECURITY_ANALYST", "StrongPassword123!")
    with sqlite3.connect(enterprise_sso.database_path) as connection:
        connection.execute("UPDATE administrators SET status='SUSPENDED' WHERE email='person@example.com'")
    begin = _begin(monkeypatch, isolated, [{"keys": [jwk]}])
    token = _sign(key, "RS256", jwk["kid"], _claims(nonce=begin["nonce"]))
    _install_token_response(monkeypatch, token)
    with pytest.raises(enterprise_sso.SSOError):
        enterprise_sso.complete_login(begin["state"], "authcode-1")


# -- JWKS rotation, retrieval failures, and unsafe discovery ----------------

def test_jwks_rotation_triggers_one_controlled_refresh(isolated, monkeypatch):
    old_key, old_jwk = _rsa_keypair(kid="old-key")
    new_key, new_jwk = _rsa_keypair(kid="new-key")
    # First JWKS fetch only has the old key; the token is signed with the new one. The module
    # must refetch once (simulating the IdP having rotated) rather than failing immediately.
    begin = _begin(monkeypatch, isolated, [{"keys": [old_jwk]}, {"keys": [old_jwk, new_jwk]}])
    token = _sign(new_key, "RS256", "new-key", _claims(nonce=begin["nonce"]))
    _install_token_response(monkeypatch, token)
    session = enterprise_sso.complete_login(begin["state"], "authcode-1")
    assert session["administrator"]["email"] == "person@example.com"


def test_discovery_retrieval_failure_is_reported_as_sso_error(isolated, monkeypatch):
    def _boom(url, **_kwargs):
        raise od.DeliveryError("simulated timeout")

    monkeypatch.setattr(enterprise_sso, "fetch_json", _boom)
    with pytest.raises(enterprise_sso.SSOError, match="could not be retrieved"):
        enterprise_sso.begin_login(isolated["provider_id"])


def test_jwks_retrieval_failure_is_reported_as_sso_error(isolated, monkeypatch):
    document = _discovery_document()

    def _fetch(url, **_kwargs):
        if url.endswith("/.well-known/openid-configuration"):
            return document
        raise od.DeliveryError("simulated timeout")

    monkeypatch.setattr(enterprise_sso, "fetch_json", _fetch)
    with pytest.raises(enterprise_sso.SSOError, match="could not be retrieved"):
        enterprise_sso._get_jwks(isolated)


def test_unsafe_jwks_uri_is_rejected_at_discovery_time(isolated, monkeypatch):
    unsafe = _discovery_document(jwks_uri="http://attacker.example/jwks")
    with pytest.raises(enterprise_sso.SSOError, match="HTTPS endpoint"):
        _begin(monkeypatch, isolated, [{"keys": []}], discovery=unsafe)


def test_discovery_issuer_mismatch_is_rejected(isolated, monkeypatch):
    mismatched = _discovery_document(issuer="https://a-different-issuer.example")
    with pytest.raises(enterprise_sso.SSOError, match="issuer does not match"):
        _begin(monkeypatch, isolated, [{"keys": []}], discovery=mismatched)


def test_list_enabled_providers_for_login_excludes_disabled(isolated):
    enterprise_identity.save_provider("owner@example.com", "Disabled IdP", "https://disabled.example", "client-x", enabled=False, allow_any_domain=True)
    names = {item["name"] for item in enterprise_sso.list_enabled_providers_for_login()}
    assert "Test IdP" in names
    assert "Disabled IdP" not in names
