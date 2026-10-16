# Tracked deviations from approved designs

Where something built differs from its approved design, it is recorded here with an owner and a follow-up task. Nothing is dropped silently.

| ID | Design | Deviation | Risk while open | Owner | Follow-up | Status |
|---|---|---|---|---|---|---|
| DEV-001 | Control Graph (`p7.5-control-graph-design.md`, "API → Rate limits") | The design says graph responses are cached for 15 seconds per (org, agent, depth, limit). It was not built in the first delivery. | None while open: performance only, bounded by the node limit, window and rate limit. | Engineering (assigned to Claude in the P7.5 sessions); accepted by the project owner | FU-CG-01 below | **Closed 2026-10-16** in `d3104e5`, with the evidence below |

## Follow-up tasks

### FU-CG-01: cache Control Graph responses for 15 seconds

- **Scope:** a per-process cache keyed by (org_id, agent, depth, limit, window), 15-second lifetime. Never shared across orgs. A cached graph must not outlive the caller's permission check: ownership and role are checked on every request before any cached graph is returned.
- **Must also:** respect `include_install_level`, so an operator's graph is never served to a tenant. That means the cache key includes it.
- **Done when:**
  - tests show a hit within 15 seconds and a miss after;
  - no cross-org or operator-to-tenant reuse;
  - the permission check still runs on a hit;
  - mutation checks pass on the key fields;
  - this row moves to "Closed" with the commit.
- **When:** after the Control Graph frontend, before v3 item 10's performance budgets are set, since budgets should measure the cached path.

**Closed in `d3104e5` (2026-10-16).** Built with a stronger key than first scoped, at the owner's direction.

- **Key:** org; the viewer's admin id, role, permissions and install-operator flag; the agent; depth and limit; the retention-bound lookback; and a data version stamp. The stamp is one org-scoped query over requests, decision records, approval and execution events, incidents (with a status-weighted sum, so a status change in the same second still changes it), policy versions, emergency controls, the identity (credential, scopes, rotation, revocation, archive) and runtime state.
- **Invalidation:** automatic. Any application write changes the stamp, so the old entry can no longer be hit. Entries also expire after 15 seconds.
- **Authorization** is never cached. It runs on every request before the cache is consulted.
- **Bypass:** a `Cache-Control: no-cache` request always rebuilds. An explicit time window is never cached. The impact preview is never cached.
- **Memory:** at most 256 graphs per process, least recently used evicted, expired entries dropped. Each graph is bounded by the node limit.
- **Known limit, documented in code:** an edit made directly in the database outside the application, leaving every stamped value equal, can be served for up to 15 seconds.

**Evidence:**
- **`test_control_graph_cache.py`, 23 tests:**
  - a hit within 15 seconds and expiry at 15;
  - LRU eviction and expiry purge;
  - shown at once after a new request, a same-second approval, an incident status change, an emergency switch, credential revocation, a scope change, a policy publication, suspension and a retention change;
  - never shared between two people with the same role, or between auditor and administrator;
  - an install operator's graph never served to a tenant, and losing operator rights hiding install-level incidents at once;
  - another org refused while cached; an auditor who moves org refused at once; a signed-out session getting 401 while cached;
  - bypass honoured, explicit windows not cached, the preview never cached;
  - the key holding the org (defence in depth).
- **Mutation checks:** 10 of 11 caught. These covered the admin id, operator flag, org, lookback and data version in the key, expiry, the memory bound, bypass, the alert status weight and the runtime stamp. The approval-event stamp survived because it is redundant: an approval also writes an execution event and updates the request, which other stamps cover.
- **The same 23 tests and the 26 Control Graph tests passed on PostgreSQL** (`postgres:17-alpine`), each alone on a freshly migrated database.
- **Full backend suite:** 481 + 369 = 850 passed. **Frontend:** `npm run check` (230 unit tests, build). **Playwright:** 74 passed, 0 flaky.
