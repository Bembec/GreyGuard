"""The Control Graph: one agent's relationships, built from existing records (P7.5 item 4).

Design: docs/roadmap/p7.5-control-graph-design.md, approved by the owner on 2026-10-16.

Rules this module keeps:
- **Tenant scope by construction.** The route checks the agent belongs to the caller's org first;
  then every query here passes that org_id. No node is ever fetched by id alone.
- **Read-only, always.** Nothing here writes, not even the seed-on-read some helpers do
  (get_emergency_controls, get_published_policy); the graph reads with SELECTs of its own.
- **Honest provenance.** A request decided since decision records exist links to the exact policy
  version and rule ("recorded"); an older one links to the version inferred from publication
  times ("inferred"), labelled as such. Neither is ever presented as the other.
- **Honest limits.** The window never reaches past retained data; when the node limit cuts the
  graph, the response says so, with counts per type.
- **No raw content.** Targets are shortened, payloads, results and notes are never included.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db_compat as sqlite3
from . import decision_provenance, main
from .database import database_path
from .time_range import TimeRange, permitted_lookback_days

DEFAULT_WINDOW_DAYS = 30
DEFAULT_LIMIT = 200
MAX_LIMIT = 500
TARGET_PREVIEW = 60
SAMPLE_SIZE = 50


def _instant(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def default_window(org_id, now: datetime | None = None) -> TimeRange:
    now = now or datetime.now(timezone.utc)
    days = min(DEFAULT_WINDOW_DAYS, permitted_lookback_days(org_id))
    return TimeRange((now - timedelta(days=days)).isoformat(), None)


def retained_from(org_id, now: datetime | None = None) -> str:
    """The oldest instant still inside retention: nothing older is offered or implied."""
    now = now or datetime.now(timezone.utc)
    return (now - timedelta(days=permitted_lookback_days(org_id))).isoformat()


# --- Read-only sources ---------------------------------------------------------------------------

def _rows(sql: str, parameters: tuple) -> list[Any]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(sql, parameters).fetchall()


def _identity(agent_name: str, org_id: str) -> dict[str, Any] | None:
    rows = _rows(
        "SELECT agent_name, scopes_json, credential_status, created_at, rotated_at, revoked_at, archived_at "
        "FROM agent_identities WHERE agent_name = ? AND org_id = ?",
        (agent_name, org_id),
    )
    if not rows:
        return None
    row = rows[0]
    return {**{key: row[key] for key in ("agent_name", "credential_status", "created_at", "rotated_at", "revoked_at", "archived_at")},
            "scopes": sorted(json.loads(row["scopes_json"] or "[]"))}


def _runtime(agent_name: str, org_id: str) -> dict[str, Any]:
    rows = _rows("SELECT agent_status, risk_score FROM agent_runtime_states WHERE agent_name = ? AND org_id = ?",
                 (agent_name, org_id))
    return {"agent_status": rows[0]["agent_status"], "risk_score": rows[0]["risk_score"]} if rows else {"agent_status": "ACTIVE", "risk_score": 0}


def _published_policy(org_id: str) -> dict[str, Any] | None:
    rows = _rows(
        "SELECT * FROM policy_versions WHERE status = 'PUBLISHED' AND org_id = ? ORDER BY version_number DESC LIMIT 1",
        (org_id,),
    )
    return _policy(rows[0]) if rows else None


def _policy(row) -> dict[str, Any]:
    return {
        "policy_id": row["policy_id"], "version_number": row["version_number"], "status": row["status"],
        "permissions": json.loads(row["permissions_json"]), "risk_weights": json.loads(row["risk_weights_json"]),
        "max_blocked_attempts": row["max_blocked_attempts"], "max_risk_score": row["max_risk_score"],
        "published_at": row["published_at"],
    }


def _policy_versions(org_id: str) -> dict[str, dict[str, Any]]:
    return {row["policy_id"]: _policy(row) for row in _rows("SELECT * FROM policy_versions WHERE org_id = ?", (org_id,))}


def _emergency(org_id: str) -> dict[str, Any]:
    rows = _rows("SELECT global_deny, disabled_agents_json, disabled_tools_json FROM policy_emergency_controls "
                 "WHERE control_id = 1 AND org_id = ?", (org_id,))
    if not rows:
        return {"global_deny": False, "disabled_agents": [], "disabled_tools": []}
    return {"global_deny": bool(rows[0]["global_deny"]), "disabled_agents": json.loads(rows[0]["disabled_agents_json"]),
            "disabled_tools": json.loads(rows[0]["disabled_tools_json"])}


def _requests(agent_name: str, org_id: str, window: TimeRange, limit: int) -> list[Any]:
    fragment, bounds = window.condition("timestamp")
    return _rows(
        "SELECT request_id, timestamp, action, target, policy_decision, approval_status, execution_status "
        f"FROM tool_requests WHERE org_id = ? AND agent_name = ? AND {fragment} ORDER BY timestamp DESC LIMIT ?",  # nosec B608  # fragment is built from constants; every value is a bound parameter
        (org_id, agent_name, *bounds, limit + 1),
    )


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join('?' for _ in values)})"


def _approvals(request_ids: list[str], org_id: str) -> list[Any]:
    if not request_ids:
        return []
    return _rows(f"SELECT id, request_id, timestamp, actor, decision FROM approval_events WHERE org_id = ? AND {_in('request_id', request_ids)} ORDER BY id",  # nosec B608  # placeholders only
                 (org_id, *request_ids))


def _alerts(agent_name: str, request_ids: list[str], org_id: str, window: TimeRange) -> list[Any]:
    fragment, bounds = window.condition("created_at")
    by_request = f" OR {_in('request_id', request_ids)}" if request_ids else ""
    return _rows(
        "SELECT alert_id, created_at, request_id, severity, status, title FROM security_alerts "
        f"WHERE org_id = ? AND (agent_name = ?{by_request}) AND ({fragment} OR status NOT IN ('RESOLVED', 'DISMISSED')) "  # nosec B608  # constants and placeholders only
        "ORDER BY created_at DESC",
        (org_id, agent_name, *request_ids, *bounds),
    )


def _install_level_alerts(agent_name: str) -> list[Any]:
    # Install-level alerts belong to no tenant (org_id IS NULL), e.g. failed sign-ins against an
    # agent name before any org could be resolved. Only install operators may see them.
    return _rows("SELECT alert_id, created_at, severity, status, title FROM security_alerts "
                 "WHERE org_id IS NULL AND agent_name = ? ORDER BY created_at DESC", (agent_name,))


# --- The graph -------------------------------------------------------------------------------------

def _short(text: str | None) -> str:
    text = (text or "").strip()
    return text if len(text) <= TARGET_PREVIEW else text[:TARGET_PREVIEW - 1] + "…"


class _Graph:
    def __init__(self, limit: int):
        self.limit = limit
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self.dropped: dict[str, int] = {}

    def node(self, node_id: str, **fields: Any) -> bool:
        if node_id in self.nodes:
            return True
        if len(self.nodes) >= self.limit:
            self.dropped[fields["type"]] = self.dropped.get(fields["type"], 0) + 1
            return False
        self.nodes[node_id] = {"id": node_id, **fields}
        return True

    def edge(self, source: str, target: str, kind: str, **fields: Any) -> None:
        if source in self.nodes and target in self.nodes:
            self.edges.append({"from": source, "to": target, "kind": kind, **fields})


def build_control_graph(agent_name: str, *, org_id: str, include_install_level: bool, window: TimeRange | None = None,
                        depth: int = 2, limit: int = DEFAULT_LIMIT, now: datetime | None = None) -> dict[str, Any]:
    """The agent's relationships within one org. The caller has already checked ownership."""
    now = now or datetime.now(timezone.utc)
    window = window or default_window(org_id, now)
    depth = 1 if depth == 1 else 2
    limit = max(1, min(int(limit), MAX_LIMIT))
    graph = _Graph(limit)

    identity = _identity(agent_name, org_id)
    runtime = _runtime(agent_name, org_id)
    policy = _published_policy(org_id)
    emergency = _emergency(org_id)
    catalogue = set(main.permissions)
    agent_id = f"agent:{agent_name}"

    graph.node(agent_id, type="agent", label=agent_name, status=runtime["agent_status"], path=f"/agents/{agent_name}",
               facts={"risk_score": runtime["risk_score"]})

    # Identity, scopes and the tools they reach, with the controls currently limiting them.
    scopes = identity["scopes"] if identity else []
    if identity:
        credential_id = f"credential:{agent_name}"
        graph.node(credential_id, type="credential", label=f"Credential ({identity['credential_status'].lower()})",
                   status=identity["credential_status"],
                   facts={key: identity[key] for key in ("created_at", "rotated_at", "revoked_at")})
        graph.edge(agent_id, credential_id, "authenticates_with")
        for scope in scopes:
            scope_id = f"scope:{scope}"
            if graph.node(scope_id, type="scope", label=scope):
                graph.edge(credential_id, scope_id, "grants")
            if scope in catalogue:
                decision = (policy or {}).get("permissions", {}).get(scope, "BLOCK")
                disabled = scope in emergency["disabled_tools"]
                tool_id = f"tool:{scope}"
                if graph.node(tool_id, type="tool", label=scope, status="DISABLED" if disabled else decision,
                              facts={"current_policy_decision": decision, "emergency_disabled": disabled}):
                    graph.edge(scope_id, tool_id, "reaches")
                if disabled and graph.node(f"control:disabled_tool:{scope}", type="control", label=f"Emergency: {scope} disabled", status="ACTIVE", path="/policies"):
                    graph.edge(f"control:disabled_tool:{scope}", tool_id, "limits")

    if emergency["global_deny"] and graph.node("control:global_deny", type="control", label="Emergency global deny", status="ACTIVE", path="/policies"):
        graph.edge("control:global_deny", agent_id, "limits")
    if agent_name in emergency["disabled_agents"] and graph.node("control:disabled_agent", type="control", label="Emergency: agent disabled", status="ACTIVE", path="/policies"):
        graph.edge("control:disabled_agent", agent_id, "limits")

    if policy and graph.node(f"policy:{policy['policy_id']}", type="policy_version", label=f"Policy v{policy['version_number']}",
                             status="PUBLISHED", path="/policies", facts={"current": True}):
        graph.edge(f"policy:{policy['policy_id']}", agent_id, "governs")

    # Requests in the window, each linked to what decided it: exact when recorded, else inferred.
    rows = _requests(agent_name, org_id, window, limit)
    requests_truncated = len(rows) > limit
    rows = rows[:limit]
    records = decision_provenance.get_decision_records([row["request_id"] for row in rows], org_id=org_id)
    versions = _policy_versions(org_id)
    request_ids: list[str] = []
    basis_counts = {"recorded": 0, "inferred": 0, "unknown": 0}

    for row in rows:
        request_id = f"request:{row['request_id']}"
        label = f"{row['action']} · {_short(row['target'])}" if row["target"] else row["action"]
        if not graph.node(request_id, type="request", label=label, status=row["policy_decision"],
                          path=f"/requests/{row['request_id']}",
                          facts={"timestamp": row["timestamp"], "approval_status": row["approval_status"],
                                 "execution_status": row["execution_status"]}):
            requests_truncated = True
            continue
        request_ids.append(row["request_id"])
        graph.edge(agent_id, request_id, "requested")
        if f"tool:{row['action']}" in graph.nodes:
            graph.edge(request_id, f"tool:{row['action']}", "uses")

        record = records.get(row["request_id"])
        if record:
            basis_counts["recorded"] += 1
            version_id = record["policy_version_id"]
            stored_version = versions.get(version_id) if version_id else None
            evidence = {
                "basis": "recorded", "matched_rule_id": record["matched_rule_id"], "rule_type": record["rule_type"],
                "rule_name": record["rule_name"], "outcome": record["outcome"], "policy_source": record["policy_source"],
                "record_intact": decision_provenance.record_intact(record),
                # Does the stored version still hold the content that decided? None when no stored
                # version decided (an emergency control, agent state or the built-in fallback).
                "policy_matches": (stored_version is not None and decision_provenance.policy_fingerprint(stored_version) == record["policy_fingerprint"])
                if version_id else None,
            }
            if record["policy_version_id"]:
                target = f"policy:{record['policy_version_id']}"
                graph.node(target, type="policy_version", label=f"Policy v{record['policy_version_number']}",
                           status=versions.get(record["policy_version_id"], {}).get("status", "UNKNOWN"), path="/policies")
            else:
                target = f"rule:{record['matched_rule_id']}"
                graph.node(target, type="control", label=record["rule_name"], status=record["rule_type"])
            graph.edge(request_id, target, "decided_by", **evidence)
        else:
            inferred = _inferred_version(versions, row["timestamp"])
            if inferred:
                basis_counts["inferred"] += 1
                target = f"policy:{inferred['policy_id']}"
                graph.node(target, type="policy_version", label=f"Policy v{inferred['version_number']}",
                           status=inferred["status"], path="/policies")
                graph.edge(request_id, target, "decided_by", basis="inferred", outcome=row["policy_decision"],
                           note="Inferred from publication time: this request predates exact decision records.")
            else:
                basis_counts["unknown"] += 1

    # One more hop: approvals and incidents.
    withheld = {"install_level": 0}
    if depth == 2:
        for approval in _approvals(request_ids, org_id):
            approval_id = f"approval:{approval['id']}"
            if graph.node(approval_id, type="approval", label=f"{approval['decision'].title()} by {approval['actor']}",
                          status=approval["decision"], path="/approvals", facts={"timestamp": approval["timestamp"]}):
                graph.edge(f"request:{approval['request_id']}", approval_id, "reviewed_by")
        for alert in _alerts(agent_name, request_ids, org_id, window):
            alert_id = f"incident:{alert['alert_id']}"
            if graph.node(alert_id, type="incident", label=alert["title"], status=alert["status"], path="/incidents",
                          facts={"severity": alert["severity"], "created_at": alert["created_at"]}):
                source = f"request:{alert['request_id']}" if alert["request_id"] and f"request:{alert['request_id']}" in graph.nodes else agent_id
                graph.edge(source, alert_id, "raised")
        install_level = _install_level_alerts(agent_name)
        if include_install_level:
            for alert in install_level:
                alert_id = f"incident:{alert['alert_id']}"
                if graph.node(alert_id, type="incident", label=alert["title"], status=alert["status"], path="/incidents",
                              facts={"severity": alert["severity"], "created_at": alert["created_at"], "install_level": True}):
                    graph.edge(agent_id, alert_id, "raised")
        else:
            # Counted, never shown: the graph does not pretend they do not exist.
            withheld["install_level"] = len(install_level)

    counts: dict[str, int] = {}
    for node in graph.nodes.values():
        counts[node["type"]] = counts.get(node["type"], 0) + 1
    return {
        "agent": agent_name,
        "generated_at": now.isoformat(),
        "window": {**window.as_dict(), "retained_from": retained_from(org_id, now)},
        "depth": depth,
        "limit": limit,
        "nodes": list(graph.nodes.values()),
        "edges": graph.edges,
        "counts": counts,
        "decision_basis": basis_counts,
        "withheld": withheld,
        "truncated": requests_truncated or bool(graph.dropped),
        "dropped": graph.dropped,
    }


