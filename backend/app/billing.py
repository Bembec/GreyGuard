"""Provider-neutral billing, billing-event evidence and payment-failure grace (P2.4).

Design rules, from the commercial roadmap addendum:

- GreyGuard stores no card data. A provider holds payment details; GreyGuard keeps only opaque
  references (customer, subscription, invoice) and the allowlisted fields of each normalized
  event (NEUTRAL_EVENT_FIELDS). A raw provider payload is never stored.
- The billing interface is provider-neutral: BillingProvider is the whole contract, and the only
  implementation is MockBillingProvider, a sandbox. No live payment processor is integrated
  (Michael's decision for P2.4).
- Billing never removes a protection. A payment failure starts a grace period; when it lapses,
  or a subscription is cancelled, the org enters the same restricted mode as an expired trial
  (entitlements.py): new growth pauses, existing agents keep being enforced, and evidence,
  export, emergency controls and offboarding stay available. A later successful payment
  recovers the org immediately - no job has to run and nobody has to lift a suspension by hand.
- Billing state is an input to the effective entitlement status, never a write to it. An
  operator's own suspension (org_entitlements) and a billing restriction are independent, so a
  payment can never lift a suspension an operator imposed.
- Every billing event is evidence: recorded once (idempotent on the provider's event id) in a
  per-org hash chain that verify_billing_evidence() can recheck.

Billing is off unless GREYGUARD_BILLING_PROVIDER names a provider; with it off nothing changes.
GRACE_DAYS is a WORKING VALUE pending a commercial decision.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from . import db_compat as sqlite3
from .database import database_path

GRACE_DAYS = 14
BILLING_STATES = {"ACTIVE", "PAST_DUE", "CANCELED"}
# Normalized, provider-neutral event types. Providers translate their own vocabulary into these.
PROVIDER_EVENT_TYPES = {"PAYMENT_SUCCEEDED", "PAYMENT_FAILED", "SUBSCRIPTION_CANCELED"}
# The only fields of a provider event GreyGuard ever stores. Anything else in a payload -
# including any card or bank detail a misbehaving provider might send - is dropped on parse.
NEUTRAL_EVENT_FIELDS = ("provider_event_id", "event_type", "subscription_ref", "occurred_at",
                        "amount_minor", "currency", "invoice_ref")
SIGNATURE_HEADER = "x-greyguard-billing-signature"
SIGNATURE_TOLERANCE_SECONDS = 300
GENESIS_HASH = "GENESIS"


class BillingError(ValueError):
    """A billing request that cannot be carried out."""


class WebhookRejected(PermissionError):
    """A webhook whose signature, timestamp or shape cannot be trusted."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BillingProvider(ABC):
    """The whole provider contract. A provider owns customers, payment methods and invoices;
    GreyGuard only ever holds the opaque references these methods return."""

    name: str

    @abstractmethod
    def create_customer(self, org_id: str, billing_email: str) -> str:
        """Create the provider's customer for an org and return its reference."""

    @abstractmethod
    def create_subscription(self, customer_ref: str, plan: str) -> str:
        """Subscribe a customer to a plan and return the subscription reference."""

    @abstractmethod
    def cancel_subscription(self, subscription_ref: str) -> None:
        """Cancel a subscription at the provider."""

    @abstractmethod
    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> dict[str, Any]:
        """Verify a webhook and translate it into a neutral event containing only
        NEUTRAL_EVENT_FIELDS. Raises WebhookRejected if it cannot be trusted."""


def _webhook_secret() -> str:
    secret = os.getenv("GREYGUARD_BILLING_WEBHOOK_SECRET", "")
    if len(secret) < 32:
        raise WebhookRejected("Billing webhooks are not configured (GREYGUARD_BILLING_WEBHOOK_SECRET).")
    return secret


