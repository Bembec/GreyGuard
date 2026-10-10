"""
GreyGuard database layer.

Version 10 preserves all previous identity, authentication,
risk, and audit records while adding persistent tool requests,
human approvals, and execution evidence.
"""

import json
from . import db_compat as sqlite3
from pathlib import Path


from .paths import data_directory

database_path = data_directory() / "greyguard.db"


def initialize_database():
    """Create or upgrade the GreyGuard database."""

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL
                    DEFAULT 'legacy_agent',
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                decision TEXT NOT NULL,
                approval TEXT NOT NULL,
                risk_added INTEGER NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                agent_status TEXT NOT NULL,
                blocked_attempts INTEGER NOT NULL,
                org_id TEXT NOT NULL DEFAULT 'org_default'
            )
            """
        )

        audit_columns = connection.execute(
            "PRAGMA table_info(audit_events)"
        ).fetchall()

        audit_column_names = [
            column[1]
            for column in audit_columns
        ]

        if "agent_name" not in audit_column_names:
            connection.execute(
                """
                ALTER TABLE audit_events
                ADD COLUMN agent_name TEXT
                NOT NULL DEFAULT 'legacy_agent'
                """
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            agent_identities (
                agent_name TEXT PRIMARY KEY,
                credential_salt TEXT NOT NULL,
                credential_hash TEXT NOT NULL,
                scopes_json TEXT NOT NULL,
                credential_status TEXT NOT NULL
                    DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL,
                rotated_at TEXT,
                revoked_at TEXT,
                org_id TEXT NOT NULL DEFAULT 'org_default'
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            agent_credential_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                org_id TEXT NOT NULL DEFAULT 'org_default'
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_agent_credential_events_agent
            ON agent_credential_events(agent_name, id)
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            authentication_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                claimed_agent_name TEXT,
                authenticated_agent_name TEXT,
                action TEXT,
                outcome TEXT NOT NULL,
                reason TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            tool_requests (
                request_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                payload_json TEXT NOT NULL,
                dry_run INTEGER NOT NULL DEFAULT 0,
                policy_decision TEXT NOT NULL,
                approval_status TEXT NOT NULL,
                execution_status TEXT NOT NULL,
                risk_added INTEGER NOT NULL,
                risk_score INTEGER NOT NULL,
                result_json TEXT,
                executed_at TEXT,
                org_id TEXT NOT NULL DEFAULT 'org_default'
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            approval_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                decision TEXT NOT NULL,
                note TEXT,
                org_id TEXT NOT NULL DEFAULT 'org_default',
                FOREIGN KEY (request_id)
                    REFERENCES tool_requests(request_id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            execution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                execution_status TEXT NOT NULL,
                result_json TEXT NOT NULL,
                org_id TEXT NOT NULL DEFAULT 'org_default',
                FOREIGN KEY (request_id)
                    REFERENCES tool_requests(request_id)
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_audit_events_agent
            ON audit_events (
                agent_name,
                id
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_authentication_events_agent
            ON authentication_events (
                claimed_agent_name,
                id
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_tool_requests_agent
            ON tool_requests (
                agent_name,
                timestamp
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_tool_requests_approval
            ON tool_requests (
                approval_status,
                timestamp
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_tool_requests_execution
            ON tool_requests (
                execution_status,
                timestamp
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_approval_events_request
            ON approval_events (
                request_id,
                id
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_execution_events_request
            ON execution_events (
                request_id,
                id
            )
            """
        )

        # P2.2 agent scoping: every agent belongs to exactly one org (batch A), and every piece
        # of evidence an agent produces - policy decisions, tool requests, approvals, executions
        # - belongs to that agent's org (batch B). agent_name stays the primary key of
        # agent_identities: agent names are a global namespace, like administrator emails,
        # because an agent authenticates by name (key or certificate) before any org can be
        # resolved. Everything that predates orgs belongs to org_default.
        for org_scoped_table in (
            "audit_events",
            "agent_identities",
            "agent_credential_events",
            "tool_requests",
            "approval_events",
            "execution_events",
        ):
            org_scoped_columns = {
                column[1]
                for column in connection.execute(
                    f"PRAGMA table_info({org_scoped_table})"
                )
            }
            if "org_id" not in org_scoped_columns:
                connection.execute(
                    f"ALTER TABLE {org_scoped_table} ADD COLUMN "
                    "org_id TEXT NOT NULL DEFAULT 'org_default'"
                )


