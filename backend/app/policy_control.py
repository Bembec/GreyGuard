"""GreyGuard policy versioning and change-control storage."""

import json
from . import db_compat as sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from .database import database_path


POLICY_STATUSES = {
    "DRAFT",
    "PENDING_APPROVAL",
    "PUBLISHED",
    "ARCHIVED",
    "REJECTED",
}


def utc_now():
    """Return a consistent UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def connect():
    """Open the GreyGuard database with named columns."""

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def serialize_policy(row):
    """Convert a stored policy row into API-safe data."""

    if row is None:
        return None

    return {
        "policy_id": row["policy_id"],
        "version_number": row["version_number"],
        "status": row["status"],
        "permissions": json.loads(row["permissions_json"]),
        "risk_weights": json.loads(row["risk_weights_json"]),
        "max_blocked_attempts": row["max_blocked_attempts"],
        "max_risk_score": row["max_risk_score"],
        "change_summary": row["change_summary"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "submitted_at": row["submitted_at"],
        "approved_by": row["approved_by"],
        "approved_at": row["approved_at"],
        "published_at": row["published_at"],
        "supersedes_policy_id": row["supersedes_policy_id"],
    }


def get_published_policy(*, org_id):
    """Return an org's published policy - the one its agents are enforced against.

    Every org has one: an org without any policy version yet is seeded on first use with the
    install defaults (see seed_org_policy())."""

    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM policy_versions
            WHERE status = 'PUBLISHED' AND org_id = ?
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (org_id,),
        ).fetchone()

    if row is None and seed_org_policy(org_id):
        return get_published_policy(org_id=org_id)

    return serialize_policy(row)


def list_policy_versions(*, org_id):
    """Return every policy version of one org, newest first."""

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM policy_versions
            WHERE org_id = ?
            ORDER BY version_number DESC
            """,
            (org_id,),
        ).fetchall()

    return [serialize_policy(row) for row in rows]


def get_policy_version(policy_id, *, org_id):
    """Return one of an org's policy versions or raise KeyError - another org's version is
    indistinguishable from a missing one."""

    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM policy_versions
            WHERE policy_id = ? AND org_id = ?
            """,
            (policy_id, org_id),
        ).fetchone()

    if row is None:
        raise KeyError("Policy version not found.")

    return serialize_policy(row)


def get_policy_history(policy_id, *, org_id):
    """Return the immutable change history for one policy."""

    get_policy_version(policy_id, org_id=org_id)

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                event_id,
                policy_id,
                timestamp,
                actor,
                event_type,
                note
            FROM policy_change_events
            WHERE policy_id = ? AND org_id = ?
            ORDER BY event_id DESC
            """,
            (policy_id, org_id),
        ).fetchall()

    return [dict(row) for row in rows]


def validate_policy_values(
    permissions,
    risk_weights,
    max_blocked_attempts,
    max_risk_score,
):
    """Reject malformed or unsafe policy documents."""

    if not permissions:
        raise ValueError(
            "A policy must contain at least one action."
        )

    if set(permissions) != set(risk_weights):
        raise ValueError(
            "Permissions and risk weights must use identical actions."
        )

    invalid_decisions = {
        decision
        for decision in permissions.values()
        if decision not in {"ALLOW", "ASK", "BLOCK"}
    }

    if invalid_decisions:
        raise ValueError(
            "Policy decisions must be ALLOW, ASK, or BLOCK."
        )

    if any(
        not isinstance(weight, int)
        or isinstance(weight, bool)
        or weight < 0
        or weight > 100
        for weight in risk_weights.values()
    ):
        raise ValueError(
            "Risk weights must be integers from 0 to 100."
        )

    if (
        not isinstance(max_blocked_attempts, int)
        or isinstance(max_blocked_attempts, bool)
        or max_blocked_attempts < 1
        or max_blocked_attempts > 100
    ):
        raise ValueError(
            "Blocked-attempt threshold must be from 1 to 100."
        )

    if (
        not isinstance(max_risk_score, int)
        or isinstance(max_risk_score, bool)
        or max_risk_score < 1
        or max_risk_score > 10_000
    ):
        raise ValueError(
            "Risk-score threshold must be from 1 to 10000."
        )


