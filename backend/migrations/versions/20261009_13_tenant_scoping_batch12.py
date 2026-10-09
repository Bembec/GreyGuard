"""P2.2 batch 12: add org_id to report_schedules and incident_postmortems.

Twelfth batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks. See
backend/app/report_governance.py for the SQLite side of this same migration
(ALTER-TABLE-style imperative DDL, run from initialize_report_governance() - both sides must
stay in sync).

Both tables use UUID-generated primary keys (schedule_id, postmortem_id), so a plain backfilled
ADD COLUMN sufficed for each - no composite-key or uniqueness reshape this batch.

run_due_schedules() (report_governance.py) is a background worker with no HTTP/admin context,
the same shape as the outbound-delivery-style workers. Its claim query against report_schedules
is deliberately cross-org (one process services every org's due schedules in a single pass),
but every subsequent read or update of a claimed row is scoped by that row's own org_id, and
the generated report itself is built using that org's org_id.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_13"
down_revision = "20261009_12"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"

TABLES = ("report_schedules", "incident_postmortems")


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
