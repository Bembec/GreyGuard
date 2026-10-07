"""Shared SSRF-safe outbound delivery infrastructure.

Every GreyGuard subsystem that sends data to an administrator-configured
network destination (notifications, incident tickets, SIEM exports, report
notifications) routes its network call through this module instead of
building its own HTTP client. Centralizing it means the SSRF defenses,
timeouts, retry/backoff, idempotency, and audit evidence are implemented
and reviewed exactly once.

Deliberately stdlib-only (no `requests`/`httpx`): adding a new runtime
dependency changes the SBOM and supply-chain surface, which this project
treats as a decision for a human to approve, not something to slip in
while wiring a feature.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import random
import socket
import ssl
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from . import db_compat as sqlite3
from .database import database_path
from .observability import redact

CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 15.0
TOTAL_TIMEOUT_SECONDS = 25.0
MAX_RESPONSE_BYTES = 1_000_000
DEFAULT_LEASE_SECONDS = 120
DEFAULT_MAX_ATTEMPTS = 8
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_CAP_SECONDS = 300.0

# AWS/Azure/GCP/Oracle/DigitalOcean (and most other clouds) all serve their
# instance-metadata service at this exact address; it must never be reachable
# regardless of any administrator allowlist entry.
CLOUD_METADATA_IPV4 = ipaddress.ip_address("169.254.169.254")
CLOUD_METADATA_IPV6 = ipaddress.ip_address("fd00:ec2::254")  # AWS IPv6 metadata


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize_outbound_delivery() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS outbound_allowed_private_hosts(
            host TEXT PRIMARY KEY, reason TEXT NOT NULL,
            created_at TEXT NOT NULL, created_by TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS outbound_delivery_evidence(
            evidence_id TEXT PRIMARY KEY, subsystem TEXT NOT NULL, record_id TEXT NOT NULL,
            event TEXT NOT NULL, attempt INTEGER, occurred_at TEXT NOT NULL,
            worker_id TEXT, detail_json TEXT)""")


class SSRFBlocked(Exception):
    """The destination resolves to an address that must never be reached. Never retryable."""


class PermanentDeliveryError(Exception):
    """The destination rejected the request in a way retrying will not fix."""


class DeliveryError(Exception):
    """A transient failure; the caller should retry with backoff."""


def record_evidence(subsystem, record_id, event, *, attempt=None, detail=None, worker_id=None):
    """Append-only lifecycle evidence: ENQUEUED/ATTEMPT/SUCCESS/FAILURE/RETRY/DEAD_LETTER/BLOCKED."""
    initialize_outbound_delivery()
    safe_detail = redact(detail) if detail is not None else None
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO outbound_delivery_evidence VALUES(?,?,?,?,?,?,?,?)",
            ("oev_" + uuid.uuid4().hex, subsystem, str(record_id), event, attempt, utc_now(),
             worker_id, json.dumps(safe_detail, separators=(",", ":"), sort_keys=True) if safe_detail is not None else None),
        )


def backoff_seconds(attempt: int, *, base: float = BACKOFF_BASE_SECONDS, cap: float = BACKOFF_CAP_SECONDS) -> float:
    """Capped exponential backoff with full jitter: a random value in [0, computed-delay]."""
    computed = min(cap, base * (2 ** max(0, attempt - 1)))
    return random.uniform(0, computed)


def new_claim_token() -> str:
    return "clm_" + uuid.uuid4().hex


def safe_error(error: Exception) -> str:
    """A truncated, redacted string for `last_error` columns and evidence detail.

    No code path in this module embeds a secret in an exception message today, but `last_error`
    is returned directly in several admin-facing API responses, so this is a defensive backstop
    against a future dependency ever echoing something sensitive back in its own error text.
    """
    return redact(str(error))[:500]


# -- Administrator-governed private-destination allowlist -------------------

def allow_private_destination(host, reason, actor):
    host = host.strip().lower()
    if not host:
        raise ValueError("A destination hostname is required.")
    reason = reason.strip()
    if len(reason) < 3:
        raise ValueError("A reason is required to allow a private destination.")
    initialize_outbound_delivery()
    with sqlite3.connect(database_path) as connection:
        existing = connection.execute("SELECT host FROM outbound_allowed_private_hosts WHERE host=?", (host,)).fetchone()
        if existing:
            connection.execute("UPDATE outbound_allowed_private_hosts SET reason=?,created_at=?,created_by=? WHERE host=?",
                                (reason, utc_now(), actor, host))
        else:
            connection.execute("INSERT INTO outbound_allowed_private_hosts VALUES(?,?,?,?)", (host, reason, utc_now(), actor))
    record_evidence("SSRF_ALLOWLIST", host, "ALLOWED", detail={"reason": reason, "actor": actor})
    return {"host": host, "reason": reason, "created_by": actor}


def revoke_private_destination(host, actor):
    host = host.strip().lower()
    initialize_outbound_delivery()
    with sqlite3.connect(database_path) as connection:
        changed = connection.execute("DELETE FROM outbound_allowed_private_hosts WHERE host=?", (host,)).rowcount
    if not changed:
        raise KeyError("Private-destination allowance not found.")
    record_evidence("SSRF_ALLOWLIST", host, "REVOKED", detail={"actor": actor})
    return {"host": host, "revoked_by": actor}