def add_policy_event(
    connection,
    policy_id,
    actor,
    event_type,
    note=None,
    *,
    org_id,
):
    """Append an immutable policy change event."""

    connection.execute(
        """
        INSERT INTO policy_change_events (
            policy_id,
            timestamp,
            actor,
            event_type,
            note,
            org_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            policy_id,
            utc_now(),
            actor,
            event_type,
            note,
            org_id,
        ),
    )


def create_policy_draft(
    permissions,
    risk_weights,
    max_blocked_attempts,
    max_risk_score,
    change_summary,
    created_by,
    *,
    org_id,
):
    """Create a new draft without changing live enforcement."""

    validate_policy_values(
        permissions,
        risk_weights,
        max_blocked_attempts,
        max_risk_score,
    )

    normalized_summary = change_summary.strip()

    if not normalized_summary:
        raise ValueError("A change summary is required.")

    policy_id = str(uuid4())
    timestamp = utc_now()

    active = get_published_policy(org_id=org_id)

    if active is None:
        raise RuntimeError(
            "No published policy is available."
        )

    with connect() as connection:
        next_version = connection.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) + 1
            FROM policy_versions
            WHERE org_id = ?
            """,
            (org_id,),
        ).fetchone()[0]

        connection.execute(
            """
            INSERT INTO policy_versions (
                policy_id,
                version_number,
                status,
                permissions_json,
                risk_weights_json,
                max_blocked_attempts,
                max_risk_score,
                change_summary,
                created_by,
                created_at,
                supersedes_policy_id,
                org_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy_id,
                next_version,
                "DRAFT",
                json.dumps(permissions, sort_keys=True),
                json.dumps(risk_weights, sort_keys=True),
                max_blocked_attempts,
                max_risk_score,
                normalized_summary,
                created_by,
                timestamp,
                active["policy_id"],
                org_id,
            ),
        )

        add_policy_event(
            connection,
            policy_id,
            created_by,
            "DRAFT_CREATED",
            normalized_summary,
            org_id=org_id,
        )

    return get_policy_version(policy_id, org_id=org_id)


def update_policy_draft(
    policy_id,
    permissions,
    risk_weights,
    max_blocked_attempts,
    max_risk_score,
    change_summary,
    actor,
    *,
    org_id,
):
    """Replace an editable draft policy document."""

    validate_policy_values(
        permissions,
        risk_weights,
        max_blocked_attempts,
        max_risk_score,
    )

    normalized_summary = change_summary.strip()

    if not normalized_summary:
        raise ValueError("A change summary is required.")

    with connect() as connection:
        existing = connection.execute(
            """
            SELECT status
            FROM policy_versions
            WHERE policy_id = ? AND org_id = ?
            """,
            (policy_id, org_id),
        ).fetchone()

        if existing is None:
            raise KeyError("Policy version not found.")

        if existing["status"] != "DRAFT":
            raise ValueError(
                "Only draft policy versions can be edited."
            )

        connection.execute(
            """
            UPDATE policy_versions
            SET
                permissions_json = ?,
                risk_weights_json = ?,
                max_blocked_attempts = ?,
                max_risk_score = ?,
                change_summary = ?
            WHERE policy_id = ? AND org_id = ?
            """,
            (
                json.dumps(permissions, sort_keys=True),
                json.dumps(risk_weights, sort_keys=True),
                max_blocked_attempts,
                max_risk_score,
                normalized_summary,
                policy_id,
                org_id,
            ),
        )

        add_policy_event(
            connection,
            policy_id,
            actor,
            "DRAFT_UPDATED",
            normalized_summary,
            org_id=org_id,
        )

    return get_policy_version(policy_id, org_id=org_id)


def submit_policy(policy_id, actor, *, org_id):
    """Freeze a draft and send it for approval."""
    with connect() as connection:
        row = connection.execute("SELECT status FROM policy_versions WHERE policy_id = ? AND org_id = ?", (policy_id, org_id)).fetchone()
        if row is None:
            raise KeyError("Policy version not found.")
        if row["status"] != "DRAFT":
            raise ValueError("Only draft policies can be submitted.")
        connection.execute("UPDATE policy_versions SET status = 'PENDING_APPROVAL', submitted_at = ? WHERE policy_id = ? AND org_id = ?", (utc_now(), policy_id, org_id))
        add_policy_event(connection, policy_id, actor, "SUBMITTED_FOR_APPROVAL", "Policy locked pending Platform Admin review.", org_id=org_id)
    return get_policy_version(policy_id, org_id=org_id)


def approve_policy(policy_id, actor, *, org_id):
    """Publish an approved policy and archive the org's previous version.

    Publishing *is* enforcement: main.evaluate_action() reads the agent's org's published policy
    from here on every decision, so there is no in-process copy to update - and no way for one
    org's approval to change what another org's agents are evaluated against."""
    timestamp = utc_now()
    with connect() as connection:
        row = connection.execute("SELECT * FROM policy_versions WHERE policy_id = ? AND org_id = ?", (policy_id, org_id)).fetchone()
        if row is None:
            raise KeyError("Policy version not found.")
        if row["status"] != "PENDING_APPROVAL":
            raise ValueError("Only pending policies can be approved.")
        if row["created_by"] == actor:
            raise ValueError("Four-eyes approval requires a different administrator.")
        connection.execute("UPDATE policy_versions SET status = 'ARCHIVED' WHERE status = 'PUBLISHED' AND org_id = ?", (org_id,))
        connection.execute("UPDATE policy_versions SET status = 'PUBLISHED', approved_by = ?, approved_at = ?, published_at = ? WHERE policy_id = ? AND org_id = ?", (actor, timestamp, timestamp, policy_id, org_id))
        add_policy_event(connection, policy_id, actor, "APPROVED_AND_PUBLISHED", "Approved policy became the active enforcement version.", org_id=org_id)
    return get_policy_version(policy_id, org_id=org_id)


def reject_policy(policy_id, actor, note, *, org_id):
    """Reject a pending policy without affecting enforcement."""
    with connect() as connection:
        row = connection.execute("SELECT status FROM policy_versions WHERE policy_id = ? AND org_id = ?", (policy_id, org_id)).fetchone()
        if row is None:
            raise KeyError("Policy version not found.")
        if row["status"] != "PENDING_APPROVAL":
            raise ValueError("Only pending policies can be rejected.")
        connection.execute("UPDATE policy_versions SET status = 'REJECTED' WHERE policy_id = ? AND org_id = ?", (policy_id, org_id))
        add_policy_event(connection, policy_id, actor, "REJECTED", note.strip() or "Policy change rejected.", org_id=org_id)
    return get_policy_version(policy_id, org_id=org_id)


def create_rollback_draft(policy_id, actor, *, org_id):
    """Clone a historical policy into a new auditable draft."""
    source = get_policy_version(policy_id, org_id=org_id)
    return create_policy_draft(
        source["permissions"], source["risk_weights"],
        source["max_blocked_attempts"], source["max_risk_score"],
        f"Rollback to version {source['version_number']}", actor, org_id=org_id,
    )


def explain_decision(decision):
    """Return an operator-facing explanation for a policy decision."""
    return {
        "ALLOW": "The scoped request may proceed without human approval.",
        "ASK": "The request requires authorized human approval before execution.",
        "BLOCK": "The request is denied by policy and contributes to risk.",
        "REFUSED": "The request is refused because the agent is suspended or globally disabled.",
    }.get(decision, "Unknown actions fail closed and are blocked.")


def simulate_policy(policy_id, action, has_scope=True, suspended=False, current_risk=0, *, org_id):
    """Evaluate a policy without changing enforcement or agent state."""
    policy = get_policy_version(policy_id, org_id=org_id)
    configured = policy["permissions"].get(action, "BLOCK")
    risk_added = policy["risk_weights"].get(action, 40)
    decision = "REFUSED" if suspended else (configured if has_scope else "BLOCK")
    projected_risk = min(current_risk + (risk_added if decision in {"ASK", "BLOCK"} else 0), 10_000)
    return {
        "policy_id": policy_id, "action": action, "decision": decision,
        "configured_decision": configured, "risk_added": risk_added,
        "projected_risk": projected_risk,
        "would_suspend": projected_risk >= policy["max_risk_score"],
        "explanation": explain_decision(decision), "simulated": True,
        "side_effects": False,
    }


def detect_policy_conflicts(policy_id, *, org_id):
    """Identify unsafe policy combinations before approval."""
    policy = get_policy_version(policy_id, org_id=org_id)
    findings = []
    for action, decision in policy["permissions"].items():
        risk = policy["risk_weights"][action]
        if decision == "ALLOW" and risk >= 40:
            findings.append({"action": action, "severity": "HIGH", "code": "HIGH_RISK_ALLOWED", "detail": "High-risk action is allowed without approval."})
        if decision == "BLOCK" and risk == 0:
            findings.append({"action": action, "severity": "MEDIUM", "code": "BLOCK_WITHOUT_RISK", "detail": "Blocked action does not increase risk."})
    return {"policy_id": policy_id, "conflicts": findings, "conflict_count": len(findings)}


def add_policy_test_case(policy_id, name, action, expected_decision, has_scope=True, suspended=False, *, org_id):
    """Store a repeatable policy expectation."""
    if expected_decision not in {"ALLOW", "ASK", "BLOCK", "REFUSED"}:
        raise ValueError("Expected decision is invalid.")
    get_policy_version(policy_id, org_id=org_id)
    test_id = str(uuid4())
    with connect() as connection:
        connection.execute(
            """INSERT INTO policy_test_cases
            (test_id,policy_id,name,action,expected_decision,has_scope,suspended,created_at,org_id)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (test_id, policy_id, name.strip(), action, expected_decision, int(has_scope), int(suspended), utc_now(), org_id),
        )
    return {"test_id": test_id, "policy_id": policy_id, "name": name.strip(), "action": action, "expected_decision": expected_decision}


