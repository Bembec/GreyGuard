import sqlite3
import urllib.parse

import pytest

from backend.app import agent_certificate_auth, database, enterprise_identity, main

FAKE_CERT_A = "-----BEGIN CERTIFICATE-----\nAAAAFAKECERTMATERIALFORAGENTA\n-----END CERTIFICATE-----"
FAKE_CERT_B = "-----BEGIN CERTIFICATE-----\nBBBBFAKECERTMATERIALFORAGENTB\n-----END CERTIFICATE-----"


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    path = tmp_path / "certauth.db"
    monkeypatch.setattr(database, "database_path", path)
    monkeypatch.setattr(enterprise_identity, "database_path", path)
    monkeypatch.setenv("GREYGUARD_TRUST_CLIENT_CERT_HEADERS", "true")
    database.initialize_database()
    enterprise_identity.initialize_enterprise_identity()
    return path


def _register_agent(agent_name="cert_agent", scopes=("read_file",), status=None):
    database.create_agent_identity(
        agent_name=agent_name,
        credential_salt="a" * 32,
        credential_hash="b" * 64,
        scopes=list(scopes),
        timestamp=main.current_timestamp(),
    )
    if status and status != "ACTIVE":
        with sqlite3.connect(database.database_path) as connection:
            connection.execute("UPDATE agent_identities SET credential_status=? WHERE agent_name=?", (status, agent_name))


def _register_workload(agent_name="cert_agent", pem=FAKE_CERT_A, days=90, actor="adm_test"):
    return enterprise_identity.create_workload_identity(actor, "Agent certificate", "CN=cert_agent", pem, ["read_file"], days, agent_name)


def _events():
    with sqlite3.connect(database.database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM authentication_events ORDER BY id")]


# -- certificate_was_presented -------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (None, False), ("", False), ("NONE", False), ("none", False),
    ("SUCCESS", True), ("FAILED:unable to verify the first certificate", True),
])
def test_certificate_was_presented(value, expected):
    assert agent_certificate_auth.certificate_was_presented(value) is expected


# -- positive ----------------------------------------------------------------

def test_positive_certificate_authentication(isolated):
    _register_agent()
    _register_workload()
    identity = agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", FAKE_CERT_A, action="read_file")
    assert identity["agent_name"] == "cert_agent"
    assert identity["credential_status"] == "ACTIVE"
    events = _events()
    assert events[-1]["outcome"] == "CERTIFICATE_AUTHENTICATED"


def test_positive_authentication_and_scope_enforcement(isolated):
    _register_agent(scopes=("read_file",))
    _register_workload()
    result = agent_certificate_auth.authenticate_and_authorize_agent_by_certificate("SUCCESS", FAKE_CERT_A, action="read_file")
    assert result["identity"]["agent_name"] == "cert_agent"
    assert result["action"] == "read_file"


def test_scope_denied_for_certificate_authenticated_agent(isolated):
    _register_agent(scopes=("read_file",))
    _register_workload()
    with pytest.raises(main.AgentScopeError):
        agent_certificate_auth.authenticate_and_authorize_agent_by_certificate("SUCCESS", FAKE_CERT_A, action="write_note")


def test_positive_authentication_with_nginx_percent_escaped_certificate(isolated):
    # nginx forwards the certificate via $ssl_client_escaped_cert, which RFC-3986 percent-escapes
    # the PEM text (real newlines become literal "%0A" sequences) because raw PEM cannot appear
    # in an HTTP header value. Registration (create_workload_identity) hashes the plain PEM an
    # admin pastes in, with real newlines - so this is what a real mTLS deployment actually sends,
    # not the same literal string used for registration like every other test in this file.
    _register_agent()
    _register_workload(pem=FAKE_CERT_A)
    escaped = urllib.parse.quote(FAKE_CERT_A, safe="")
    assert "%0A" in escaped
    identity = agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", escaped, action="read_file")
    assert identity["agent_name"] == "cert_agent"


def test_last_authenticated_at_is_updated_on_success(isolated):
    _register_agent()
    workload = _register_workload()
    assert workload["last_authenticated_at"] is None
    agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", FAKE_CERT_A, action="read_file")
    refreshed = enterprise_identity.get_workload_identity(workload["workload_id"])
    assert refreshed["last_authenticated_at"] is not None


# -- invalid ------------------------------------------------------------------

def test_unregistered_certificate_is_rejected(isolated):
    _register_agent()
    _register_workload(pem=FAKE_CERT_A)
    with pytest.raises(main.AgentAuthenticationError):
        agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", FAKE_CERT_B, action="read_file")


def test_failed_proxy_verification_is_rejected(isolated):
    _register_agent()
    _register_workload()
    with pytest.raises(main.AgentAuthenticationError):
        agent_certificate_auth.authenticate_agent_by_certificate("FAILED:unable to get local issuer certificate", FAKE_CERT_A, action="read_file")


def test_no_certificate_presented_is_rejected_when_called_directly(isolated):
    _register_agent()
    _register_workload()
    with pytest.raises(main.AgentAuthenticationError):
        agent_certificate_auth.authenticate_agent_by_certificate("NONE", FAKE_CERT_A, action="read_file")


