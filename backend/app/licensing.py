"""Self-hosted licence leases with grace and recovery rules (P2.4).

A self-hosted install proves its licence with a lease: a JSON payload signed with GreyGuard's
licensing key (Ed25519) and verified here against GREYGUARD_LICENSE_PUBLIC_KEY. Leases are
short-lived by design and renewed by installing a newer one, so a lapsed commercial agreement
eventually stops new growth without anyone touching the install.

Rules:

- A lease is bound to one install (its install_id) and cannot be moved to another.
- A lease is VALID until expires_at, then in GRACE for its grace_days, then LAPSED.
- A LAPSED or missing lease puts every org on the install in the same restricted mode as an
  expired trial (entitlements.py): new growth pauses, existing agents keep being enforced, and
  evidence, export, emergency controls and offboarding stay available. Licensing never stops
  a protection.
- Recovery is installing a valid newer lease; it takes effect at once.
- A lease older than the one installed is refused, so an old lease cannot be replayed.
- The stored token is re-verified on every read, so editing the table cannot extend a lease.
- The clock cannot be wound back to revive a lease: time is measured from the latest time the
  install has seen (a high-water mark), and a clock that moves backwards is reported.

Licensing is enforced only when GREYGUARD_LICENSE_REQUIRED is true (hosted installs do not use
leases), so with it unset nothing changes.
"""
from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import db_compat as sqlite3
from .database import database_path

MAX_GRACE_DAYS = 30
MAX_LEASE_DAYS = 400
# The clock may drift this far behind the high-water mark before it is reported as wound back.
CLOCK_TOLERANCE = timedelta(minutes=10)
LEASE_FIELDS = ("lease_id", "licensee", "install_id", "plan", "issued_at", "expires_at", "grace_days")


class LicenseError(ValueError):
    """A lease that cannot be installed."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def required() -> bool:
    return os.getenv("GREYGUARD_LICENSE_REQUIRED", "false").strip().lower() in ("1", "true", "yes")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def initialize_licensing() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS license_install (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1), install_id TEXT NOT NULL,
            clock_high_water TEXT NOT NULL, created_at TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS license_leases (
            lease_id TEXT PRIMARY KEY, licensee TEXT NOT NULL, plan TEXT NOT NULL, issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL, grace_days INTEGER NOT NULL, token TEXT NOT NULL,
            installed_at TEXT NOT NULL, installed_by TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS license_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, actor TEXT NOT NULL,
            event_type TEXT NOT NULL, detail_json TEXT NOT NULL)""")
        now = utc_now().isoformat()
        connection.execute(
            "INSERT OR IGNORE INTO license_install (singleton, install_id, clock_high_water, created_at) VALUES (1, ?, ?, ?)",
            ("ins_" + uuid.uuid4().hex, now, now))


def _install() -> dict[str, Any]:
    initialize_licensing()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return dict(connection.execute("SELECT install_id, clock_high_water FROM license_install WHERE singleton = 1").fetchone())


def install_id() -> str:
    return _install()["install_id"]


def _trusted_now() -> tuple[datetime, bool]:
    """The later of the real clock and the latest time this install has seen, and whether the
    clock has been wound back past the tolerance."""
    real = utc_now()
    high_water = datetime.fromisoformat(_install()["clock_high_water"])
    if real > high_water + timedelta(minutes=1):
        with sqlite3.connect(database_path) as connection:
            connection.execute("UPDATE license_install SET clock_high_water = ? WHERE singleton = 1 AND clock_high_water < ?",
                               (real.isoformat(), real.isoformat()))
    return max(real, high_water), real < high_water - CLOCK_TOLERANCE


def _record(connection, actor: str, event_type: str, detail: dict) -> None:
    connection.execute("INSERT INTO license_events (timestamp, actor, event_type, detail_json) VALUES (?, ?, ?, ?)",
                       (utc_now().isoformat(), actor, event_type, json.dumps(detail, sort_keys=True)))


def _public_key() -> Ed25519PublicKey:
    value = os.getenv("GREYGUARD_LICENSE_PUBLIC_KEY", "").strip()
    if not value:
        raise LicenseError("No licence verification key is configured (GREYGUARD_LICENSE_PUBLIC_KEY).")
    try:
        return Ed25519PublicKey.from_public_bytes(_b64decode(value))
    except ValueError as error:
        raise LicenseError("GREYGUARD_LICENSE_PUBLIC_KEY is not a valid Ed25519 public key.") from error


