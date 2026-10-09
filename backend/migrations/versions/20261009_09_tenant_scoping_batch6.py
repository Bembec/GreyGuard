"""P2.2 batch 6: add org_id to isolation_executions; reshape isolation_config's primary key
from (config_id) to (config_id, org_id).

Sixth batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks. See
backend/app/execution_isolation.py for the SQLite side of this same migration
(ALTER-TABLE-style imperative DDL, run from initialize_execution_isolation() - both sides must
stay in sync).

isolation_config is the first of the seven singleton `CHECK (config_id = 1)` tables flagged in
tenant_guard.py's PENDING_TENANT_SCOPING comments to actually land. Reshaped to a composite
(config_id, org_id) primary key, the same treatment as the fixed-row-set tables in batches 1, 2
and 5 - each org gets its own config_id=1 row rather than sharing the one global row. The
existing `CHECK (config_id = 1)` constraint is untouched; it still correctly allows exactly one
row per org_id.

isolation_executions needed only a plain backfilled ADD COLUMN - its primary key is a
UUID-generated execution_id, not a fixed-row problem.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_09"
down_revision = "20261009_08"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"


def upgrade():
    op.add_column("isolation_executions", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE isolation_executions SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("isolation_executions", "org_id", nullable=False)

    op.add_column("isolation_config", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE isolation_config SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("isolation_config", "org_id", nullable=False)
    op.drop_constraint("isolation_config_pkey", "isolation_config", type_="primary")
    op.create_primary_key("isolation_config_pkey", "isolation_config", ["config_id", "org_id"])


def downgrade():
    op.drop_constraint("isolation_config_pkey", "isolation_config", type_="primary")
    # Same caveat as prior batches' composite-key downgrades: only safe to reverse if at most
    # one org's worth of rows exists.
    op.create_primary_key("isolation_config_pkey", "isolation_config", ["config_id"])
    op.drop_column("isolation_config", "org_id")
    op.drop_column("isolation_executions", "org_id")
