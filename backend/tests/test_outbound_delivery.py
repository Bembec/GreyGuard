import json
import ssl
import threading
import datetime as dt
import http.server

import pytest

from backend.app import outbound_delivery as od


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(od, "database_path", tmp_path / "outbound.db")
    od.initialize_outbound_delivery()
    return od


def _fake_getaddrinfo(*ips):
    def _resolver(host, port, *_, **__):
        return [(None, None, None, None, (ip, port)) for ip in ips]
    return _resolver


# -- SSRF resolution ----------------------------------------------------------

def test_cloud_metadata_address_is_always_blocked(isolated, monkeypatch):
    monkeypatch.setattr(od.socket, "getaddrinfo", _fake_getaddrinfo("169.254.169.254"))
    with pytest.raises(od.SSRFBlocked):
        od.resolve_and_validate("metadata.internal", 443)


def test_loopback_address_is_always_blocked(isolated, monkeypatch):
    monkeypatch.setattr(od.socket, "getaddrinfo", _fake_getaddrinfo("127.0.0.1"))
    with pytest.raises(od.SSRFBlocked):
        od.resolve_and_validate("localhost", 443)


def test_link_local_address_is_always_blocked(isolated, monkeypatch):
    monkeypatch.setattr(od.socket, "getaddrinfo", _fake_getaddrinfo("169.254.1.1"))
    with pytest.raises(od.SSRFBlocked):
        od.resolve_and_validate("link-local.internal", 443)


def test_unspecified_and_multicast_addresses_are_blocked(isolated, monkeypatch):
    monkeypatch.setattr(od.socket, "getaddrinfo", _fake_getaddrinfo("0.0.0.0"))
    with pytest.raises(od.SSRFBlocked):
        od.resolve_and_validate("unspecified.internal", 443)
    monkeypatch.setattr(od.socket, "getaddrinfo", _fake_getaddrinfo("224.0.0.1"))
    with pytest.raises(od.SSRFBlocked):
        od.resolve_and_validate("multicast.internal", 443)


def test_private_address_is_blocked_without_an_allowlist_entry(isolated, monkeypatch):
    monkeypatch.setattr(od.socket, "getaddrinfo", _fake_getaddrinfo("10.0.0.5"))
    with pytest.raises(od.SSRFBlocked):
        od.resolve_and_validate("internal-siem.corp", 443)


def test_private_address_is_allowed_after_explicit_admin_allowlist(isolated, monkeypatch):
    od.allow_private_destination("internal-siem.corp", "On-prem SIEM, approved by security", "admin@example.com")
    monkeypatch.setattr(od.socket, "getaddrinfo", _fake_getaddrinfo("10.0.0.5"))
    assert od.resolve_and_validate("internal-siem.corp", 443) == "10.0.0.5"


def test_revoking_the_allowlist_entry_blocks_it_again(isolated, monkeypatch):
    od.allow_private_destination("internal-siem.corp", "Temporary access", "admin@example.com")
    od.revoke_private_destination("internal-siem.corp", "admin@example.com")
    monkeypatch.setattr(od.socket, "getaddrinfo", _fake_getaddrinfo("10.0.0.5"))
    with pytest.raises(od.SSRFBlocked):
        od.resolve_and_validate("internal-siem.corp", 443)


def test_revoking_an_unknown_allowance_raises(isolated):
    with pytest.raises(KeyError):
        od.revoke_private_destination("never-allowed.corp", "admin@example.com")


def test_public_address_is_allowed(isolated, monkeypatch):
    monkeypatch.setattr(od.socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))
    assert od.resolve_and_validate("public.example.test", 443) == "93.184.216.34"