def _inferred_version(versions: dict[str, dict[str, Any]], decided_at: str) -> dict[str, Any] | None:
    """The version published most recently before the request, compared as instants (stored
    timestamps carry different offsets) at the request's one-second precision: a version
    published within the request's own second counts as before it."""
    decided = _instant(decided_at)
    if decided is None:
        return None

    def published(version):
        moment = _instant(version.get("published_at"))
        return moment.replace(microsecond=0) if moment else None

    candidates = [v for v in versions.values() if published(v) and published(v) <= decided]
    return max(candidates, key=lambda v: (_instant(v["published_at"]), v["version_number"]), default=None)


# --- Impact preview --------------------------------------------------------------------------------

CHANGES = ("revoke_scope", "revoke_credential", "disable_tool")


class PreviewError(ValueError):
    pass


def impact_preview(agent_name: str, change: str, target: str | None, *, org_id: str,
                   now: datetime | None = None) -> dict[str, Any]:
    """What a change would affect. Reads only: the change itself stays on its own page."""
    if change not in CHANGES:
        raise PreviewError(f"change must be one of {', '.join(CHANGES)}.")
    now = now or datetime.now(timezone.utc)
    window = default_window(org_id, now)
    identity = _identity(agent_name, org_id)
    scopes = identity["scopes"] if identity else []
    reachable = sorted(scope for scope in scopes if scope in main.permissions)

    if change == "revoke_scope":
        if not target or target not in scopes:
            raise PreviewError("Choose one of this agent's scopes.")
        unreachable, actions, note = [target] if target in main.permissions else [], {target}, None
    elif change == "revoke_credential":
        if not identity:
            raise PreviewError("This agent has no credential to revoke.")
        unreachable, actions, note = reachable, None, "Every request from this agent would be refused until a new credential is issued."
    else:
        if not target or target not in main.permissions:
            raise PreviewError("Choose a tool from the catalogue.")
        unreachable, actions = [target], {target}
        note = "Disabling a tool affects every agent in this organization; only this agent's requests are counted here."

    fragment, bounds = window.condition("timestamp")
    action_filter = f" AND {_in('action', sorted(actions))}" if actions else ""
    rows = _rows(
        "SELECT request_id, timestamp, action, policy_decision FROM tool_requests "
        f"WHERE org_id = ? AND agent_name = ? AND {fragment}{action_filter} "  # nosec B608  # constants and placeholders only
        "AND policy_decision IN ('ALLOW', 'ASK') ORDER BY timestamp DESC",
        (org_id, agent_name, *bounds, *(sorted(actions) if actions else [])),
    )
    return {
        "read_only": True,
        "agent": agent_name,
        "change": change,
        "target": target,
        "window": {**window.as_dict(), "retained_from": retained_from(org_id, now)},
        "unreachable_tools": unreachable,
        "remaining_tools": [tool for tool in reachable if tool not in unreachable],
        "affected_requests": {
            "count": len(rows),
            "sample": [{"request_id": row["request_id"], "timestamp": row["timestamp"], "action": row["action"],
                        "policy_decision": row["policy_decision"], "path": f"/requests/{row['request_id']}"}
                       for row in rows[:SAMPLE_SIZE]],
        },
        "note": note,
        "how_to_apply": "Nothing changes here. Make the change on the Agents or Policies page, where it is confirmed and recorded.",
    }
