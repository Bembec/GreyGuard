# Gateway nodes and policy distribution

In the hybrid deployment model, a customer runs an enforcement gateway next to its agents, and the hosted control plane distributes policy to it. `backend/app/gateways.py` is the control-plane side. `sdk/python/greyguard_sdk/gateway.py` is the gateway side: it verifies bundles and makes local decisions. Install it with `pip install "greyguard-sdk[gateway]"`.

Gateways are an Enterprise capability, gated by the `gateway_nodes` entitlement feature.

## Enrollment

1. A platform administrator registers a node with `POST /gateways`, giving a `name` and `max_offline_seconds`. The response contains a one-time **enrollment token**, valid for 24 hours.
2. The node exchanges that token at `POST /gateways/enroll`, exactly once. It receives its **node credential** and the distribution public key.

Only SHA-256 hashes of the token and the credential are stored. A node belongs to one org and only ever receives that org's policy.

## Distribution

`GET /gateways/bundle` requires the `X-Gateway-Node` and `X-Gateway-Key` headers. It returns a bundle signed with **Ed25519** using `GREYGUARD_DISTRIBUTION_SIGNING_KEY`. The bundle contains:

- the org's published policy;
- its emergency controls;
- the agents whose credentials are revoked;
- `issued_at`, `valid_until` and a `content_digest`.

Gateways hold only the public key (`GET /gateways/distribution-key`, which is public). They can verify a bundle but never forge one. The older `/policy-versions/{id}/bundle` export uses HMAC, so anything able to verify it could also sign it. It must not be used for distribution.

A gateway must refuse a bundle in any of these cases:

- its signature does not verify;
- it was issued for another node;
- it is not newer than the bundle already applied (replay);
- it is past `valid_until`.

## Bounded offline use and revocation freshness

`valid_until` is `issued_at` plus the node's offline allowance, which is between 5 minutes and 7 days (default 1 hour). A gateway that cannot refresh by then **fails closed**: `decide()` returns `BLOCK` for everything.

The offline allowance is also the worst-case delay before a credential revocation, a node revocation or an emergency stop takes effect at that node. Keep it short where revocation speed matters.

## Fleet and revocation

- **Heartbeats.** A node reports the digest it has applied with `POST /gateways/heartbeat`.
- **Fleet view.** `GET /gateways` shows each node's health:
  - `IN_SYNC`: the node has applied the current bundle.
  - `OUT_OF_DATE`: the node is behind the current bundle.
  - `SILENT`: the node has not been seen within its offline allowance.
  - `PENDING` or `REVOKED`: the node's lifecycle state.
- **Revocation.** `POST /gateways/{node_id}/revoke` kills the node's credential at once. Its last bundle still expires on schedule.
- **Offboarding.** Offboarding an org revokes all of its nodes.
