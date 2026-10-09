"""P2.2 batch 2: add org_id to adapter_events; reshape adapter_configs' primary key from
(adapter_id) to (adapter_id, org_id).

Second batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks. See
backend/app/adapter_control.py for the SQLite side of this same migration (ALTER-TABLE-style
imperative DDL, run from initialize_adapter_control() - both sides must stay in sync).

adapter_configs has the same shape problem universal_capability_controls had in batch 1: seven
fixed named rows (one per entry in adapter_control.ADAPTER_DEFINITIONS), keyed by `adapter_id`
alone. Reshaped to a composite (adapter_id, org_id) primary key, after backfilling every
existing row into the default org - see 20261009_04's docstring for the same reasoning.

abuse_protection.py's three tables (rate_limit_policies, rate_limit_counters, abuse_events)
were also evaluated this batch and deliberately reclassified as GLOBAL_TABLES rather than
migrated - see tenant_guard.py's comment for why (they are shared request-throttling
infrastructure read from a middleware that runs before any org is known, not per-resource
tenant data). No schema change for them.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_05"
down_revision = "20261009_04"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"


def upgrade():
    op.add_column("adapter_events", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE adapter_events SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("adapter_events", "org_id", nullable=False)

    op.add_column("adapter_configs", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE adapter_configs SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("adapter_configs", "org_id", nullable=False)
    op.drop_constraint("adapter_configs_pkey", "adapter_configs", type_="primary")
    op.create_primary_key("adapter_configs_pkey", "adapter_configs", ["adapter_id", "org_id"])


def downgrade():
    op.drop_constraint("adapter_configs_pkey", "adapter_configs", type_="primary")
    # Same caveat as 20261009_04's downgrade: only safe to reverse if at most one org's worth
    # of rows exists.
    op.create_primary_key("adapter_configs_pkey", "adapter_configs", ["adapter_id"])
    op.drop_column("adapter_configs", "org_id")
    op.drop_column("adapter_events", "org_id")
