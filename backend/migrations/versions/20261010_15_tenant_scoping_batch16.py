"""P2.2 batch 16: add org_id to notification_deliveries; reshape notification_destinations' and
notification_templates' unique constraints from (name) to (name, org_id).

Sixteenth batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks. See
backend/app/notification_delivery.py for the SQLite side of this same migration (imperative DDL
run from initialize_notification_delivery() - both sides must stay in sync).

Both config tables had a globally UNIQUE `name` (citext for destinations, plain text for
templates), which would let two orgs collide on the same human-chosen name - the same problem
as service_accounts (batch 4), secret_references (batch 11) and export_destinations (batch 15).

notification_deliveries needed only a plain backfilled ADD COLUMN - its existing
UNIQUE(destination_id, dedupe_key) is already effectively per-org, since destination_ids are
random and each belongs to exactly one org.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_15"
down_revision = "20261010_14"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"

RESHAPED = ("notification_destinations", "notification_templates")


def _add_org_id(table):
    op.add_column(table, sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text(f"UPDATE {table} SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column(table, "org_id", nullable=False)


def upgrade():
    _add_org_id("notification_deliveries")
    for table in RESHAPED:
        _add_org_id(table)
        op.drop_constraint(f"{table}_name_key", table, type_="unique")
        op.create_unique_constraint(f"{table}_name_key", table, ["name", "org_id"])


def downgrade():
    for table in reversed(RESHAPED):
        op.drop_constraint(f"{table}_name_key", table, type_="unique")
        # Same caveat as prior batches' composite-key downgrades: only safe to reverse if at
        # most one org's worth of rows exists.
        op.create_unique_constraint(f"{table}_name_key", table, ["name"])
        op.drop_column(table, "org_id")
    op.drop_column("notification_deliveries", "org_id")
