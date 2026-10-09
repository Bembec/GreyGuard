"""P2.2 batch 8: reshape simulation_config's primary key from (config_id) to
(config_id, org_id).

Eighth batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks. See
backend/app/adversarial_simulations.py for the SQLite side of this same migration
(ALTER-TABLE-style imperative DDL, run from initialize_simulations() - both sides must stay in
sync).

simulation_config is the third of the seven singleton `CHECK (config_id = 1)` tables to land
(after isolation_config in batch 6 and isolation_operations_config in batch 7) - same
composite-key reshape, CHECK constraint untouched. This is also the table explicitly deferred
back in batch 1 when simulation_runs was scoped (see that migration's docstring) - the one
remaining call site that still updated a simulations table without an org_id
(update_simulation_lab() in api.py) is fixed in the same commit as this migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_11"
down_revision = "20261009_10"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"


def upgrade():
    op.add_column("simulation_config", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE simulation_config SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("simulation_config", "org_id", nullable=False)
    op.drop_constraint("simulation_config_pkey", "simulation_config", type_="primary")
    op.create_primary_key("simulation_config_pkey", "simulation_config", ["config_id", "org_id"])


def downgrade():
    op.drop_constraint("simulation_config_pkey", "simulation_config", type_="primary")
    # Same caveat as prior batches' composite-key downgrades: only safe to reverse if at most
    # one org's worth of rows exists.
    op.create_primary_key("simulation_config_pkey", "simulation_config", ["config_id"])
    op.drop_column("simulation_config", "org_id")