def run_policy_tests(policy_id, *, org_id):
    """Run stored test cases against a draft or historical policy."""
    get_policy_version(policy_id, org_id=org_id)
    with connect() as connection:
        rows = connection.execute("SELECT * FROM policy_test_cases WHERE policy_id=? AND org_id=? ORDER BY created_at", (policy_id, org_id)).fetchall()
    results = []
    for row in rows:
        actual = simulate_policy(policy_id, row["action"], bool(row["has_scope"]), bool(row["suspended"]), org_id=org_id)["decision"]
        results.append({"test_id": row["test_id"], "name": row["name"], "expected": row["expected_decision"], "actual": actual, "passed": actual == row["expected_decision"]})
    return {"policy_id": policy_id, "passed": all(item["passed"] for item in results), "total": len(results), "results": results}


def get_emergency_controls(*, org_id):
    """Return one org's fail-closed emergency controls. global_deny stops every agent *of that
    org*; it can no longer stop other orgs' agents."""
    with connect() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO policy_emergency_controls
            (control_id,org_id,global_deny,disabled_agents_json,disabled_tools_json,disabled_integrations_json,updated_by,updated_at)
            VALUES(1,?,0,'[]','[]','[]','SYSTEM',?)""", (org_id, utc_now())
        )
        row = connection.execute("SELECT * FROM policy_emergency_controls WHERE control_id=1 AND org_id=?", (org_id,)).fetchone()
    return {
        "global_deny": bool(row["global_deny"]),
        "disabled_agents": json.loads(row["disabled_agents_json"]),
        "disabled_tools": json.loads(row["disabled_tools_json"]),
        "disabled_integrations": json.loads(row["disabled_integrations_json"]),
        "updated_by": row["updated_by"], "updated_at": row["updated_at"],
    }


def update_emergency_controls(global_deny, disabled_agents, disabled_tools, disabled_integrations, actor, *, org_id):
    """Atomically update one org's audited emergency policy switches."""
    get_emergency_controls(org_id=org_id)
    timestamp = utc_now()
    with connect() as connection:
        connection.execute(
            """UPDATE policy_emergency_controls SET global_deny=?,disabled_agents_json=?,
            disabled_tools_json=?,disabled_integrations_json=?,updated_by=?,updated_at=? WHERE control_id=1 AND org_id=?""",
            (int(global_deny), json.dumps(sorted(set(disabled_agents))), json.dumps(sorted(set(disabled_tools))), json.dumps(sorted(set(disabled_integrations))), actor, timestamp, org_id),
        )
        connection.execute(
            "INSERT INTO policy_emergency_events(timestamp,actor,global_deny,detail,org_id) VALUES(?,?,?,?,?)",
            (timestamp, actor, int(global_deny), "Emergency policy controls updated.", org_id),
        )
    return get_emergency_controls(org_id=org_id)


