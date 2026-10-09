"""Create organizations, org_memberships and org_invitations; seed the default organization
and backfill a membership for every pre-existing administrator (P2.1).

PostgreSQL side of the pair this migration belongs to - the SQLite side is
backend/app/organizations.py's initialize_organizations(), which creates the identical three
tables via ALTER-TABLE-style imperative DDL and runs the same backfill logic. Both must stay in
sync; see that module's docstring for why one org_id column per person doesn't work (multi-org
membership) and why operational_role/governance_role are two orthogonal columns, not one.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_03"
down_revision = "20261008_02"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"
DEFAULT_ORG_NAME = "Default Organization"


def upgrade():
    op.create_table(
        "organizations",
        sa.Column("org_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="ACTIVE"),
        sa.Column("plan_id", sa.Text()),
        sa.Column("trial_ends_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text()),
    )
    op.create_table(
        "org_memberships",
        sa.Column("membership_id", sa.Text(), primary_key=True),
        sa.Column("org_id", sa.Text(), sa.ForeignKey("organizations.org_id"), nullable=False),
        sa.Column("admin_id", sa.Text(), sa.ForeignKey("administrators.admin_id"), nullable=False),
        sa.Column("operational_role", sa.Text(), nullable=False),
        sa.Column("governance_role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="ACTIVE"),
        sa.Column("invited_by", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("org_id", "admin_id"),
    )
    op.create_table(
        "org_invitations",
        sa.Column("invitation_id", sa.Text(), primary_key=True),
        sa.Column("org_id", sa.Text(), sa.ForeignKey("organizations.org_id"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("operational_role", sa.Text(), nullable=False),
        sa.Column("governance_role", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("invited_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.Text()),
        sa.Column("revoked_at", sa.Text()),
    )

    op.execute(
        sa.text(
            "INSERT INTO organizations (org_id,name,slug,status,created_at,created_by) "
            "VALUES (:org_id,:name,'default','ACTIVE',(SELECT now()::text),'system') "
            "ON CONFLICT (org_id) DO NOTHING"
        ).bindparams(org_id=DEFAULT_ORG_ID, name=DEFAULT_ORG_NAME)
    )
    # Backfill: every existing administrator becomes a member of the default org, carrying
    # their existing global role over verbatim. Nobody is auto-promoted to BILLING_ADMIN -
    # there is no billing history yet to justify it. Deterministic membership_id (not random)
    # so a re-run of this exact statement is idempotent and the result is reviewable.
    op.execute(
        sa.text(
            "INSERT INTO org_memberships "
            "(membership_id,org_id,admin_id,operational_role,governance_role,status,created_at) "
            "SELECT 'mem_' || admin_id, :org_id, admin_id, role, "
            "       CASE WHEN role = 'PLATFORM_ADMIN' THEN 'OWNER' ELSE 'MEMBER' END, "
            "       'ACTIVE', (SELECT now()::text) "
            "FROM administrators "
            "ON CONFLICT (org_id, admin_id) DO NOTHING"
        ).bindparams(org_id=DEFAULT_ORG_ID)
    )


def downgrade():
    op.drop_table("org_invitations")
    op.drop_table("org_memberships")
    op.drop_table("organizations")
