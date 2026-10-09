"""P2.2 batch 7: add org_id to quarantined_artifacts; reshape isolation_operations_config's
primary key from (config_id) to (config_id, org_id); reshape isolated_workspaces' unique
constraint from (agent_name) to (agent_name, org_id).

Seventh batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks. See
backend/app/isolation_operations.py for the SQLite side of this same migration
(ALTER-TABLE-style imperative DDL, run from initialize_isolation_operations() - both sides must
stay in sync).

isolation_operations_config is the second of the seven singleton `CHECK (config_id = 1)` tables
to land (the first was isolation_config in batch 6) - same composite-key reshape, CHECK
constraint untouched.

isolated_workspaces had its own uniqueness problem, like service_accounts in batch 4:
`agent_name` was globally UNIQUE, which would let two orgs collide on an agent of the same name.
Reshaped to UNIQUE(agent_name, org_id). This one also has a filesystem consequence the
application code addresses separately: workspace paths are now nested under an org_id
subdirectory so two orgs with the same agent name never share a directory on disk.

quarantined_artifacts needed only a plain backfilled ADD COLUMN - its artifact_id is a UUID, no
uniqueness or on-disk collision risk.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_10"
down_revision = "20261009_09"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"


def upgrade():
    op.add_column("quarantined_artifacts", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE quarantined_artifacts SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("quarantined_artifacts", "org_id", nullable=False)

    op.add_column("isolated_workspaces", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE isolated_workspaces SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("isolated_workspaces", "org_id", nullable=False)
    op.drop_constraint("isolated_workspaces_agent_name_key", "isolated_workspaces", type_="unique")
    op.create_unique_constraint("isolated_workspaces_agent_name_key", "isolated_workspaces", ["agent_name", "org_id"])

    op.add_column("isolation_operations_config", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE isolation_operations_config SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("isolation_operations_config", "org_id", nullable=False)
    op.drop_constraint("isolation_operations_config_pkey", "isolation_operations_config", type_="primary")
    op.create_primary_key("isolation_operations_config_pkey", "isolation_operations_config", ["config_id", "org_id"])


def downgrade():
    op.drop_constraint("isolation_operations_config_pkey", "isolation_operations_config", type_="primary")
    # Same caveat as prior batches' composite-key downgrades: only safe to reverse if at most
    # one org's worth of rows exists.
    op.create_primary_key("isolation_operations_config_pkey", "isolation_operations_config", ["config_id"])
    op.drop_column("isolation_operations_config", "org_id")

    op.drop_constraint("isolated_workspaces_agent_name_key", "isolated_workspaces", type_="unique")
    op.create_unique_constraint("isolated_workspaces_agent_name_key", "isolated_workspaces", ["agent_name"])
    op.drop_column("isolated_workspaces", "org_id")

    op.drop_column("quarantined_artifacts", "org_id")