def save_audit_event(
    agent_name,
    timestamp,
    action,
    decision,
    approval,
    risk_added,
    risk_score,
    risk_level,
    agent_status,
    blocked_attempts,
    *,
    org_id,
):
    """Save one GreyGuard security event."""

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO audit_events (
                agent_name,
                timestamp,
                action,
                decision,
                approval,
                risk_added,
                risk_score,
                risk_level,
                agent_status,
                blocked_attempts,
                org_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_name,
                timestamp,
                action,
                decision,
                approval,
                risk_added,
                risk_score,
                risk_level,
                agent_status,
                blocked_attempts,
                org_id,
            ),
        )


def get_recent_audit_events(
    agent_name,
    limit=5,
    *,
    org_id,
):
    """Return recent policy events for one agent."""

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            SELECT
                agent_name,
                timestamp,
                action,
                decision,
                approval,
                risk_score,
                risk_level,
                agent_status
            FROM audit_events
            WHERE agent_name = ? AND org_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                agent_name,
                org_id,
                limit,
            ),
        )

        return cursor.fetchall()


def get_audit_summary(agent_name, *, org_id):
    """Return policy-audit statistics for one agent."""

    with sqlite3.connect(database_path) as connection:
        summary = connection.execute(
            """
            SELECT
                COUNT(*),
                SUM(
                    CASE
                        WHEN decision = 'ALLOW'
                        THEN 1
                        ELSE 0
                    END
                ),
                SUM(
                    CASE
                        WHEN decision = 'ASK'
                        THEN 1
                        ELSE 0
                    END
                ),
                SUM(
                    CASE
                        WHEN decision = 'BLOCK'
                        THEN 1
                        ELSE 0
                    END
                ),
                SUM(
                    CASE
                        WHEN decision = 'REFUSED'
                        THEN 1
                        ELSE 0
                    END
                ),
                COALESCE(
                    MAX(risk_score),
                    0
                )
            FROM audit_events
            WHERE agent_name = ? AND org_id = ?
            """,
            (agent_name, org_id),
        ).fetchone()

    return {
        "total_events": summary[0],
        "allowed": summary[1] or 0,
        "asked": summary[2] or 0,
        "blocked": summary[3] or 0,
        "refused": summary[4] or 0,
        "highest_risk_score": summary[5],
    }


def create_agent_identity(
    agent_name,
    credential_salt,
    credential_hash,
    scopes,
    timestamp,
    *,
    org_id,
):
    """Store a new agent identity."""

    scopes_json = json.dumps(
        sorted(set(scopes))
    )

    try:
        with sqlite3.connect(
            database_path
        ) as connection:
            connection.execute(
                """
                INSERT INTO agent_identities (
                    agent_name,
                    credential_salt,
                    credential_hash,
                    scopes_json,
                    credential_status,
                    created_at,
                    rotated_at,
                    revoked_at,
                    org_id
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    'ACTIVE',
                    ?,
                    NULL,
                    NULL,
                    ?
                )
                """,
                (
                    agent_name,
                    credential_salt,
                    credential_hash,
                    scopes_json,
                    timestamp,
                    org_id,
                ),
            )

    except sqlite3.IntegrityError:
        return False

    return True


