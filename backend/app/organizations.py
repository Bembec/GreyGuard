"""Organizations, membership, invitations, and the active-org session concept (P2.1).

An administrator account represents a person, not an org membership - one person can belong to
several organizations (Michael's explicit decision), so org_id cannot live on `administrators`
itself. Membership (who belongs to which org, with what role) lives in `org_memberships`; which
org a given session is currently acting as lives on `administrator_sessions.active_org_id`
(admin_auth.py), switchable without re-authenticating via switch_active_org().

Two orthogonal roles per membership, not a collapsed enum:
- operational_role: PLATFORM_ADMIN / SECURITY_ANALYST / AUDITOR - the existing ROLES enum from
  admin_auth.py, unchanged. Governs what a person can DO inside the security product.
- governance_role: OWNER / BILLING_ADMIN / MEMBER - new. Governs whether a person can manage the
  org itself: membership, invitations, billing. Only OWNER can invite/remove/change members in
  this sub-phase (billing-admin-specific actions arrive with billing in a later sub-phase).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from . import admin_auth
from . import db_compat as sqlite3
from .database import database_path as greyguard_database_path

database_path = greyguard_database_path

DEFAULT_ORG_ID = "org_default"
DEFAULT_ORG_NAME = "Default Organization"
GOVERNANCE_ROLES = {"OWNER", "BILLING_ADMIN", "MEMBER"}
INVITATION_DAYS = 7


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_tables(connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            org_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            plan_id TEXT,
            trial_ends_at TEXT,
            created_at TEXT NOT NULL,
            created_by TEXT
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS org_memberships (
            membership_id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL REFERENCES organizations(org_id),
            admin_id TEXT NOT NULL REFERENCES administrators(admin_id),
            operational_role TEXT NOT NULL,
            governance_role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            invited_by TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(org_id, admin_id)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS org_invitations (
            invitation_id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL REFERENCES organizations(org_id),
            email TEXT NOT NULL,
            operational_role TEXT NOT NULL,
            governance_role TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            invited_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            accepted_at TEXT,
            revoked_at TEXT
        )
    """)


def _ensure_schema() -> None:
    """Cheap, idempotent table-creation only - no default-org seed, no backfill. Called
    defensively from every read/write path below, mirroring admin_auth.count_administrators()'s
    own defensive self-init pattern: a test fixture (or any other caller) that only calls
    admin_auth.initialize_admin_auth() directly, bypassing this module's own
    initialize_organizations(), must not crash with "no such table" the moment it issues a
    session - every login goes through _issue_session() -> resolve_initial_active_org_id() ->
    list_memberships_for_admin() below.

    Deliberately not cached process-wide (unlike db_compat.py's _ensure_extensions): tests
    repoint `database_path` to a fresh SQLite file per test function, so "the schema already
    exists" is a fact about one specific file, not the process - a process-wide flag would
    skip real table creation for every file after the first and break with "no such table"
    exactly as this function exists to prevent. CREATE TABLE IF NOT EXISTS is cheap enough to
    run on every call; production's real cost (once per request, via the auth hot path) is a
    handful of no-op existence checks.
    """
    with sqlite3.connect(database_path) as connection:
        _create_tables(connection)


def initialize_organizations() -> None:
    """Create organization/membership/invitation tables, seed the default org, and backfill a
    membership for every pre-existing administrator. Idempotent: safe to call on every startup.

    Defensively calls initialize_admin_auth() first - lifespan() does not reliably call it
    (admin_auth.count_administrators() has the same defensive call for the same reason), and
    this module's backfill query joins against `administrators`.
    """
    admin_auth.initialize_admin_auth()
    with sqlite3.connect(database_path) as connection:
        _create_tables(connection)
        connection.execute(
            "INSERT OR IGNORE INTO organizations (org_id,name,slug,status,created_at,created_by) "
            "VALUES (?,?,?,?,?,?)",
            (DEFAULT_ORG_ID, DEFAULT_ORG_NAME, "default", "ACTIVE", utc_now(), "system"),
        )
        # Backfill: every existing administrator who isn't already a member of any org becomes a
        # member of the default org, carrying their existing global role over verbatim. Nobody is
        # auto-promoted to BILLING_ADMIN - there is no billing history yet to justify it.
        connection.row_factory = sqlite3.Row
        unmigrated = connection.execute("""
            SELECT admin_id, role FROM administrators
            WHERE admin_id NOT IN (SELECT admin_id FROM org_memberships)
        """).fetchall()
        for row in unmigrated:
            governance_role = "OWNER" if row["role"] == "PLATFORM_ADMIN" else "MEMBER"
            connection.execute(
                "INSERT INTO org_memberships "
                "(membership_id,org_id,admin_id,operational_role,governance_role,status,created_at) "
                "VALUES (?,?,?,?,?,'ACTIVE',?)",
                ("mem_" + secrets.token_hex(12), DEFAULT_ORG_ID, row["admin_id"],
                 row["role"], governance_role, utc_now()),
            )