def test_missing_certificate_text_despite_success_status_is_rejected(isolated):
    _register_agent()
    _register_workload()
    with pytest.raises(main.AgentAuthenticationError):
        agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", None, action="read_file")


def test_claimed_agent_name_mismatch_is_rejected(isolated):
    _register_agent("cert_agent")
    _register_agent("other_agent")
    _register_workload(agent_name="cert_agent")
    with pytest.raises(main.AgentAuthenticationError):
        agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", FAKE_CERT_A, claimed_agent_name="other_agent", action="read_file")


def test_certificate_bound_agent_revoked_credential_is_rejected(isolated):
    _register_agent(status="REVOKED")
    _register_workload()
    with pytest.raises(main.AgentAuthenticationError):
        agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", FAKE_CERT_A, action="read_file")


# -- spoofed headers ----------------------------------------------------------

def test_spoofed_headers_are_rejected_when_trust_is_disabled(isolated, monkeypatch):
    monkeypatch.setenv("GREYGUARD_TRUST_CLIENT_CERT_HEADERS", "false")
    _register_agent()
    _register_workload()
    # Even a perfectly well-formed, matching certificate must be refused outright if this
    # deployment has not explicitly opted into trusting these headers at all - simulating a
    # client that somehow reached the backend directly, bypassing nginx.
    with pytest.raises(main.AgentAuthenticationError):
        agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", FAKE_CERT_A, action="read_file")


def test_spoofed_headers_are_rejected_by_default(isolated, monkeypatch):
    monkeypatch.delenv("GREYGUARD_TRUST_CLIENT_CERT_HEADERS", raising=False)
    _register_agent()
    _register_workload()
    with pytest.raises(main.AgentAuthenticationError):
        agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", FAKE_CERT_A, action="read_file")


# -- expired and revoked workload identities ----------------------------------

def test_expired_certificate_binding_is_rejected(isolated):
    _register_agent()
    workload = _register_workload(days=1)
    with sqlite3.connect(database.database_path) as connection:
        connection.execute("UPDATE workload_identities SET expires_at='2000-01-01T00:00:00+00:00' WHERE workload_id=?", (workload["workload_id"],))
    with pytest.raises(main.AgentAuthenticationError):
        agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", FAKE_CERT_A, action="read_file")


def test_revoked_workload_identity_is_rejected(isolated):
    _register_agent()
    workload = _register_workload()
    enterprise_identity.revoke_workload_identity("adm_test", workload["workload_id"], "Certificate compromised")
    with pytest.raises(main.AgentAuthenticationError):
        agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", FAKE_CERT_A, action="read_file")


def test_revocation_is_recorded_as_evidence(isolated):
    _register_agent()
    workload = _register_workload()
    enterprise_identity.revoke_workload_identity("adm_test", workload["workload_id"], "Certificate compromised")
    revoked = enterprise_identity.get_workload_identity(workload["workload_id"])
    assert revoked["status"] == "REVOKED"
    assert revoked["revoked_at"] is not None
    with sqlite3.connect(database.database_path) as connection:
        connection.row_factory = sqlite3.Row
        events = [dict(row) for row in connection.execute("SELECT * FROM enterprise_identity_events WHERE event_type='WORKLOAD_IDENTITY_REVOKED'")]
    assert events and "Certificate compromised" in events[0]["detail"]


def test_revoking_an_already_revoked_identity_raises(isolated):
    _register_agent()
    workload = _register_workload()
    enterprise_identity.revoke_workload_identity("adm_test", workload["workload_id"], "First revocation")
    with pytest.raises(KeyError):
        enterprise_identity.revoke_workload_identity("adm_test", workload["workload_id"], "Second attempt")


def test_revoking_an_unknown_identity_raises(isolated):
    with pytest.raises(KeyError):
        enterprise_identity.revoke_workload_identity("adm_test", "wli_does_not_exist", "No such identity")


# -- authentication-failure evidence does not leak the specific reason --------

def test_failure_message_is_generic_but_evidence_is_detailed(isolated):
    _register_agent()
    _register_workload()
    try:
        agent_certificate_auth.authenticate_agent_by_certificate("SUCCESS", FAKE_CERT_B, action="read_file")
        assert False, "expected AgentAuthenticationError"
    except main.AgentAuthenticationError as error:
        assert str(error) == "Agent certificate authentication failed."
    events = _events()
    assert "does not match" in events[-1]["reason"]


# -- registration binding validation ------------------------------------------

def test_create_workload_identity_requires_a_real_registered_agent(isolated):
    with pytest.raises(KeyError):
        _register_workload(agent_name="no_such_agent")


def test_create_workload_identity_without_agent_binding_is_still_allowed(isolated):
    # Unbound workload identities (no agent_name) remain valid registration records; they are
    # simply never matched by certificate authentication (agent_name IS NOT NULL in the lookup).
    workload = enterprise_identity.create_workload_identity("adm_test", "Unbound", "CN=unbound", FAKE_CERT_A, ["read_file"])
    assert workload["agent_name"] is None
    assert enterprise_identity.find_active_workload_identity_by_thumbprint(enterprise_identity.certificate_thumbprint(FAKE_CERT_A)) is None