def get_agent_identity(agent_name):
    """Return one stored agent identity, including the org that owns it.

    Deliberately not filtered by org: agent names are a global namespace, and this is how an
    agent's org is *found* - agent authentication runs before any org is known. Callers acting
    for an administrator must compare the returned org_id with the administrator's own org
    (see main.agent_org_id())."""

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            -- global agent-name lookup, no org_id filter: see get_agent_identity() docstring
            SELECT
                org_id,
                agent_name,
                credential_salt,
                credential_hash,
                scopes_json,
                credential_status,
                created_at,
                rotated_at,
                revoked_at
            FROM agent_identities
            WHERE agent_name = ?
            """,
            (agent_name,),
        ).fetchone()

    if row is None:
        return None

    identity = dict(row)

    try:
        identity["scopes"] = json.loads(
            identity.pop("scopes_json")
        )
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        identity["scopes"] = []

    return identity


def count_agent_identities():
    """Install-wide identity count for the health endpoint."""

    with sqlite3.connect(database_path) as connection:
        return connection.execute(
            "-- install-wide count across every org_id, for /health only\n"
            "SELECT COUNT(*) FROM agent_identities"
        ).fetchone()[0]


def get_agent_identities(org_id):
    """Return one org's identities without credential hashes."""

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                agent_name,
                scopes_json,
                credential_status,
                created_at,
                rotated_at,
                revoked_at
            FROM agent_identities
            WHERE org_id = ?
            ORDER BY agent_name
            """,
            (org_id,),
        ).fetchall()

    identities = []

    for row in rows:
        identity = dict(row)

        try:
            identity["scopes"] = json.loads(
                identity.pop("scopes_json")
            )
        except (
            json.JSONDecodeError,
            TypeError,
        ):
            identity["scopes"] = []

        identities.append(identity)

    return identities


def update_agent_scopes(
    agent_name,
    scopes,
    *,
    org_id,
):
    """Replace the scopes assigned to an agent."""

    scopes_json = json.dumps(
        sorted(set(scopes))
    )

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE agent_identities
            SET scopes_json = ?
            WHERE agent_name = ? AND org_id = ?
            """,
            (
                scopes_json,
                agent_name,
                org_id,
            ),
        )

        return cursor.rowcount > 0


def rotate_agent_credential(
    agent_name,
    credential_salt,
    credential_hash,
    timestamp,
    *,
    org_id,
):
    """Replace and reactivate an agent credential."""

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE agent_identities
            SET
                credential_salt = ?,
                credential_hash = ?,
                credential_status = 'ACTIVE',
                rotated_at = ?,
                revoked_at = NULL
            WHERE agent_name = ? AND org_id = ?
            """,
            (
                credential_salt,
                credential_hash,
                timestamp,
                agent_name,
                org_id,
            ),
        )

        return cursor.rowcount > 0


def revoke_agent_credential(
    agent_name,
    timestamp,
    *,
    org_id,
):
    """Revoke an agent credential."""

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE agent_identities
            SET
                credential_status = 'REVOKED',
                revoked_at = ?
            WHERE agent_name = ? AND org_id = ?
            """,
            (
                timestamp,
                agent_name,
                org_id,
            ),
        )

        return cursor.rowcount > 0


def record_credential_history_event(
    agent_name,
    event_type,
    actor,
    timestamp,
    *,
    org_id,
):
    """Append an immutable credential lifecycle event. Never store a credential or its hash
    here - this table exists only to answer who issued, rotated, or revoked a credential and
    when, never to reconstruct or verify one."""

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO agent_credential_events
            (agent_name, timestamp, event_type, actor, org_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (agent_name, timestamp, event_type, actor, org_id),
        )


def get_credential_history(
    agent_name,
    limit=20,
    offset=0,
    *,
    org_id,
):
    """Return one page of credential lifecycle evidence, newest first."""

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, agent_name, timestamp, event_type, actor
            FROM agent_credential_events
            WHERE agent_name = ? AND org_id = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (agent_name, org_id, limit, offset),
        ).fetchall()
        total = connection.execute(
            "SELECT COUNT(*) FROM agent_credential_events WHERE agent_name = ? AND org_id = ?",
            (agent_name, org_id),
        ).fetchone()[0]

    return {
        "events": [dict(row) for row in rows],
        "total": total,
    }


def save_authentication_event(
    timestamp,
    claimed_agent_name,
    authenticated_agent_name,
    action,
    outcome,
    reason,
):
    """Save an identity or scope event."""

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO authentication_events (
                timestamp,
                claimed_agent_name,
                authenticated_agent_name,
                action,
                outcome,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                claimed_agent_name,
                authenticated_agent_name,
                action,
                outcome,
                reason,
            ),
        )


