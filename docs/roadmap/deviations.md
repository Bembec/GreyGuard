# Tracked deviations from approved designs

Where something built differs from its approved design, it is recorded here with an owner and a follow-up task. Nothing is dropped silently.

| ID | Design | Deviation | Risk while open | Owner | Follow-up | Status |
|---|---|---|---|---|---|---|
| DEV-001 | Control Graph (`p7.5-control-graph-design.md`, "API → Rate limits") | The design says graph responses are cached for 15 seconds per (org, agent, depth, limit). This is **not built**: every request recomputes the graph. | Performance only, not security: each request is bounded by the node limit (≤ 500), the 30-day window and the GENERAL rate limit. A burst of opens costs repeated database reads. | Engineering (assigned to Claude in the P7.5 sessions); accepted by the project owner | FU-CG-01 below | Open (recorded 2026-10-16) |

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