@lru_cache(maxsize=32)
def _verify_cached(token: str, public_key: str) -> tuple[tuple[str, Any], ...]:
    try:
        payload_part, signature_part = token.strip().split(".")
        payload_bytes = _b64decode(payload_part)
        _public_key().verify(_b64decode(signature_part), payload_bytes)
        payload = json.loads(payload_bytes)
    except LicenseError:
        raise
    except (ValueError, InvalidSignature) as error:
        raise LicenseError("The lease signature is invalid.") from error
    if not isinstance(payload, dict) or set(payload) != set(LEASE_FIELDS):
        raise LicenseError("The lease is malformed.")
    try:
        issued, expires = datetime.fromisoformat(payload["issued_at"]), datetime.fromisoformat(payload["expires_at"])
    except (TypeError, ValueError) as error:
        raise LicenseError("The lease dates are malformed.") from error
    if issued.tzinfo is None or expires.tzinfo is None or not issued < expires <= issued + timedelta(days=MAX_LEASE_DAYS):
        raise LicenseError(f"A lease must run forwards for at most {MAX_LEASE_DAYS} days.")
    grace = payload["grace_days"]
    if not isinstance(grace, int) or isinstance(grace, bool) or not 0 <= grace <= MAX_GRACE_DAYS:
        raise LicenseError(f"A lease grace period is 0 to {MAX_GRACE_DAYS} days.")
    return tuple(payload.items())


def verify_lease(token: str) -> dict[str, Any]:
    """Verify a lease's signature and shape (not its install binding or dates)."""
    return dict(_verify_cached(str(token), os.getenv("GREYGUARD_LICENSE_PUBLIC_KEY", "").strip()))


def _state(lease: dict[str, Any], now: datetime) -> str:
    expires = datetime.fromisoformat(lease["expires_at"])
    if now < expires:
        return "VALID"
    if now < expires + timedelta(days=lease["grace_days"]):
        return "GRACE"
    return "LAPSED"


def _current_token() -> str | None:
    initialize_licensing()
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT token FROM license_leases ORDER BY issued_at DESC LIMIT 1").fetchone()
    return row[0] if row else None


def install_lease(token: str, actor: str) -> dict[str, Any]:
    """Install-operator action: install a newer lease. Takes effect at once (recovery)."""
    lease = verify_lease(token)
    if lease["install_id"] != install_id():
        raise LicenseError("This lease was issued for a different install.")
    now, _ = _trusted_now()
    if _state(lease, now) == "LAPSED":
        raise LicenseError("This lease has already lapsed.")
    current = _current_token()
    if current:
        try:
            installed = verify_lease(current)
        except LicenseError:
            installed = None
        if installed and lease["issued_at"] <= installed["issued_at"]:
            raise LicenseError("A newer lease is already installed; an older lease cannot replace it.")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """INSERT INTO license_leases (lease_id, licensee, plan, issued_at, expires_at, grace_days, token,
            installed_at, installed_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (lease["lease_id"], lease["licensee"], lease["plan"], lease["issued_at"], lease["expires_at"],
             lease["grace_days"], token.strip(), utc_now().isoformat(), actor))
        _record(connection, actor, "LEASE_INSTALLED", {k: lease[k] for k in LEASE_FIELDS if k != "install_id"})
    return license_status()


def license_status() -> dict[str, Any]:
    """The install's licence state. NOT_REQUIRED when leases are not enforced on this install."""
    now, clock_rolled_back = _trusted_now()
    status: dict[str, Any] = {"required": required(), "install_id": install_id(), "clock_rolled_back": clock_rolled_back}
    token = _current_token()
    if token is None:
        return {**status, "state": "MISSING" if required() else "NOT_REQUIRED", "lease": None}
    try:
        lease = verify_lease(token)
    except LicenseError:
        # A stored lease that no longer verifies (edited, or the key was rotated) counts as none.
        return {**status, "state": "INVALID" if required() else "NOT_REQUIRED", "lease": None}
    state = _state(lease, now)
    grace_ends = datetime.fromisoformat(lease["expires_at"]) + timedelta(days=lease["grace_days"])
    return {**status, "state": state if required() else "NOT_REQUIRED",
            "lease_state": state, "grace_ends_at": grace_ends.isoformat(),
            "lease": {k: lease[k] for k in LEASE_FIELDS}}


def restriction() -> str | None:
    """The licence reason, if any, that puts every org on this install in restricted mode."""
    if not required():
        return None
    state = license_status()["state"]
    return {"MISSING": "LICENSE_MISSING", "INVALID": "LICENSE_MISSING", "LAPSED": "LICENSE_LAPSED"}.get(state)


def license_history(limit: int = 50) -> list[dict[str, Any]]:
    initialize_licensing()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT timestamp, actor, event_type, detail_json FROM license_events ORDER BY event_id DESC LIMIT ?",
                                  (max(1, min(int(limit), 200)),)).fetchall()
    return [{"timestamp": r["timestamp"], "actor": r["actor"], "event_type": r["event_type"],
             "detail": json.loads(r["detail_json"])} for r in rows]


def issue_lease(private_key: str, *, licensee: str, install: str, plan: str, days: int, grace_days: int,
                issued_at: datetime | None = None) -> str:
    """Vendor side: sign a lease. Used by scripts/issue_license_lease.py and tests - an install
    never holds the private key."""
    issued = issued_at or utc_now()
    payload = {"lease_id": "lse_" + uuid.uuid4().hex, "licensee": licensee, "install_id": install, "plan": plan,
               "issued_at": issued.isoformat(), "expires_at": (issued + timedelta(days=days)).isoformat(),
               "grace_days": grace_days}
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = Ed25519PrivateKey.from_private_bytes(_b64decode(private_key)).sign(payload_bytes)
    return f"{_b64encode(payload_bytes)}.{_b64encode(signature)}"
