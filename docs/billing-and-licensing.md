# Billing and self-hosted licensing

GreyGuard connects plans to billing through a provider-neutral interface (`backend/app/billing.py`) and licenses self-hosted installs with signed leases (`backend/app/licensing.py`). This document is the specification both modules implement. Plans, limits and restricted mode themselves are specified in [metering-and-entitlements.md](metering-and-entitlements.md).

Both features are **off by default**. An install with neither configured behaves exactly as it did before billing and licensing existed.

## Principles

These come from the commercial roadmap addendum.

- **No card data.** A billing provider holds payment details. GreyGuard keeps only opaque references (customer, subscription and invoice IDs) and a fixed allowlist of fields from each event. A raw provider payload is never stored, and anything outside the allowlist, card numbers included, is dropped when the event is parsed.
- **Provider-neutral.** `BillingProvider` is the whole contract. The only implementation is `MockBillingProvider`, a sandbox in which no money moves. No live payment processor is integrated.
- **Failure is safe.** Billing and licensing can put an org in restricted mode, never further:
  - **Paused:** new growth, meaning new agents and new gated configuration.
  - **Still enforced:** existing agents, exactly as before.
  - **Still available:** evidence, exports, emergency controls, credential revocation and offboarding.
- **Recovery is immediate.** A successful payment or a renewed lease lifts its restriction on the next request. No job has to run, and nobody has to lift anything by hand.
- **Independent inputs.** Restricted mode has separate causes: the plan status an install operator sets, billing, and the install's licence. Each is evaluated separately, so clearing one never clears another. For example, a payment can never lift a suspension an operator imposed.
- **Evidence.** Every billing event is recorded once, in a per-org hash chain that can be rechecked.

## Restriction reasons

`GET /entitlements` reports `restricted` and the `restriction_reasons` behind it. A refused action returns `403` with `"reason": "ENTITLEMENT"` and names every cause.

| Reason | Cause |
|---|---|
| `PLAN_EXPIRED` | The plan's trial ended. |
| `PLAN_SUSPENDED` | An install operator suspended the plan. |
| `PAYMENT_OVERDUE` | A payment failed and its grace period has ended. |
| `SUBSCRIPTION_CANCELED` | The subscription was cancelled. |
| `LICENSE_LAPSED` | The install's licence lease and its grace period have both ended. |
| `LICENSE_MISSING` | Leases are required, and none is installed or the installed one no longer verifies. |

The two licence reasons apply to every org on the install.

## Billing

### Billing states

| State | Meaning | Restricted? |
|---|---|---|
| `ACTIVE` | The subscription is in good standing. | No |
| `PAST_DUE` | A payment failed. The grace period runs for `GRACE_DAYS` (14) from the first failure. | Only once the grace period has ended (`PAYMENT_OVERDUE`) |
| `CANCELED` | The subscription was cancelled. | Yes (`SUBSCRIPTION_CANCELED`) |

Transitions:

- **Payment failed:** `ACTIVE` becomes `PAST_DUE` and the grace clock starts. Further failures keep the original deadline, so a provider's retries can never extend it.
- **Payment succeeded:** `PAST_DUE` becomes `ACTIVE`. A payment does not reopen a cancelled subscription; that takes a new one.
- **Subscription cancelled:** any state becomes `CANCELED`.

The grace period lapses lazily: an org becomes restricted at the moment its deadline passes, with no background job involved.

### Plans stay operator decisions

An org never subscribes itself to a plan. An install operator links an org to billing with `POST /billing/{org_id}/link`. That one call:

1. creates the provider customer and subscription; and
2. assigns the matching plan through the entitlements engine, which records an audited `PLAN_ASSIGNED` event.

Billing never changes a plan by itself.

### Webhooks

`POST /billing/webhooks/{provider}` authenticates by signature, not by session.

The mock provider signs `"<timestamp>.<body>"` with HMAC-SHA256 using `GREYGUARD_BILLING_WEBHOOK_SECRET`, which must be at least 32 characters. The signature travels in the `X-GreyGuard-Billing-Signature: t=<unix time>,v1=<hex>` header.

A webhook is refused with `400` if any of these is true:

- the signature is missing or wrong;
- the timestamp is more than 5 minutes from the current time;
- the event type is unknown;
- the body is not a JSON object.

Valid webhooks are handled as follows:

- **Redeliveries are idempotent.** Uniqueness is per provider event ID, and concurrent deliveries are serialized per org.
- **Unknown subscriptions** get the same acknowledgement as known ones, so the endpoint reveals nothing about which subscriptions exist.

### Billing-event evidence

`billing_events` holds:

