"""GreyGuard policy versioning and change-control storage."""

import json
import sqlite3
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


def get_published_policy():
    """Return the latest published policy."""

    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM policy_versions
            WHERE status = 'PUBLISHED'
            ORDER BY version_number DESC
            LIMIT 1
            """
        ).fetchone()

    return serialize_policy(row)


def list_policy_versions():
    """Return every policy version, newest first."""

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM policy_versions
            ORDER BY version_number DESC
            """
        ).fetchall()

    return [serialize_policy(row) for row in rows]


def get_policy_version(policy_id):
    """Return one policy version or raise KeyError."""

    with connect() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM policy_versions
            WHERE policy_id = ?
            """,
            (policy_id,),
        ).fetchone()

    if row is None:
        raise KeyError("Policy version not found.")

    return serialize_policy(row)


def get_policy_history(policy_id):
    """Return the immutable change history for one policy."""

    get_policy_version(policy_id)

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
            WHERE policy_id = ?
            ORDER BY event_id DESC
            """,
            (policy_id,),
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
):
    """Append an immutable policy change event."""

    connection.execute(
        """
        INSERT INTO policy_change_events (
            policy_id,
            timestamp,
            actor,
            event_type,
            note
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            policy_id,
            utc_now(),
            actor,
            event_type,
            note,
        ),
    )


def create_policy_draft(
    permissions,
    risk_weights,
    max_blocked_attempts,
    max_risk_score,
    change_summary,
    created_by,
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

    with connect() as connection:
        active = connection.execute(
            """
            SELECT policy_id
            FROM policy_versions
            WHERE status = 'PUBLISHED'
            ORDER BY version_number DESC
            LIMIT 1
            """
        ).fetchone()

        if active is None:
            raise RuntimeError(
                "No published policy is available."
            )

        next_version = connection.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) + 1
            FROM policy_versions
            """
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
                supersedes_policy_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )

        add_policy_event(
            connection,
            policy_id,
            created_by,
            "DRAFT_CREATED",
            normalized_summary,
        )

    return get_policy_version(policy_id)


def update_policy_draft(
    policy_id,
    permissions,
    risk_weights,
    max_blocked_attempts,
    max_risk_score,
    change_summary,
    actor,
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
            WHERE policy_id = ?
            """,
            (policy_id,),
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
            WHERE policy_id = ?
            """,
            (
                json.dumps(permissions, sort_keys=True),
                json.dumps(risk_weights, sort_keys=True),
                max_blocked_attempts,
                max_risk_score,
                normalized_summary,
                policy_id,
            ),
        )

        add_policy_event(
            connection,
            policy_id,
            actor,
            "DRAFT_UPDATED",
            normalized_summary,
        )

    return get_policy_version(policy_id)


def submit_policy(policy_id, actor):
    """Freeze a draft and send it for approval."""
    with connect() as connection:
        row = connection.execute("SELECT status FROM policy_versions WHERE policy_id = ?", (policy_id,)).fetchone()
        if row is None:
            raise KeyError("Policy version not found.")
        if row["status"] != "DRAFT":
            raise ValueError("Only draft policies can be submitted.")
        connection.execute("UPDATE policy_versions SET status = 'PENDING_APPROVAL', submitted_at = ? WHERE policy_id = ?", (utc_now(), policy_id))
        add_policy_event(connection, policy_id, actor, "SUBMITTED_FOR_APPROVAL", "Policy locked pending Platform Admin review.")
    return get_policy_version(policy_id)


def approve_policy(policy_id, actor):
    """Publish an approved policy and archive the previous version."""
    timestamp = utc_now()
    with connect() as connection:
        row = connection.execute("SELECT * FROM policy_versions WHERE policy_id = ?", (policy_id,)).fetchone()
        if row is None:
            raise KeyError("Policy version not found.")
        if row["status"] != "PENDING_APPROVAL":
            raise ValueError("Only pending policies can be approved.")
        connection.execute("UPDATE policy_versions SET status = 'ARCHIVED' WHERE status = 'PUBLISHED'")
        connection.execute("UPDATE policy_versions SET status = 'PUBLISHED', approved_by = ?, approved_at = ?, published_at = ? WHERE policy_id = ?", (actor, timestamp, timestamp, policy_id))
        add_policy_event(connection, policy_id, actor, "APPROVED_AND_PUBLISHED", "Approved policy became the active enforcement version.")
    return get_policy_version(policy_id)


def reject_policy(policy_id, actor, note):
    """Reject a pending policy without affecting enforcement."""
    with connect() as connection:
        row = connection.execute("SELECT status FROM policy_versions WHERE policy_id = ?", (policy_id,)).fetchone()
        if row is None:
            raise KeyError("Policy version not found.")
        if row["status"] != "PENDING_APPROVAL":
            raise ValueError("Only pending policies can be rejected.")
        connection.execute("UPDATE policy_versions SET status = 'REJECTED' WHERE policy_id = ?", (policy_id,))
        add_policy_event(connection, policy_id, actor, "REJECTED", note.strip() or "Policy change rejected.")
    return get_policy_version(policy_id)


def create_rollback_draft(policy_id, actor):
    """Clone a historical policy into a new auditable draft."""
    source = get_policy_version(policy_id)
    return create_policy_draft(
        source["permissions"], source["risk_weights"],
        source["max_blocked_attempts"], source["max_risk_score"],
        f"Rollback to version {source['version_number']}", actor,
    )


def initialize_policy_control(
    permissions,
    risk_weights,
    max_blocked_attempts,
    max_risk_score,
):
    """Create policy tables and seed the existing policy once."""

    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS policy_versions (
                policy_id TEXT PRIMARY KEY,
                version_number INTEGER NOT NULL UNIQUE,
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
                FOREIGN KEY (supersedes_policy_id)
                    REFERENCES policy_versions(policy_id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS policy_change_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                note TEXT,
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

        existing_policy = connection.execute(
            """
            SELECT policy_id
            FROM policy_versions
            LIMIT 1
            """
        ).fetchone()

        if existing_policy is not None:
            return

        policy_id = str(uuid4())
        timestamp = utc_now()

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
                published_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy_id,
                1,
                "PUBLISHED",
                json.dumps(permissions, sort_keys=True),
                json.dumps(risk_weights, sort_keys=True),
                max_blocked_attempts,
                max_risk_score,
                (
                    "Initial policy imported from "
                    "GreyGuard's existing enforcement rules."
                ),
                "SYSTEM_MIGRATION",
                timestamp,
                "SYSTEM_MIGRATION",
                timestamp,
                timestamp,
            ),
        )

        connection.execute(
            """
            INSERT INTO policy_change_events (
                policy_id,
                timestamp,
                actor,
                event_type,
                note
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                policy_id,
                timestamp,
                "SYSTEM_MIGRATION",
                "POLICY_IMPORTED",
                (
                    "Existing GreyGuard policy stored "
                    "as the initial published version."
                ),
            ),
        )
