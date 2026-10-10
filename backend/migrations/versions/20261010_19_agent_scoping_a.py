"""P2.2 agent scoping, batch A: add org_id to agent_identities and agent_credential_events.

See backend/app/database.py for the SQLite side of this same migration (run from
initialize_database() - both sides must stay in sync).

agent_name stays the primary key of agent_identities: agent names are a global namespace, like
administrator emails, because an agent authenticates by name before any org can be resolved.
Its org is a property of its identity. Pre-existing agents predate orgs and are backfilled to
org_default.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_19"
down_revision = "20261010_18"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"
TABLES = ("agent_identities", "agent_credential_events")


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