def get_recent_authentication_events(
    agent_name,
    limit=10,
):
    """Return recent authentication events."""

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                id,
                timestamp,
                claimed_agent_name,
                authenticated_agent_name,
                action,
                outcome,
                reason
            FROM authentication_events
            WHERE
                claimed_agent_name = ?
                OR authenticated_agent_name = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                agent_name,
                agent_name,
                limit,
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def decode_json_object(value):
    """Convert stored JSON into a dictionary."""

    if value is None:
        return None

    try:
        decoded_value = json.loads(value)
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return {
            "error": (
                "Stored JSON could not be decoded."
            )
        }

    if isinstance(decoded_value, dict):
        return decoded_value

    return {
        "value": decoded_value
    }


def serialize_tool_request(row):
    """Convert one tool-request row into API data."""

    if row is None:
        return None

    request = dict(row)

    request["payload"] = decode_json_object(
        request.pop("payload_json")
    ) or {}

    request["result"] = decode_json_object(
        request.pop("result_json")
    )

    request["dry_run"] = bool(
        request["dry_run"]
    )

    return request


def save_tool_request(
    request_id,
    agent_name,
    timestamp,
    action,
    target,
    payload,
    dry_run,
    policy_decision,
    approval_status,
    execution_status,
    risk_added,
    risk_score,
    *,
    org_id,
):
    """Store a new tool request."""

    payload_json = json.dumps(
        payload or {},
        sort_keys=True,
    )

    try:
        with sqlite3.connect(
            database_path
        ) as connection:
            connection.execute(
                """
                INSERT INTO tool_requests (
                    request_id,
                    agent_name,
                    timestamp,
                    updated_at,
                    action,
                    target,
                    payload_json,
                    dry_run,
                    policy_decision,
                    approval_status,
                    execution_status,
                    risk_added,
                    risk_score,
                    result_json,
                    executed_at,
                    org_id
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    NULL,
                    NULL,
                    ?
                )
                """,
                (
                    request_id,
                    agent_name,
                    timestamp,
                    timestamp,
                    action,
                    target,
                    payload_json,
                    int(bool(dry_run)),
                    policy_decision,
                    approval_status,
                    execution_status,
                    risk_added,
                    risk_score,
                    org_id,
                ),
            )

    except sqlite3.IntegrityError:
        return False

    return True


def get_tool_request(request_id, *, org_id):
    """Return one stored tool request."""

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT
                request_id,
                agent_name,
                timestamp,
                updated_at,
                action,
                target,
                payload_json,
                dry_run,
                policy_decision,
                approval_status,
                execution_status,
                risk_added,
                risk_score,
                result_json,
                executed_at,
                org_id
            FROM tool_requests
            WHERE request_id = ? AND org_id = ?
            """,
            (request_id, org_id),
        ).fetchone()

    return serialize_tool_request(row)


def get_tool_requests(
    agent_name=None,
    approval_status=None,
    execution_status=None,
    limit=50,
    *,
    org_id,
):
    """Return filtered tool requests."""

    conditions = ["org_id = ?"]
    parameters = [org_id]

    if agent_name is not None:
        conditions.append(
            "agent_name = ?"
        )
        parameters.append(agent_name)

    if approval_status is not None:
        conditions.append(
            "approval_status = ?"
        )
        parameters.append(approval_status)

    if execution_status is not None:
        conditions.append(
            "execution_status = ?"
        )
        parameters.append(execution_status)

    where_clause = (
        "WHERE "
        + " AND ".join(conditions)
    )

    parameters.append(limit)

    query = f"""
        SELECT
            request_id,
            agent_name,
            timestamp,
            updated_at,
            action,
            target,
            payload_json,
            dry_run,
            policy_decision,
            approval_status,
            execution_status,
            risk_added,
            risk_score,
            result_json,
            executed_at,
            org_id
        FROM tool_requests
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT ?
    """

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            query,
            tuple(parameters),
        ).fetchall()

    return [
        serialize_tool_request(row)
        for row in rows
    ]


def decide_tool_request(
    request_id,
    timestamp,
    actor,
    decision,
    note=None,
    *,
    org_id,
):
    """Approve or deny one pending tool request."""

    normalized_decision = (
        str(decision).strip().upper()
    )

    if normalized_decision not in (
        "APPROVED",
        "DENIED",
    ):
        raise ValueError(
            "Decision must be APPROVED or DENIED."
        )

    if normalized_decision == "DENIED":
        execution_status = "DENIED"
    else:
        execution_status = "NOT_STARTED"

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE tool_requests
            SET
                approval_status = ?,
                execution_status = ?,
                updated_at = ?
            WHERE
                request_id = ?
                AND org_id = ?
                AND approval_status = 'PENDING'
                AND execution_status = 'NOT_STARTED'
            """,
            (
                normalized_decision,
                execution_status,
                timestamp,
                request_id,
                org_id,
            ),
        )

        if cursor.rowcount == 0:
            return False

        connection.execute(
            """
            INSERT INTO approval_events (
                request_id,
                timestamp,
                actor,
                decision,
                note,
                org_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                timestamp,
                actor,
                normalized_decision,
                note,
                org_id,
            ),
        )

    return True


def claim_tool_request_execution(
    request_id,
    timestamp,
    *,
    org_id,
):
    """Atomically claim a request for one execution."""

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE tool_requests
            SET
                execution_status = 'RUNNING',
                updated_at = ?
            WHERE
                request_id = ?
                AND org_id = ?
                AND execution_status = 'NOT_STARTED'
                AND approval_status IN (
                    'NOT_REQUIRED',
                    'APPROVED'
                )
            """,
            (
                timestamp,
                request_id,
                org_id,
            ),
        )

        return cursor.rowcount > 0