_POLICY_VERSIONS_SCHEMA = """(
    policy_id TEXT PRIMARY KEY,
    version_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    permissions_json TEXT NOT NULL,
    risk_weights_json TEXT NOT NULL,
    max_blocked_attempts INTEGER NOT NULL,
    max_risk_score INTEGER NOT NULL,
    change_summary TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    submitted_at TEXT,
    approved_by TEXT,
    approved_at TEXT,
    published_at TEXT,
    supersedes_policy_id TEXT,
    org_id TEXT NOT NULL DEFAULT 'org_default',
    UNIQUE (version_number, org_id),
    FOREIGN KEY (supersedes_policy_id)
        REFERENCES policy_versions(policy_id)
)"""
_POLICY_VERSION_COLUMNS = (
    "policy_id,version_number,status,permissions_json,risk_weights_json,max_blocked_attempts,"
    "max_risk_score,change_summary,created_by,created_at,submitted_at,approved_by,approved_at,"
    "published_at,supersedes_policy_id"
)

# The install defaults each org's first published policy is seeded from (main.py's built-in
# rules, handed over by initialize_policy_control() at startup).
_DEFAULT_POLICY = {}


def _upgrade_legacy_policy_tables():
    """Bring a pre-org database up to the org-scoped schema (P2.2 policy batch).

    Runs on a plain connection, *without* connect()'s PRAGMA foreign_keys = ON: SQLite's
    DROP TABLE performs an implicit DELETE, which would fail against policy_change_events' and
    policy_test_cases' foreign keys. Uses batch 15's build-new/drop/rename-into-place order, so
    SQLite never rewrites those inbound foreign keys (or the table's own self-reference) to point
    at a renamed-aside table."""

    with sqlite3.connect(database_path) as connection:
        version_columns = [row[1] for row in connection.execute("PRAGMA table_info(policy_versions)")]
        if version_columns and "org_id" not in version_columns:
            # version_number was globally UNIQUE: two orgs could never both have a version 1.
            connection.execute("CREATE TABLE policy_versions_org " + _POLICY_VERSIONS_SCHEMA)
            connection.execute(
                f"INSERT INTO policy_versions_org ({_POLICY_VERSION_COLUMNS},org_id) "
                f"SELECT {_POLICY_VERSION_COLUMNS},'org_default' FROM policy_versions"
            )
            connection.execute("DROP TABLE policy_versions")
            connection.execute("ALTER TABLE policy_versions_org RENAME TO policy_versions")
        control_columns = [row[1] for row in connection.execute("PRAGMA table_info(policy_emergency_controls)")]
        if control_columns and "org_id" not in control_columns:
            # The former singleton (PK control_id, CHECK control_id = 1): one org's global_deny
            # stopped every org's agents. Nothing references it, so renaming aside is safe.
            connection.execute("ALTER TABLE policy_emergency_controls RENAME TO policy_emergency_controls_pre_org")
        for table in ("policy_change_events", "policy_test_cases", "policy_emergency_events"):
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if columns and "org_id" not in columns:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN org_id TEXT NOT NULL DEFAULT 'org_default'")


