import json
import sqlite3
from pathlib import Path


database_path = (
    Path(__file__).parent / "greyguard.db"
)


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
                blocked_attempts INTEGER NOT NULL
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
                revoked_at TEXT
            )
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
                blocked_attempts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )


def get_recent_audit_events(
    agent_name,
    limit=5,
):
    """Return recent events for one agent."""

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
            WHERE agent_name = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                agent_name,
                limit,
            ),
        )

        return cursor.fetchall()


def get_audit_summary(agent_name):
    """Return audit statistics for one agent."""

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
            WHERE agent_name = ?
            """,
            (agent_name,),
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
                    revoked_at
                )
                VALUES (?, ?, ?, ?, 'ACTIVE', ?, NULL, NULL)
                """,
                (
                    agent_name,
                    credential_salt,
                    credential_hash,
                    scopes_json,
                    timestamp,
                ),
            )

    except sqlite3.IntegrityError:
        return False

    return True


def get_agent_identity(agent_name):
    """Return one stored agent identity."""

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT
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


def get_agent_identities():
    """Return all identities without credential data."""

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
            ORDER BY agent_name
            """
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
            WHERE agent_name = ?
            """,
            (
                scopes_json,
                agent_name,
            ),
        )

        return cursor.rowcount > 0


def rotate_agent_credential(
    agent_name,
    credential_salt,
    credential_hash,
    timestamp,
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
            WHERE agent_name = ?
            """,
            (
                credential_salt,
                credential_hash,
                timestamp,
                agent_name,
            ),
        )

        return cursor.rowcount > 0


def revoke_agent_credential(
    agent_name,
    timestamp,
):
    """Revoke an agent credential."""

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE agent_identities
            SET
                credential_status = 'REVOKED',
                revoked_at = ?
            WHERE agent_name = ?
            """,
            (
                timestamp,
                agent_name,
            ),
        )

        return cursor.rowcount > 0


def save_authentication_event(
    timestamp,
    claimed_agent_name,
    authenticated_agent_name,
    action,
    outcome,
    reason,
):
    """Save an identity-authentication event."""

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


if __name__ == "__main__":
    initialize_database()

    print(
        "GreyGuard V9 database initialized:"
    )
    print(database_path)