def complete_tool_request_execution(
    request_id,
    timestamp,
    execution_status,
    result,
    *,
    org_id,
):
    """Finish an execution and save its evidence."""

    normalized_status = (
        str(execution_status).strip().upper()
    )

    valid_statuses = {
        "SUCCEEDED",
        "FAILED",
        "DRY_RUN",
    }

    if normalized_status not in valid_statuses:
        raise ValueError(
            "Invalid final execution status."
        )

    result_json = json.dumps(
        result or {},
        sort_keys=True,
    )

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE tool_requests
            SET
                execution_status = ?,
                result_json = ?,
                executed_at = ?,
                updated_at = ?
            WHERE
                request_id = ?
                AND org_id = ?
                AND execution_status = 'RUNNING'
            """,
            (
                normalized_status,
                result_json,
                timestamp,
                timestamp,
                request_id,
                org_id,
            ),
        )

        if cursor.rowcount == 0:
            return False

        connection.execute(
            """
            INSERT INTO execution_events (
                request_id,
                timestamp,
                execution_status,
                result_json,
                org_id
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                request_id,
                timestamp,
                normalized_status,
                result_json,
                org_id,
            ),
        )

    return True


def save_blocked_execution_result(
    request_id,
    timestamp,
    result,
    *,
    org_id,
):
    """Attach evidence to a blocked request."""

    result_json = json.dumps(
        result or {},
        sort_keys=True,
    )

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE tool_requests
            SET
                result_json = ?,
                updated_at = ?
            WHERE
                request_id = ?
                AND org_id = ?
                AND execution_status = 'BLOCKED'
            """,
            (
                result_json,
                timestamp,
                request_id,
                org_id,
            ),
        )

        return cursor.rowcount > 0


def get_approval_events(
    request_id,
    *,
    org_id,
):
    """Return approval history for a request."""

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                id,
                request_id,
                timestamp,
                actor,
                decision,
                note,
                org_id
            FROM approval_events
            WHERE request_id = ? AND org_id = ?
            ORDER BY id
            """,
            (request_id, org_id),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def get_execution_events(
    request_id,
    *,
    org_id,
):
    """Return execution history for a request."""

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                id,
                request_id,
                timestamp,
                execution_status,
                result_json,
                org_id
            FROM execution_events
            WHERE request_id = ? AND org_id = ?
            ORDER BY id
            """,
            (request_id, org_id),
        ).fetchall()

    events = []

    for row in rows:
        event = dict(row)
        event["result"] = decode_json_object(
            event.pop("result_json")
        ) or {}
        events.append(event)

    return events


def get_tool_request_details(request_id, *, org_id):
    """Return a request with approval and execution history."""

    request = get_tool_request(
        request_id,
        org_id=org_id,
    )

    if request is None:
        return None

    request["approval_events"] = (
        get_approval_events(request_id, org_id=org_id)
    )

    request["execution_events"] = (
        get_execution_events(request_id, org_id=org_id)
    )

    return request


if __name__ == "__main__":
    initialize_database()

    print(
        "GreyGuard V10 database initialized:"
    )
    print(database_path)


# Sentinel for get_administrator_audit_events(org_id=ALL_ORGS): an object, so it can never be
# produced from request input the way a magic string could.
ALL_ORGS = object()


def get_administrator_audit_events(
    event_type=None,
    agent_name=None,
    limit=100,
    *,
    org_id,
):
    """Return a unified administrator evidence timeline for one org.

    Every event carries the org_id it belongs to. org_id=ALL_ORGS is reserved for install-level
    background derivation (alerts.sync_alerts_from_events()), never for an administrator's view.
    Authentication events live in a global, pre-auth table; an org sees those whose agent belongs
    to it. Attempts against agent names that exist in no org belong to no tenant and appear only
    in the ALL_ORGS view."""

    normalized_type = (
        str(event_type).strip().upper()
        if event_type
        else None
    )
    normalized_agent = (
        str(agent_name).strip().lower()
        if agent_name
        else None
    )
    safe_limit = max(1, min(int(limit), 500))

    events = []
    every_org = org_id is ALL_ORGS
    # Each query below is either scoped to one org or - only for ALL_ORGS - deliberately spans
    # every org_id; the SQL comment says which, for tenant_guard and for the reader.
    scope = (
        "1 = 1 /* every org_id: install-level background derivation */"
        if every_org else "{alias}org_id = ?"
    )
    scope_parameters = () if every_org else (org_id,)

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        policy_rows = connection.execute(
            f"""
            SELECT
                org_id,
                id,
                timestamp,
                agent_name,
                action,
                decision,
                approval,
                risk_added,
                risk_score,
                risk_level,
                agent_status,
                blocked_attempts
            FROM audit_events
            WHERE {scope.format(alias="")}
            ORDER BY id DESC
            LIMIT ?
            """,
            (*scope_parameters, safe_limit),
        ).fetchall()

        authentication_rows = connection.execute(
            f"""
            SELECT
                identities.org_id AS org_id,
                events.id,
                events.timestamp,
                events.claimed_agent_name,
                events.authenticated_agent_name,
                events.action,
                events.outcome,
                events.reason
            FROM authentication_events AS events
            LEFT JOIN agent_identities AS identities
                ON identities.agent_name = COALESCE(
                    events.authenticated_agent_name,
                    events.claimed_agent_name
                )
            WHERE {scope.format(alias="identities.")}
            ORDER BY events.id DESC
            LIMIT ?
            """,
            (*scope_parameters, safe_limit),
        ).fetchall()

        approval_rows = connection.execute(
            f"""
            SELECT
                approvals.org_id,
                approvals.id,
                approvals.request_id,
                approvals.timestamp,
                approvals.actor,
                approvals.decision,
                approvals.note,
                requests.agent_name,
                requests.action
            FROM approval_events AS approvals
            LEFT JOIN tool_requests AS requests
                ON requests.request_id =
                   approvals.request_id
                AND requests.org_id = approvals.org_id
            WHERE {scope.format(alias="approvals.")}
            ORDER BY approvals.id DESC
            LIMIT ?
            """,
            (*scope_parameters, safe_limit),
        ).fetchall()

        execution_rows = connection.execute(
            f"""
            SELECT
                executions.org_id,
                executions.id,
                executions.request_id,
                executions.timestamp,
                executions.execution_status,
                executions.result_json,
                requests.agent_name,
                requests.action
            FROM execution_events AS executions
            LEFT JOIN tool_requests AS requests
                ON requests.request_id =
                   executions.request_id
                AND requests.org_id = executions.org_id
            WHERE {scope.format(alias="executions.")}
            ORDER BY executions.id DESC
            LIMIT ?
            """,
            (*scope_parameters, safe_limit),
        ).fetchall()

    for row in policy_rows:
        decision = row["decision"]
        severity = (
            "CRITICAL"
            if row["agent_status"] == "SUSPENDED"
            else "HIGH"
            if decision in ("BLOCK", "REFUSED")
            else "MEDIUM"
            if decision == "ASK"
            else "INFO"
        )

        events.append({
            "event_id": f"policy-{row['id']}",
            "org_id": row["org_id"],
            "event_type": "POLICY",
            "timestamp": row["timestamp"],
            "agent_name": row["agent_name"],
            "action": row["action"],
            "outcome": decision,
            "severity": severity,
            "request_id": None,
            "actor": row["agent_name"],
            "summary": (
                f"Policy decision {decision} for "
                f"{row['action']}."
            ),
            "details": {
                "approval": row["approval"],
                "risk_added": row["risk_added"],
                "risk_score": row["risk_score"],
                "risk_level": row["risk_level"],
                "agent_status": row["agent_status"],
                "blocked_attempts": (
                    row["blocked_attempts"]
                ),
            },
        })

    for row in authentication_rows:
        outcome = row["outcome"]
        successful = outcome in (
            "AUTHENTICATED",
            "SCOPE_ALLOWED",
        )

        events.append({
            "event_id": f"authentication-{row['id']}",
            "org_id": row["org_id"],
            "event_type": "AUTHENTICATION",
            "timestamp": row["timestamp"],
            "agent_name": (
                row["authenticated_agent_name"]
                or row["claimed_agent_name"]
            ),
            "action": row["action"],
            "outcome": outcome,
            "severity": (
                "INFO" if successful else "HIGH"
            ),
            "request_id": None,
            "actor": row["claimed_agent_name"],
            "summary": (
                row["reason"]
                or f"Authentication outcome: {outcome}."
            ),
            "details": {
                "claimed_agent_name": (
                    row["claimed_agent_name"]
                ),
                "authenticated_agent_name": (
                    row["authenticated_agent_name"]
                ),
                "reason": row["reason"],
            },
        })

    for row in approval_rows:
        decision = row["decision"]

        events.append({
            "event_id": f"approval-{row['id']}",
            "org_id": row["org_id"],
            "event_type": "APPROVAL",
            "timestamp": row["timestamp"],
            "agent_name": row["agent_name"],
            "action": row["action"],
            "outcome": decision,
            "severity": (
                "MEDIUM"
                if decision == "DENIED"
                else "INFO"
            ),
            "request_id": row["request_id"],
            "actor": row["actor"],
            "summary": (
                f"{row['actor']} recorded approval "
                f"decision {decision}."
            ),
            "details": {
                "note": row["note"],
            },
        })

    for row in execution_rows:
        status = row["execution_status"]
        failed = status in (
            "FAILED",
            "DENIED",
            "BLOCKED",
        )

        events.append({
            "event_id": f"execution-{row['id']}",
            "org_id": row["org_id"],
            "event_type": "EXECUTION",
            "timestamp": row["timestamp"],
            "agent_name": row["agent_name"],
            "action": row["action"],
            "outcome": status,
            "severity": (
                "HIGH" if failed else "INFO"
            ),
            "request_id": row["request_id"],
            "actor": row["agent_name"],
            "summary": (
                f"Controlled execution finished "
                f"with status {status}."
            ),
            "details": {
                "result": decode_json_object(
                    row["result_json"]
                ),
            },
        })

    if normalized_type:
        events = [
            event
            for event in events
            if event["event_type"] == normalized_type
        ]

    if normalized_agent:
        events = [
            event
            for event in events
            if normalized_agent in str(
                event["agent_name"] or ""
            ).lower()
        ]

    events.sort(
        key=lambda event: event["timestamp"],
        reverse=True,
    )

    events = events[:safe_limit]

    return {
        "events": events,
        "count": len(events),
        "filters": {
            "event_type": normalized_type,
            "agent_name": normalized_agent,
            "limit": safe_limit,
        },
    }