def create_organization(name: str, created_by_admin_id: str, slug: str | None = None) -> dict:
    """Create a new organization and make the creator its OWNER. Any authenticated
    administrator may create an org - this is how a real signup flow would start one."""
    _ensure_schema()
    normalized_name = str(name).strip()
    if not normalized_name:
        raise ValueError("Organization name is required.")
    normalized_slug = (slug or normalized_name).strip().lower().replace(" ", "-")
    org_id = "org_" + secrets.token_hex(12)
    with sqlite3.connect(database_path) as connection:
        try:
            connection.execute(
                "INSERT INTO organizations (org_id,name,slug,status,created_at,created_by) "
                "VALUES (?,?,?,'ACTIVE',?,?)",
                (org_id, normalized_name, normalized_slug, utc_now(), created_by_admin_id),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("An organization with this slug already exists.") from error
        connection.execute(
            "INSERT INTO org_memberships "
            "(membership_id,org_id,admin_id,operational_role,governance_role,status,created_at) "
            "VALUES (?,?,?,'PLATFORM_ADMIN','OWNER','ACTIVE',?)",
            ("mem_" + secrets.token_hex(12), org_id, created_by_admin_id, utc_now()),
        )
    return get_organization(org_id)


def get_organization(org_id: str) -> dict:
    _ensure_schema()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM organizations WHERE org_id = ?", (org_id,)
        ).fetchone()
    if not row:
        raise KeyError("Organization not found.")
    return dict(row)


def list_memberships_for_admin(admin_id: str) -> list[dict]:
    """Every organization this administrator belongs to, for the frontend's org switcher."""
    _ensure_schema()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT m.org_id, o.name AS org_name, m.operational_role, m.governance_role,
                   m.status, m.created_at
            FROM org_memberships m JOIN organizations o ON o.org_id = m.org_id
            WHERE m.admin_id = ? AND m.status = 'ACTIVE'
            ORDER BY m.created_at
        """, (admin_id,)).fetchall()
    return [dict(row) for row in rows]


def get_membership(org_id: str, admin_id: str) -> dict | None:
    _ensure_schema()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM org_memberships WHERE org_id = ? AND admin_id = ? AND status = 'ACTIVE'",
            (org_id, admin_id),
        ).fetchone()
    return dict(row) if row else None


def apply_identity_context(administrator: dict, admin_id: str, active_org_id: str | None) -> dict:
    """Overlays org/membership context onto an already-built administrator dict (the one
    admin_auth._public_admin() returns), called from admin_auth.validate_session().

    Deliberately permissive, not a hard dependency: an administrator with zero memberships
    (every pre-P2.1 test fixture that calls create_administrator() directly, bypassing
    setup_first_administrator/provision_sso_administrator) keeps working exactly as before -
    administrator["role"] stays whatever _public_admin() already set from administrators.role,
    and organizations/active_org come back empty/None. Only when a resolvable membership exists
    does its operational_role/governance_role override the dict - every existing permission
    check (has_permission/required_permission/require_policy_editor/require_platform_admin) only
    ever reads administrator["role"], so this is the single place tenancy enters the auth chain.
    """
    memberships = list_memberships_for_admin(admin_id)
    administrator["organizations"] = memberships
    active = next((item for item in memberships if item["org_id"] == active_org_id), None)
    if active is None:
        administrator["active_org_id"] = None
        administrator["active_org_name"] = None
        administrator["governance_role"] = None
        return administrator
    administrator["role"] = active["operational_role"]
    administrator["permissions"] = sorted(admin_auth.ROLES.get(active["operational_role"], set()))
    administrator["governance_role"] = active["governance_role"]
    administrator["active_org_id"] = active["org_id"]
    administrator["active_org_name"] = active["org_name"]
    return administrator


def resolve_initial_active_org_id(admin_id: str) -> str | None:
    """Picks the default active org for a brand-new session: the earliest membership, or None
    if the administrator belongs to no organization yet."""
    memberships = list_memberships_for_admin(admin_id)
    return memberships[0]["org_id"] if memberships else None


def switch_active_org(admin_id: str, org_id: str, token_hash: str) -> None:
    """Switch which org a session acts as, without re-authenticating. The caller (api.py) has
    already resolved `admin_id` from the session; this only needs to confirm that admin still
    holds an active membership in the requested org before honouring the switch."""
    if get_membership(org_id, admin_id) is None:
        raise PermissionError("You are not a member of that organization.")
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            "UPDATE administrator_sessions SET active_org_id = ? WHERE token_hash = ?",
            (org_id, token_hash),
        )
    if cursor.rowcount == 0:
        raise ValueError("Administrator session is invalid.")


def list_members(org_id: str) -> list[dict]:
    _ensure_schema()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT m.admin_id, a.email, a.display_name, m.operational_role, m.governance_role,
                   m.status, m.created_at
            FROM org_memberships m JOIN administrators a ON a.admin_id = m.admin_id
            WHERE m.org_id = ? ORDER BY m.created_at
        """, (org_id,)).fetchall()
    return [dict(row) for row in rows]