def _signature(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


class MockBillingProvider(BillingProvider):
    """Sandbox provider: no money moves and nothing leaves the install. Its webhooks use the same
    signed path a real provider's would (HMAC-SHA256 over timestamp and body, with a replay
    window), so the evidence, idempotency and grace rules are exercised exactly as in production."""

    name = "mock"

    def create_customer(self, org_id: str, billing_email: str) -> str:
        return "mock_cus_" + secrets.token_hex(8)

    def create_subscription(self, customer_ref: str, plan: str) -> str:
        return "mock_sub_" + secrets.token_hex(8)

    def cancel_subscription(self, subscription_ref: str) -> None:
        return None

    def sign(self, event: dict[str, Any], timestamp: int | None = None) -> tuple[bytes, dict[str, str]]:
        """Produce a webhook body and headers as the provider would send them."""
        body = json.dumps(event, sort_keys=True).encode()
        stamp = str(int(time.time() if timestamp is None else timestamp))
        return body, {SIGNATURE_HEADER: f"t={stamp},v1={_signature(_webhook_secret(), stamp, body)}"}

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> dict[str, Any]:
        header = {key.lower(): value for key, value in headers.items()}.get(SIGNATURE_HEADER, "")
        parts = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
        stamp, signature = parts.get("t", ""), parts.get("v1", "")
        if not stamp.isdigit() or not signature:
            raise WebhookRejected("Billing webhook signature is missing.")
        if abs(time.time() - int(stamp)) > SIGNATURE_TOLERANCE_SECONDS:
            raise WebhookRejected("Billing webhook timestamp is outside the replay window.")
        if not hmac.compare_digest(_signature(_webhook_secret(), stamp, body), signature):
            raise WebhookRejected("Billing webhook signature is invalid.")
        try:
            payload = json.loads(body)
        except ValueError as error:
            raise WebhookRejected("Billing webhook body is not JSON.") from error
        if not isinstance(payload, dict):
            raise WebhookRejected("Billing webhook body must be an object.")
        return normalize_event(payload)


PROVIDERS: dict[str, type[BillingProvider]] = {"mock": MockBillingProvider}


def normalize_event(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only NEUTRAL_EVENT_FIELDS, validated. Used by every provider's parse_webhook()."""
    event = {field: payload.get(field) for field in NEUTRAL_EVENT_FIELDS if payload.get(field) is not None}
    if event.get("event_type") not in PROVIDER_EVENT_TYPES:
        raise WebhookRejected("Unsupported billing event type.")
    for field in ("provider_event_id", "subscription_ref"):
        if not isinstance(event.get(field), str) or not 1 <= len(event[field]) <= 200:
            raise WebhookRejected(f"Billing event needs a {field}.")
    if "amount_minor" in event and (not isinstance(event["amount_minor"], int) or isinstance(event["amount_minor"], bool)):
        raise WebhookRejected("amount_minor must be an integer.")
    for field in ("occurred_at", "currency", "invoice_ref"):
        if field in event and (not isinstance(event[field], str) or len(event[field]) > 200):
            raise WebhookRejected(f"{field} must be a short string.")
    return event


def configured_provider_name() -> str | None:
    name = os.getenv("GREYGUARD_BILLING_PROVIDER", "none").strip().lower()
    return None if name in ("", "none") else name


def provider(name: str | None = None) -> BillingProvider:
    """The configured provider. The mock is a sandbox and is refused in production."""
    name = name or configured_provider_name()
    if name is None:
        raise BillingError("Billing is not enabled on this install.")
    if name not in PROVIDERS:
        raise BillingError(f"Unknown billing provider: {name}")
    if name == "mock" and os.getenv("GREYGUARD_ENV", "development").strip().lower() == "production":
        raise BillingError("The mock billing provider is a sandbox and is not available in production.")
    return PROVIDERS[name]()


def initialize_billing() -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS billing_accounts (
            org_id TEXT PRIMARY KEY, provider TEXT NOT NULL, customer_ref TEXT NOT NULL,
            subscription_ref TEXT NOT NULL UNIQUE, plan TEXT NOT NULL, billing_state TEXT NOT NULL,
            billing_email TEXT NOT NULL, past_due_since TEXT, grace_ends_at TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        # Appends are serialized per org (see _record); previous_hash being unique per org is the
        # backstop that makes a forked chain impossible to store rather than merely unlikely.
        connection.execute("""CREATE TABLE IF NOT EXISTS billing_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, org_id TEXT NOT NULL, provider TEXT NOT NULL,
            provider_event_id TEXT NOT NULL, event_type TEXT NOT NULL, actor TEXT NOT NULL,
            recorded_at TEXT NOT NULL, detail_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
            record_hash TEXT NOT NULL, UNIQUE (provider, provider_event_id), UNIQUE (org_id, previous_hash))""")


def _hash(previous_hash: str, fields: dict[str, Any]) -> str:
    return hashlib.sha256((previous_hash + json.dumps(fields, sort_keys=True, separators=(",", ":"))).encode()).hexdigest()


def _record(connection, org_id: str, provider_name: str, provider_event_id: str, event_type: str,
            actor: str, detail: dict[str, Any]) -> bool:
    """Append one event to the org's evidence chain. Returns False if the provider event was
    already recorded (webhooks are delivered at least once)."""
    # Lock the org's billing account row first: concurrent appends for one org (a webhook racing
    # its own redelivery, say) then run one after the other on SQLite and PostgreSQL alike, so
    # each sees the other's event - both for the duplicate check and as its previous hash.
    connection.execute("UPDATE billing_accounts SET updated_at = updated_at WHERE org_id = ?", (org_id,))
    if connection.execute("SELECT org_id FROM billing_events WHERE provider = ? AND provider_event_id = ?",
                          (provider_name, provider_event_id)).fetchone():
        return False
    last = connection.execute(
        "SELECT record_hash FROM billing_events WHERE org_id = ? ORDER BY event_id DESC LIMIT 1", (org_id,)).fetchone()
    previous = last[0] if last else GENESIS_HASH
    fields = {"org_id": org_id, "provider": provider_name, "provider_event_id": provider_event_id,
              "event_type": event_type, "actor": actor, "recorded_at": utc_now().isoformat(), "detail": detail}
    connection.execute(
        """INSERT INTO billing_events (org_id, provider, provider_event_id, event_type, actor, recorded_at,
        detail_json, previous_hash, record_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (org_id, provider_name, provider_event_id, event_type, actor, fields["recorded_at"],
         json.dumps(detail, sort_keys=True), previous, _hash(previous, fields)))
    return True


def _internal_event_id() -> str:
    return "gg_" + uuid.uuid4().hex


def get_account(org_id: str) -> dict[str, Any] | None:
    initialize_billing()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM billing_accounts WHERE org_id = ?", (org_id,)).fetchone()
    return dict(row) if row else None


def restriction(org_id: str) -> str | None:
    """The billing reason, if any, that puts this org in restricted mode right now. A lapsed
    grace period takes effect the moment it ends; no background job has to notice."""
    account = get_account(org_id)
    if account is None:
        return None
    if account["billing_state"] == "CANCELED":
        return "SUBSCRIPTION_CANCELED"
    if account["billing_state"] == "PAST_DUE" and account["grace_ends_at"] and account["grace_ends_at"] <= utc_now().isoformat():
        return "PAYMENT_OVERDUE"
    return None


def billing_summary(org_id: str) -> dict[str, Any]:
    """What an org's administrators see about billing: never card data, which GreyGuard never has."""
    account = get_account(org_id)
    if account is None:
        return {"enabled": configured_provider_name() is not None, "linked": False, "restriction": None}
    return {
        "enabled": configured_provider_name() is not None, "linked": True,
        "provider": account["provider"], "plan": account["plan"], "billing_state": account["billing_state"],
        "billing_email": account["billing_email"], "past_due_since": account["past_due_since"],
        "grace_ends_at": account["grace_ends_at"], "restriction": restriction(org_id),
    }


def link_account(org_id: str, plan: str, billing_email: str, actor: str) -> dict[str, Any]:
    """Install-operator action: open a customer and subscription at the provider for an org.
    The caller assigns the matching entitlement plan; billing never assigns plans itself."""
    billing_email = str(billing_email).strip()
    if "@" not in billing_email or len(billing_email) > 254:
        raise BillingError("A billing contact email is required.")
    if get_account(org_id) is not None:
        raise BillingError("This organization already has a billing account.")
    active = provider()
    customer_ref = active.create_customer(org_id, billing_email)
    subscription_ref = active.create_subscription(customer_ref, plan)
    now = utc_now().isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """INSERT INTO billing_accounts (org_id, provider, customer_ref, subscription_ref, plan, billing_state,
            billing_email, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)""",
            (org_id, active.name, customer_ref, subscription_ref, plan, billing_email, now, now))
        _record(connection, org_id, active.name, _internal_event_id(), "ACCOUNT_LINKED", actor,
                {"plan": plan, "customer_ref": customer_ref, "subscription_ref": subscription_ref})
    return billing_summary(org_id)


def update_contact(org_id: str, billing_email: str, actor: str) -> dict[str, Any]:
    """Owner/billing-admin action: change where billing correspondence goes."""
    billing_email = str(billing_email).strip()
    if "@" not in billing_email or len(billing_email) > 254:
        raise BillingError("A billing contact email is required.")
    account = get_account(org_id)
    if account is None:
        raise KeyError("This organization has no billing account.")
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE billing_accounts SET billing_email = ?, updated_at = ? WHERE org_id = ?",
                           (billing_email, utc_now().isoformat(), org_id))
        _record(connection, org_id, account["provider"], _internal_event_id(), "CONTACT_UPDATED", actor,
                {"billing_email": billing_email})
    return billing_summary(org_id)


def cancel_account(org_id: str, actor: str) -> dict[str, Any]:
    """Install-operator action: cancel the subscription at the provider. The org becomes
    restricted, never cut off: evidence, export and offboarding stay available."""
    account = get_account(org_id)
    if account is None:
        raise KeyError("This organization has no billing account.")
    provider(account["provider"]).cancel_subscription(account["subscription_ref"])
    _apply(org_id, account, "SUBSCRIPTION_CANCELED", {}, actor, account["provider"], _internal_event_id())
    return billing_summary(org_id)


def _apply(org_id, account, event_type, detail, actor, provider_name, provider_event_id) -> bool:
    now = utc_now()
    with sqlite3.connect(database_path) as connection:
        if not _record(connection, org_id, provider_name, provider_event_id, event_type, actor, detail):
            return False
        if event_type == "PAYMENT_SUCCEEDED":
            # Recovery: a successful payment clears a past-due state at once. It does not reopen a
            # cancelled subscription - that takes a new subscription.
            if account["billing_state"] == "PAST_DUE":
                connection.execute(
                    "UPDATE billing_accounts SET billing_state = 'ACTIVE', past_due_since = NULL, grace_ends_at = NULL,"
                    " updated_at = ? WHERE org_id = ?", (now.isoformat(), org_id))
        elif event_type == "PAYMENT_FAILED":
            # Repeated failures keep the original grace deadline; a retry storm cannot extend it.
            if account["billing_state"] == "ACTIVE":
                connection.execute(
                    "UPDATE billing_accounts SET billing_state = 'PAST_DUE', past_due_since = ?, grace_ends_at = ?,"
                    " updated_at = ? WHERE org_id = ?",
                    (now.isoformat(), (now + timedelta(days=GRACE_DAYS)).isoformat(), now.isoformat(), org_id))
        elif event_type == "SUBSCRIPTION_CANCELED":
            connection.execute("UPDATE billing_accounts SET billing_state = 'CANCELED', updated_at = ? WHERE org_id = ?",
                               (now.isoformat(), org_id))
    return True


def handle_webhook(provider_name: str, body: bytes, headers: Mapping[str, str]) -> dict[str, Any]:
    """Verify, normalize, record and apply one provider webhook. Unknown subscriptions are
    acknowledged without saying whether they exist, so the endpoint reveals nothing."""
    active = provider(provider_name)
    event = active.parse_webhook(body, headers)
    initialize_billing()
    # Identify first, scope second: the subscription reference is globally unique, and the org
    # it resolves to scopes everything after this lookup.
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT org_id FROM billing_accounts WHERE provider = ? AND subscription_ref = ?",
            (active.name, event["subscription_ref"])).fetchone()
    if row is None:
        return {"received": True}
    org_id = row["org_id"]
    account = get_account(org_id)
    detail = {key: value for key, value in event.items() if key not in ("provider_event_id", "event_type")}
    applied = _apply(org_id, account, event["event_type"], detail, f"billing:{active.name}",
                     active.name, event["provider_event_id"])
    return {"received": True, "duplicate": not applied}


def billing_events(org_id: str, limit: int = 100) -> list[dict[str, Any]]:
    initialize_billing()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT event_id, provider, provider_event_id, event_type, actor, recorded_at, detail_json, record_hash
            FROM billing_events WHERE org_id = ? ORDER BY event_id DESC LIMIT ?""",
            (org_id, max(1, min(int(limit), 500)))).fetchall()
    return [{**{k: row[k] for k in row.keys() if k != "detail_json"}, "detail": json.loads(row["detail_json"])} for row in rows]


def verify_billing_evidence(org_id: str) -> dict[str, Any]:
    """Recompute the org's billing-event hash chain. Any edited, deleted or reordered event breaks it."""
    initialize_billing()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM billing_events WHERE org_id = ? ORDER BY event_id", (org_id,)).fetchall()
    previous = GENESIS_HASH
    for row in rows:
        fields = {"org_id": row["org_id"], "provider": row["provider"], "provider_event_id": row["provider_event_id"],
                  "event_type": row["event_type"], "actor": row["actor"], "recorded_at": row["recorded_at"],
                  "detail": json.loads(row["detail_json"])}
        if row["previous_hash"] != previous or row["record_hash"] != _hash(previous, fields):
            return {"valid": False, "events": len(rows), "broken_at_event_id": row["event_id"]}
        previous = row["record_hash"]
    return {"valid": True, "events": len(rows), "head": previous}


def simulate_event(org_id: str, event_type: str, amount_minor: int | None = None, currency: str | None = None) -> dict[str, Any]:
    """Sandbox only: send a signed mock-provider webhook for an org through the real webhook path."""
    account = get_account(org_id)
    if account is None:
        raise KeyError("This organization has no billing account.")
    if account["provider"] != "mock":
        raise BillingError("Only the mock provider's events can be simulated.")
    mock = provider("mock")
    event = {"provider_event_id": "mock_evt_" + secrets.token_hex(8), "event_type": event_type,
             "subscription_ref": account["subscription_ref"], "occurred_at": utc_now().isoformat(),
             "invoice_ref": "mock_inv_" + secrets.token_hex(6)}
    if amount_minor is not None:
        event["amount_minor"], event["currency"] = amount_minor, (currency or "USD").upper()
    body, headers = mock.sign(event)
    return {**handle_webhook("mock", body, headers), "provider_event_id": event["provider_event_id"]}