def test_mixed_public_and_private_response_fails_closed(isolated, monkeypatch):
    # An attacker-influenced DNS answer that hides one internal address behind a public-looking
    # one must still be refused entirely, not just downgraded to "use the safe-looking one".
    monkeypatch.setattr(od.socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34", "10.0.0.9"))
    with pytest.raises(od.SSRFBlocked):
        od.resolve_and_validate("mixed.example.test", 443)


def test_dns_resolution_failure_is_a_retryable_delivery_error(isolated, monkeypatch):
    def _raise(*_, **__):
        raise od.socket.gaierror("no such host")
    monkeypatch.setattr(od.socket, "getaddrinfo", _raise)
    with pytest.raises(od.DeliveryError):
        od.resolve_and_validate("does-not-resolve.test", 443)


# -- send_json request construction -------------------------------------------

def test_send_json_rejects_non_https_scheme(isolated):
    with pytest.raises(od.PermanentDeliveryError):
        od.send_json("http://example.test/webhook", b"{}")


def test_send_json_rejects_a_url_with_no_host(isolated):
    with pytest.raises(od.PermanentDeliveryError):
        od.send_json("https:///no-host", b"{}")


# -- HTTP status classification ------------------------------------------------

@pytest.mark.parametrize("status", [200, 201, 202, 204])
def test_success_statuses_do_not_raise(status):
    od._raise_for_status(status)  # should not raise


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_statuses_are_permanent_and_never_followed(status):
    with pytest.raises(od.PermanentDeliveryError, match="redirect"):
        od._raise_for_status(status)


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_server_and_rate_limit_statuses_are_retryable(status):
    with pytest.raises(od.DeliveryError):
        od._raise_for_status(status)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_client_error_statuses_are_permanent(status):
    with pytest.raises(od.PermanentDeliveryError):
        od._raise_for_status(status)


# -- backoff with jitter -------------------------------------------------------

def test_backoff_grows_with_attempt_number():
    # Full jitter means any single sample can be small, so compare the ceiling, not the sample.
    small = max(od.backoff_seconds(1) for _ in range(50))
    large = max(od.backoff_seconds(6) for _ in range(50))
    assert large > small


def test_backoff_is_capped():
    samples = [od.backoff_seconds(50, cap=5.0) for _ in range(50)]
    assert all(0 <= value <= 5.0 for value in samples)


def test_backoff_jitter_is_not_deterministic():
    samples = {od.backoff_seconds(8) for _ in range(20)}
    assert len(samples) > 1


# -- evidence and claim tokens --------------------------------------------------

def test_claim_tokens_are_unique():
    assert od.new_claim_token() != od.new_claim_token()


def test_evidence_is_recorded_and_secrets_are_redacted(isolated):
    od.record_evidence("TEST_SUBSYSTEM", "rec_1", "ATTEMPT", org_id="org_default", attempt=1,
                        detail={"endpoint": "https://example.test", "api_key": "super-secret-value"})
    with od.sqlite3.connect(od.database_path) as connection:
        connection.row_factory = od.sqlite3.Row
        row = connection.execute("SELECT * FROM outbound_delivery_evidence WHERE record_id='rec_1' AND org_id='org_default'").fetchone()
    assert row["subsystem"] == "TEST_SUBSYSTEM"
    assert row["event"] == "ATTEMPT"
    detail = json.loads(row["detail_json"])
    assert detail["api_key"] == "[REDACTED]"
    assert "super-secret-value" not in row["detail_json"]


def test_allowlist_changes_are_recorded_as_evidence(isolated):
    od.allow_private_destination("audit-me.corp", "Needed for audit trail test", "admin@example.com")
    with od.sqlite3.connect(od.database_path) as connection:
        connection.row_factory = od.sqlite3.Row
        rows = connection.execute("SELECT * FROM outbound_delivery_evidence WHERE record_id='audit-me.corp' AND org_id IS NULL").fetchall()
    assert any(row["event"] == "ALLOWED" for row in rows)


def test_evidence_requires_an_explicit_org_decision(isolated):
    # No default: a new call site must say which org its evidence belongs to (or None for an
    # install-level event), so evidence can never be silently left unattributed.
    with pytest.raises(TypeError):
        od.record_evidence("TEST_SUBSYSTEM", "rec_2", "ATTEMPT")


def test_legacy_evidence_is_backfilled_except_install_level_events(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE outbound_delivery_evidence(
            evidence_id TEXT PRIMARY KEY, subsystem TEXT NOT NULL, record_id TEXT NOT NULL,
            event TEXT NOT NULL, attempt INTEGER, occurred_at TEXT NOT NULL,
            worker_id TEXT, detail_json TEXT)""")
        connection.execute("INSERT INTO outbound_delivery_evidence VALUES('oev_legacy','SECURITY_EXPORT','exp_1','SUCCESS',1,'2026-01-01',NULL,NULL)")
        connection.execute("INSERT INTO outbound_delivery_evidence VALUES('oev_sso','ENTERPRISE_SSO','idp_1','LOGIN_SUCCESS',NULL,'2026-01-01',NULL,NULL)")
    monkeypatch.setattr(od, "database_path", path)
    od.initialize_outbound_delivery()
    od.record_evidence("SECURITY_EXPORT", "exp_2", "SUCCESS", org_id="org_other")
    with sqlite3.connect(path) as connection:
        rows = dict(connection.execute("SELECT evidence_id, org_id FROM outbound_delivery_evidence").fetchall())
    assert rows.pop("oev_legacy") == "org_default"
    assert rows.pop("oev_sso") is None
    assert list(rows.values()) == ["org_other"]


# -- a real local TLS server, to exercise the pinned-connection sender end to end -----

def _self_signed_cert(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5))
        .not_valid_after(dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    return cert_path, key_path


class _EchoHandler(http.server.BaseHTTPRequestHandler):
    captured = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        type(self).captured = {"path": self.path, "headers": dict(self.headers), "body": body}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *_args):
        pass


@pytest.fixture()
def local_tls_server(tmp_path):
    cert_path, key_path = _self_signed_cert(tmp_path)
    server = http.server.HTTPServer(("127.0.0.1", 0), _EchoHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, cert_path
    finally:
        server.shutdown()
        server.server_close()


def _client_context_trusting(cert_path):
    context = ssl.create_default_context(cafile=str(cert_path))
    return context


def test_send_to_ip_delivers_payload_with_idempotency_header(isolated, local_tls_server):
    server, cert_path = local_tls_server
    port = server.server_address[1]
    result = od._send_to_ip(
        "localhost", "127.0.0.1", port, "POST", "/hook",
        b'{"hello":"world"}',
        {"Content-Type": "application/json", "Idempotency-Key": "dedupe-123"},
        connect_timeout=5.0, read_timeout=5.0, deadline=od.time.monotonic() + 10,
        ssl_context=_client_context_trusting(cert_path),
    )
    assert result["status_code"] == 200
    assert _EchoHandler.captured["path"] == "/hook"
    assert _EchoHandler.captured["headers"]["Idempotency-Key"] == "dedupe-123"
    assert json.loads(_EchoHandler.captured["body"]) == {"hello": "world"}


def test_send_to_ip_uses_the_real_hostname_for_tls_verification(isolated, local_tls_server):
    # The certificate is issued for "localhost"; connecting via the pinned IP must still verify
    # against that name (proving SNI/hostname checks use the original host, not the IP we pinned).
    server, cert_path = local_tls_server
    port = server.server_address[1]
    od._send_to_ip(
        "localhost", "127.0.0.1", port, "POST", "/hook", b"{}", {"Content-Type": "application/json"},
        connect_timeout=5.0, read_timeout=5.0, deadline=od.time.monotonic() + 10,
        ssl_context=_client_context_trusting(cert_path),
    )  # no exception means hostname verification against "localhost" succeeded


def test_send_to_ip_fails_hostname_verification_for_a_mismatched_pinned_target(isolated, local_tls_server):
    # If a caller ever pinned the wrong hostname against this IP, certificate verification (not a
    # silent connection to the wrong place) must be what stops it.
    server, cert_path = local_tls_server
    port = server.server_address[1]
    with pytest.raises(od.DeliveryError):
        od._send_to_ip(
            "not-the-right-hostname.test", "127.0.0.1", port, "POST", "/hook", b"{}", {},
            connect_timeout=5.0, read_timeout=5.0, deadline=od.time.monotonic() + 10,
            ssl_context=_client_context_trusting(cert_path),
        )