def ensure_membership(org_id: str, admin_id: str, operational_role: str, governance_role: str,
                       invited_by: str | None = None) -> dict:
    """Idempotent: used by setup_first_administrator, provision_sso_administrator and the
    team-management "create administrator" route, each of which must guarantee the person they
    just created has at least one org membership - otherwise they have no resolvable role on
    their next login (see apply_identity_context's fallback behavior above)."""
    _ensure_schema()
    if operational_role not in admin_auth.ROLES:
        raise ValueError("Unknown operational role.")
    if governance_role not in GOVERNANCE_ROLES:
        raise ValueError("Unknown governance role.")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO org_memberships "
            "(membership_id,org_id,admin_id,operational_role,governance_role,status,invited_by,created_at) "
            "VALUES (?,?,?,?,?,'ACTIVE',?,?)",
            ("mem_" + secrets.token_hex(12), org_id, admin_id, operational_role, governance_role,
             invited_by, utc_now()),
        )
    return get_membership(org_id, admin_id)


def sync_operational_role(org_id: str, admin_id: str, operational_role: str) -> None:
    """Keeps a membership's operational_role in step with an external role change - used by
    provision_sso_administrator() when a provider's role mapping changes an existing SSO
    administrator's role on a later login. No-op if no membership row exists yet."""
    _ensure_schema()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE org_memberships SET operational_role = ? WHERE org_id = ? AND admin_id = ?",
            (operational_role, org_id, admin_id),
        )


def _require_owner(org_id: str, actor_admin_id: str) -> None:
    membership = get_membership(org_id, actor_admin_id)
    if not membership or membership["governance_role"] != "OWNER":
        raise PermissionError("Organization owner access is required.")


def _active_owner_count(connection, org_id: str) -> int:
    return connection.execute(
        "SELECT COUNT(*) FROM org_memberships WHERE org_id = ? AND governance_role = 'OWNER' AND status = 'ACTIVE'",
        (org_id,),
    ).fetchone()[0]


def create_invitation(org_id: str, email: str, operational_role: str, governance_role: str,
                       invited_by_admin_id: str) -> dict:
    _require_owner(org_id, invited_by_admin_id)
    if operational_role not in admin_auth.ROLES:
        raise ValueError("Unknown operational role.")
    if governance_role not in GOVERNANCE_ROLES:
        raise ValueError("Unknown governance role.")
    normalized_email = str(email).strip().lower()
    if "@" not in normalized_email:
        raise ValueError("A valid email is required.")
    token = "orgi_" + secrets.token_urlsafe(32)
    invitation_id = "inv_" + secrets.token_hex(12)
    created = datetime.now(timezone.utc)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO org_invitations "
            "(invitation_id,org_id,email,operational_role,governance_role,token_hash,invited_by,"
            " created_at,expires_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (invitation_id, org_id, normalized_email, operational_role, governance_role,
             hashlib.sha256(token.encode()).hexdigest(), invited_by_admin_id,
             created.isoformat(), (created + timedelta(days=INVITATION_DAYS)).isoformat()),
        )
    return {"invitation_id": invitation_id, "token": token, "email": normalized_email,
            "expires_at": (created + timedelta(days=INVITATION_DAYS)).isoformat()}