def list_allowed_private_destinations():
    initialize_outbound_delivery()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute("SELECT * FROM outbound_allowed_private_hosts ORDER BY host")]


def is_private_destination_allowed(hostname: str) -> bool:
    initialize_outbound_delivery()
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT host FROM outbound_allowed_private_hosts WHERE host=?", (hostname.strip().lower(),)).fetchone()
    return row is not None


# -- SSRF-safe resolution -----------------------------------------------------

def _always_blocked(ip) -> bool:
    if ip in (CLOUD_METADATA_IPV4, CLOUD_METADATA_IPV6):
        return True
    return bool(ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved)


def resolve_and_validate(hostname: str, port: int) -> str:
    """Resolve `hostname` right now (never from a cache) and return one safe IP literal.

    Raises SSRFBlocked if any resolved address is disallowed. Checking every
    resolved address (not just the first) and failing closed on a mixed result
    denies an attacker the trick of hiding an internal address behind one
    public-looking record in the same DNS answer.
    """
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        raise DeliveryError(f"DNS resolution failed for {hostname}: {error}") from error
    resolved = []
    for _family, _type, _proto, _canon, sockaddr in infos:
        try:
            resolved.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue
    if not resolved:
        raise DeliveryError(f"DNS resolution returned no usable address for {hostname}.")
    for ip in resolved:
        if _always_blocked(ip):
            raise SSRFBlocked(f"{hostname} resolves to a disallowed address ({ip}).")
    private_hits = [ip for ip in resolved if ip.is_private]
    if private_hits and not is_private_destination_allowed(hostname):
        raise SSRFBlocked(f"{hostname} resolves to a private address ({private_hits[0]}) that is not on the explicit allowlist.")
    return str(resolved[0])


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """An HTTPSConnection that connects to a pre-validated IP while still
    using the original hostname for SNI, certificate hostname verification,
    and the Host header -- so a DNS change after validation can never change
    where the TCP connection actually goes (DNS-rebinding resistant)."""

    def __init__(self, hostname, pinned_ip, port, *, timeout, context):
        super().__init__(hostname, port, timeout=timeout, context=context)
        self._pinned_ip = pinned_ip

    def connect(self):
        raw_socket = socket.create_connection((self._pinned_ip, self.port), timeout=self.timeout)
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


def _raise_for_status(status: int) -> None:
    if status in (301, 302, 303, 307, 308):
        raise PermanentDeliveryError(f"Destination attempted an HTTP {status} redirect; redirects are never followed.")
    if status == 429 or 500 <= status < 600:
        raise DeliveryError(f"Destination returned a retryable error (HTTP {status}).")
    if status >= 400:
        raise PermanentDeliveryError(f"Destination rejected the request (HTTP {status}).")


def _send_to_ip(hostname, ip, port, path, payload: bytes, headers: dict, *, connect_timeout, read_timeout, deadline, ssl_context=None):
    # `ssl_context` exists only so tests can point this at a local server with a throwaway
    # certificate; every production call site leaves it unset and gets the real default context.
    context = ssl_context or ssl.create_default_context()
    connection = _PinnedHTTPSConnection(hostname, ip, port, timeout=connect_timeout, context=context)
    try:
        connection.connect()
        connection.sock.settimeout(read_timeout)
        if time.monotonic() > deadline:
            raise DeliveryError("Outbound delivery exceeded its total time budget before the request was sent.")
        connection.request("POST", path, body=payload, headers=headers)
        response = connection.getresponse()
        body = response.read(MAX_RESPONSE_BYTES + 1)[:MAX_RESPONSE_BYTES]
        status = response.status
    except (SSRFBlocked, PermanentDeliveryError, DeliveryError):
        raise
    except (socket.timeout, TimeoutError) as error:
        raise DeliveryError(f"Outbound delivery timed out: {error}") from error
    except OSError as error:
        raise DeliveryError(f"Outbound delivery network error: {error}") from error
    finally:
        connection.close()
    _raise_for_status(status)
    return {"status_code": status, "body": body}


def send_json(url: str, payload: bytes, *, headers: dict | None = None, idempotency_key: str | None = None,
              connect_timeout: float = CONNECT_TIMEOUT_SECONDS, read_timeout: float = READ_TIMEOUT_SECONDS,
              total_timeout: float = TOTAL_TIMEOUT_SECONDS) -> dict:
    """POST `payload` (already-serialized JSON bytes) to `url` through every SSRF defense.

    Resolves fresh on every call (no caching), validates every resolved
    address, connects only to the validated IP, enforces HTTPS, never follows
    redirects, and applies bounded connect/read/total timeouts.
    """
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise PermanentDeliveryError("Outbound delivery requires an https:// destination.")
    hostname = parts.hostname
    if not hostname:
        raise PermanentDeliveryError("Destination URL has no host.")
    port = parts.port or 443
    deadline = time.monotonic() + total_timeout
    ip = resolve_and_validate(hostname, port)
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    request_headers = {"Content-Type": "application/json", "Content-Length": str(len(payload))}
    if headers:
        request_headers.update(headers)
    if idempotency_key:
        request_headers["Idempotency-Key"] = idempotency_key
    return _send_to_ip(hostname, ip, port, path, payload, request_headers,
                        connect_timeout=connect_timeout, read_timeout=read_timeout, deadline=deadline)