- every provider event;
- the internal events: account linked, contact updated and cancellation.

Each row's `record_hash` is SHA-256 over the previous row's hash and the row's own fields, chained separately per org. `verify_billing_evidence()` recomputes the chain, so an edited, deleted or reordered event breaks it at that row. The `(org_id, previous_hash)` pair is unique, so a forked chain cannot be stored at all.

### Billing settings

| Variable | Default | Meaning |
|---|---|---|
| `GREYGUARD_BILLING_PROVIDER` | `none` | `mock` enables the sandbox provider. The mock is refused when `GREYGUARD_ENV=production`. |
| `GREYGUARD_BILLING_WEBHOOK_SECRET` | none | The webhook signing secret, at least 32 characters. Without it, every webhook is refused. |

## Self-hosted licence leases

A lease is a JSON payload signed with GreyGuard's licensing key (Ed25519), in the form `base64url(payload).base64url(signature)`. The payload contains:

- `lease_id`
- `licensee`
- `install_id`
- `plan`
- `issued_at`
- `expires_at` (at most 400 days after `issued_at`)
- `grace_days` (0–30)

An install holds only the public key. The private key and the issuing tool (`python -m scripts.issue_license_lease`) stay with the vendor.

### Lease states

| State | Meaning |
|---|---|
| `NOT_REQUIRED` | `GREYGUARD_LICENSE_REQUIRED` is not set. Nothing is enforced. |
| `VALID` | Before `expires_at`. |
| `GRACE` | After `expires_at`, within `grace_days`. Nothing is restricted yet. |
| `LAPSED` | Past the grace period. Every org on the install is restricted (`LICENSE_LAPSED`). |
| `MISSING` / `INVALID` | Required, but no lease is installed, or the stored lease no longer verifies. Every org is restricted (`LICENSE_MISSING`). |

To renew or recover, an install operator installs a newer lease with `PUT /license`. It takes effect at once.

### Safeguards

| Attack | Defence |
|---|---|
| Moving a lease to another install | Each install generates a random `install_id` once. A lease for any other ID is refused. |
| Replaying an old lease | A lease issued before the installed one is refused. |
| Installing a lease that has already lapsed | Refused. |
| Editing the stored lease | The signed token is re-verified on every read, so editing the table's dates has no effect, and editing the token makes the install unlicensed rather than extended. |
| Winding the clock back | Time is measured from the latest moment the install has seen (a high-water mark), and a clock more than 10 minutes behind it is reported as `clock_rolled_back`. |

### Licensing settings

| Variable | Default | Meaning |
|---|---|---|
| `GREYGUARD_LICENSE_REQUIRED` | `false` | Enforce leases on this install. Hosted installs do not use leases. |
| `GREYGUARD_LICENSE_PUBLIC_KEY` | none | The vendor's Ed25519 public key, as base64url raw bytes. |

## API

| Route | Who | Purpose |
|---|---|---|
| `GET /billing` | any administrator | Their org's billing status: state, grace deadline and restriction. Never card data. |
| `GET /billing/events` | org owner or billing administrator | Their org's billing evidence and its chain verification |
| `PUT /billing/contact` | org owner or billing administrator | Change the billing contact email |
| `POST /billing/webhooks/{provider}` | the provider, by signature | Receive a billing event |
| `GET /billing/{org_id}` | install operator | Any org's billing status, evidence and verification |
| `POST /billing/{org_id}/link` | install operator | Open a subscription and assign the matching plan |
| `POST /billing/{org_id}/cancel` | install operator | Cancel the subscription |
| `POST /billing/{org_id}/simulate` | install operator, mock provider only | Send a signed sandbox event through the real webhook path |
| `GET /license` | install operator | Lease state, install ID and lease history |
| `PUT /license` | install operator | Install a lease |

Billing access follows an org's **governance** role, not its operational role. A billing administrator who is an `AUDITOR` can still manage the billing contact.

The Settings page shows every administrator their org's billing state, and the reason for any restriction, in the Plan & usage panel.

## Open commercial decisions

The mechanics are complete. These decisions belong to the business:

1. **A live provider.** Which payment processor to integrate behind `BillingProvider`, and its event mapping.
2. **Grace length.** `GRACE_DAYS` (14) is a working value.
3. **Self-serve checkout.** Whether org owners should ever start or change their own subscription. Today only install operators link billing.
4. **Lease terms.** The default lease length and grace period issued to self-hosted customers, and how lease renewal is delivered (manually, or automated against a licensing service).
5. **Cancellation beyond restricted mode.** For example, a data-retention period after which an org is offboarded. That belongs with P2.5 (organization lifecycle).