def accept_invitation(token: str, admin_id: str, admin_email: str) -> dict:
    """An invitation is scoped to the email address it was sent to - the accepting
    administrator's own account email must match, so one person can't redeem an invitation
    meant for someone else's inbox."""
    _ensure_schema()
    if not token or not token.startswith("orgi_"):
        raise ValueError("Invitation token is invalid.")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM org_invitations WHERE token_hash = ?", (token_hash,)
        ).fetchone()
        if not row:
            raise ValueError("Invitation not found.")
        if row["revoked_at"]:
            raise ValueError("This invitation has been revoked.")
        if row["accepted_at"]:
            raise ValueError("This invitation has already been accepted.")
        if row["expires_at"] <= utc_now():
            raise ValueError("This invitation has expired.")
        if row["email"] != str(admin_email).strip().lower():
            raise PermissionError("This invitation was issued to a different email address.")
        connection.execute(
            "INSERT OR IGNORE INTO org_memberships "
            "(membership_id,org_id,admin_id,operational_role,governance_role,status,invited_by,created_at) "
            "VALUES (?,?,?,?,?,'ACTIVE',?,?)",
            ("mem_" + secrets.token_hex(12), row["org_id"], admin_id, row["operational_role"],
             row["governance_role"], row["invited_by"], utc_now()),
        )
        connection.execute(
            "UPDATE org_invitations SET accepted_at = ? WHERE invitation_id = ?",
            (utc_now(), row["invitation_id"]),
        )
    return get_membership(row["org_id"], admin_id)


def revoke_invitation(org_id: str, invitation_id: str, actor_admin_id: str) -> None:
    _require_owner(org_id, actor_admin_id)
    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            "UPDATE org_invitations SET revoked_at = ? "
            "WHERE invitation_id = ? AND org_id = ? AND accepted_at IS NULL AND revoked_at IS NULL",
            (utc_now(), invitation_id, org_id),
        )
    if cursor.rowcount == 0:
        raise KeyError("Invitation not found or already resolved.")


def update_membership(org_id: str, admin_id: str, actor_admin_id: str,
                       operational_role: str | None = None, governance_role: str | None = None) -> dict:
    _require_owner(org_id, actor_admin_id)
    membership = get_membership(org_id, admin_id)
    if not membership:
        raise KeyError("Membership not found.")
    resulting_operational = operational_role or membership["operational_role"]
    resulting_governance = governance_role or membership["governance_role"]
    if resulting_operational not in admin_auth.ROLES:
        raise ValueError("Unknown operational role.")
    if resulting_governance not in GOVERNANCE_ROLES:
        raise ValueError("Unknown governance role.")
    with sqlite3.connect(database_path) as connection:
        removes_last_owner = (
            membership["governance_role"] == "OWNER" and resulting_governance != "OWNER"
            and _active_owner_count(connection, org_id) <= 1
        )
        if removes_last_owner:
            raise ValueError("The final owner of an organization cannot be demoted.")
        connection.execute(
            "UPDATE org_memberships SET operational_role = ?, governance_role = ? "
            "WHERE org_id = ? AND admin_id = ?",
            (resulting_operational, resulting_governance, org_id, admin_id),
        )
    return get_membership(org_id, admin_id)


def remove_membership(org_id: str, admin_id: str, actor_admin_id: str) -> None:
    _require_owner(org_id, actor_admin_id)
    membership = get_membership(org_id, admin_id)
    if not membership:
        raise KeyError("Membership not found.")
    with sqlite3.connect(database_path) as connection:
        if membership["governance_role"] == "OWNER" and _active_owner_count(connection, org_id) <= 1:
            raise ValueError("The final owner of an organization cannot be removed.")
        connection.execute(
            "UPDATE org_memberships SET status = 'REMOVED' WHERE org_id = ? AND admin_id = ?",
            (org_id, admin_id),
        )