def initialize_policy_control(
    permissions,
    risk_weights,
    max_blocked_attempts,
    max_risk_score,
):
    """Create the org-scoped policy tables and record the install defaults new orgs are seeded
    from. The default org's first policy is seeded here, as it always was; every other org is
    seeded on first use (get_published_policy())."""

    _DEFAULT_POLICY.update(
        permissions=dict(permissions),
        risk_weights=dict(risk_weights),
        max_blocked_attempts=max_blocked_attempts,
        max_risk_score=max_risk_score,
    )
    _upgrade_legacy_policy_tables()

    with connect() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS policy_versions " + _POLICY_VERSIONS_SCHEMA)

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS policy_change_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                note TEXT,
                org_id TEXT NOT NULL DEFAULT 'org_default',
                FOREIGN KEY (policy_id)
                    REFERENCES policy_versions(policy_id)
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_policy_versions_status
            ON policy_versions (
                status,
                version_number
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_policy_change_events_policy
            ON policy_change_events (
                policy_id,
                event_id
            )
            """
        )

        connection.execute(
            """CREATE TABLE IF NOT EXISTS policy_test_cases (
            test_id TEXT PRIMARY KEY, policy_id TEXT NOT NULL, name TEXT NOT NULL,
            action TEXT NOT NULL, expected_decision TEXT NOT NULL, has_scope INTEGER NOT NULL,
            suspended INTEGER NOT NULL, created_at TEXT NOT NULL,
            org_id TEXT NOT NULL DEFAULT 'org_default',
            FOREIGN KEY(policy_id) REFERENCES policy_versions(policy_id))"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS policy_emergency_controls (
            control_id INTEGER NOT NULL CHECK(control_id=1),
            org_id TEXT NOT NULL DEFAULT 'org_default', global_deny INTEGER NOT NULL,
            disabled_agents_json TEXT NOT NULL, disabled_tools_json TEXT NOT NULL,
            disabled_integrations_json TEXT NOT NULL, updated_by TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY (control_id, org_id))"""
        )
        legacy_controls = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='policy_emergency_controls_pre_org'"
        ).fetchone() if sqlite3.backend_name() == "sqlite" else None
        if legacy_controls:
            connection.execute(
                """INSERT INTO policy_emergency_controls
                (control_id,org_id,global_deny,disabled_agents_json,disabled_tools_json,disabled_integrations_json,updated_by,updated_at)
                SELECT control_id,'org_default',global_deny,disabled_agents_json,disabled_tools_json,disabled_integrations_json,updated_by,updated_at
                FROM policy_emergency_controls_pre_org"""
            )
            connection.execute("DROP TABLE policy_emergency_controls_pre_org")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS policy_emergency_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
            actor TEXT NOT NULL, global_deny INTEGER NOT NULL, detail TEXT NOT NULL,
            org_id TEXT NOT NULL DEFAULT 'org_default')"""
        )

    seed_org_policy("org_default")
    get_emergency_controls(org_id="org_default")


