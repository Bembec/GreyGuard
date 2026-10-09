"""P2.2 batch 3: add org_id to browser_connectors, defensive_response_plans,
endpoint_collectors, and endpoint_telemetry_events.

Third batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks. See
backend/app/defensive_integrations.py and backend/app/endpoint_telemetry.py for the SQLite side
of this same migration (ALTER-TABLE-style imperative DDL, run from
initialize_defensive_integrations()/initialize_endpoint_telemetry() - both sides must stay in
sync).

Unlike batches 1 and 2, none of these four tables needed a primary-key reshape: all four are
keyed by a UUID generated at insert time (connector_id/response_id/collector_id/event_id), not a
small fixed set of named rows, so a plain backfilled ADD COLUMN is sufficient.

endpoint_telemetry_events has no live call site writing to it anywhere in the codebase today
(confirmed by search) - the column is still added for schema completeness and so the table can
leave PENDING_TENANT_SCOPING with an honest decision recorded rather than sitting in the
undecided bucket indefinitely.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_06"
down_revision = "20261009_05"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"

TABLES = (
    "browser_connectors",
    "defensive_response_plans",
    "endpoint_collectors",
    "endpoint_telemetry_events",
)


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
