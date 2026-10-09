"""P2.2 batch 11: add org_id to secret_events; reshape secret_references' unique constraint
from (name) to (name, org_id).

Eleventh batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks (batches
9 and 10 were pure registry reclassifications with no schema change, so this migration's
down_revision continues directly from batch 8's). See backend/app/secret_manager.py for the
SQLite side of this same migration (ALTER-TABLE-style imperative DDL, run from
initialize_secret_manager() - both sides must stay in sync).

secret_references had the same uniqueness problem as service_accounts (batch 4) and
isolated_workspaces (batch 7): `name` was globally UNIQUE (case-insensitive, citext on
PostgreSQL), which would let two orgs collide on the same human-chosen secret name. Reshaped to
UNIQUE(name, org_id).

secret_events needed only a plain backfilled ADD COLUMN - its event_id is an AUTOINCREMENT
surrogate, not a fixed-row or uniqueness problem.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_12"
down_revision = "20261009_11"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"


def upgrade():
    op.add_column("secret_events", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE secret_events SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("secret_events", "org_id", nullable=False)

    op.add_column("secret_references", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE secret_references SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("secret_references", "org_id", nullable=False)
    op.drop_constraint("secret_references_name_key", "secret_references", type_="unique")
    op.create_unique_constraint("secret_references_name_key", "secret_references", ["name", "org_id"])


def downgrade():
    op.drop_constraint("secret_references_name_key", "secret_references", type_="unique")
    # Same caveat as prior batches' composite-key downgrades: only safe to reverse if at most
    # one org's worth of rows exists.
    op.create_unique_constraint("secret_references_name_key", "secret_references", ["name"])
    op.drop_column("secret_references", "org_id")

    op.drop_column("secret_events", "org_id")
