"""P2.2 batch 17: add org_id to external_incident_records; reshape incident_destinations' unique
constraint from (name) to (name, org_id).

Seventeenth batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks. See
backend/app/incident_integrations.py for the SQLite side of this same migration (imperative DDL
run from initialize_incident_integrations() - both sides must stay in sync).

incident_destinations had a globally UNIQUE `name` (citext), which would let two orgs collide on
the same human-chosen destination name - the same problem as export_destinations (batch 15) and
notification_destinations (batch 16).

external_incident_records needed only a plain backfilled ADD COLUMN - its existing
UNIQUE(destination_id, source_alert_id) is already effectively per-org, since destination_ids are
random and each belongs to exactly one org.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_16"
down_revision = "20261010_15"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"


def _add_org_id(table):
    op.add_column(table, sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text(f"UPDATE {table} SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column(table, "org_id", nullable=False)


def upgrade():
    _add_org_id("external_incident_records")
    _add_org_id("incident_destinations")
    op.drop_constraint("incident_destinations_name_key", "incident_destinations", type_="unique")
    op.create_unique_constraint("incident_destinations_name_key", "incident_destinations", ["name", "org_id"])


def downgrade():
    op.drop_constraint("incident_destinations_name_key", "incident_destinations", type_="unique")
    # Same caveat as prior batches' composite-key downgrades: only safe to reverse if at most one
    # org's worth of rows exists.
    op.create_unique_constraint("incident_destinations_name_key", "incident_destinations", ["name"])
    op.drop_column("incident_destinations", "org_id")
    op.drop_column("external_incident_records", "org_id")
