"""P2.2 agent scoping, batch B: add org_id to audit_events, tool_requests, approval_events and
execution_events.

See backend/app/database.py for the SQLite side of this same migration (run from
initialize_database() - both sides must stay in sync).

Every piece of evidence an agent produces belongs to that agent's org, derived from the agent's
identity at write time. Pre-existing evidence predates orgs and is backfilled to org_default.
The audit-integrity tables become install-wide (operator-only) in the same batch; that is a
registry and route change with no schema change.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_20"
down_revision = "20261010_19"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"
TABLES = ("audit_events", "tool_requests", "approval_events", "execution_events")


def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column("org_id", sa.Text(), nullable=True))
        op.execute(
            sa.text(f"UPDATE {table} SET org_id = :org_id WHERE org_id IS NULL")
            .bindparams(org_id=DEFAULT_ORG_ID)
        )
        op.alter_column(table, "org_id", nullable=False)


def downgrade():
    for table in reversed(TABLES):
        op.drop_column(table, "org_id")