def seed_org_policy(org_id):
    """Give an org with no policy version yet its first published policy, from the install
    defaults. Returns True if a policy was created. Safe to call repeatedly."""

    if not _DEFAULT_POLICY:
        return False

    with connect() as connection:
        existing_policy = connection.execute(
            """
            SELECT policy_id
            FROM policy_versions
            WHERE org_id = ?
            LIMIT 1
            """,
            (org_id,),
        ).fetchone()

        if existing_policy is not None:
            return False

        policy_id = str(uuid4())
        timestamp = utc_now()

        try:
            connection.execute(
                """
                INSERT INTO policy_versions (
                    policy_id,
                    version_number,
                    status,
                    permissions_json,
                    risk_weights_json,
                    max_blocked_attempts,
                    max_risk_score,
                    change_summary,
                    created_by,
                    created_at,
                    approved_by,
                    approved_at,
                    published_at,
                    org_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy_id,
                    1,
                    "PUBLISHED",
                    json.dumps(_DEFAULT_POLICY["permissions"], sort_keys=True),
                    json.dumps(_DEFAULT_POLICY["risk_weights"], sort_keys=True),
                    _DEFAULT_POLICY["max_blocked_attempts"],
                    _DEFAULT_POLICY["max_risk_score"],
                    (
                        "Initial policy imported from "
                        "GreyGuard's existing enforcement rules."
                    ),
                    "SYSTEM_MIGRATION",
                    timestamp,
                    "SYSTEM_MIGRATION",
                    timestamp,
                    timestamp,
                    org_id,
                ),
            )
        except sqlite3.IntegrityError:
            # Another request seeded this org concurrently (UNIQUE(version_number, org_id)).
            return False

        add_policy_event(
            connection,
            policy_id,
            "SYSTEM_MIGRATION",
            "POLICY_IMPORTED",
            (
                "Existing GreyGuard policy stored "
                "as the initial published version."
            ),
            org_id=org_id,
        )

    return True
