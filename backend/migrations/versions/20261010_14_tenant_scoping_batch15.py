"""P2.2 batch 15: add org_id to export_queue; reshape export_destinations' unique constraint
from (name) to (name, org_id).

Fifteenth batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks (batches
13 and 14 had no schema change, so this migration's down_revision continues directly from batch
12's). See backend/app/security_exports.py for the SQLite side of this same migration
(ALTER-TABLE-style imperative DDL, run from initialize_security_exports() - both sides must stay
in sync).

export_destinations had the same uniqueness problem as service_accounts (batch 4) and
secret_references (batch 11): `name` was globally UNIQUE (case-insensitive, citext on
PostgreSQL), which would let two orgs collide on the same human-chosen destination name.
Reshaped to UNIQUE(name, org_id). export_queue's foreign key references destination_id (the
primary key, unchanged), so it is unaffected by the reshape on PostgreSQL.

export_queue needed only a plain backfilled ADD COLUMN - export_id is a UUID-derived primary key.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_14"
down_revision = "20261009_13"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"


def upgrade():
    op.add_column("export_queue", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE export_queue SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("export_queue", "org_id", nullable=False)

    op.add_column("export_destinations", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE export_destinations SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("export_destinations", "org_id", nullable=False)
    op.drop_constraint("export_destinations_name_key", "export_destinations", type_="unique")
    op.create_unique_constraint("export_destinations_name_key", "export_destinations", ["name", "org_id"])


def downgrade():
    op.drop_constraint("export_destinations_name_key", "export_destinations", type_="unique")
    # Same caveat as prior batches' composite-key downgrades: only safe to reverse if at most
    # one org's worth of rows exists.
    op.create_unique_constraint("export_destinations_name_key", "export_destinations", ["name"])
    op.drop_column("export_destinations", "org_id")

    op.drop_column("export_queue", "org_id")
