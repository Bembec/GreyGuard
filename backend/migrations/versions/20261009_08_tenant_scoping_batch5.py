"""P2.2 batch 5: add org_id to threat_register_history; reshape threat_register's primary key
from (threat_id) to (threat_id, org_id).

Fifth batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks. See
backend/app/threat_register.py for the SQLite side of this same migration (ALTER-TABLE-style
imperative DDL, run from initialize_threat_register() - both sides must stay in sync).

threat_register has the same fixed-row-set shape as universal_capability_controls and
adapter_configs in batches 1-2: 30 fixed threat_id rows seeded from the THREATS tuple, keyed by
threat_id alone. Reshaped to a composite (threat_id, org_id) primary key, after backfilling
every existing row into the default org - see 20261009_04's docstring for the same reasoning.

threat_register_history needed only a plain backfilled ADD COLUMN - its primary key is an
AUTOINCREMENT/bigint surrogate (history_id), not a fixed set of named rows.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_08"
down_revision = "20261009_07"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"


def upgrade():
    op.add_column("threat_register_history", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE threat_register_history SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("threat_register_history", "org_id", nullable=False)

    op.add_column("threat_register", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE threat_register SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("threat_register", "org_id", nullable=False)
    op.drop_constraint("threat_register_pkey", "threat_register", type_="primary")
    op.create_primary_key("threat_register_pkey", "threat_register", ["threat_id", "org_id"])


def downgrade():
    op.drop_constraint("threat_register_pkey", "threat_register", type_="primary")
    # Same caveat as prior batches' composite-key downgrades: only safe to reverse if at most
    # one org's worth of rows exists.
    op.create_primary_key("threat_register_pkey", "threat_register", ["threat_id"])
    op.drop_column("threat_register", "org_id")
    op.drop_column("threat_register_history", "org_id")
