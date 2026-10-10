"""P2.2 final batch: add org_id to compliance_reports, expiring_approval_links and
callback_evidence - the last tables in tenant_guard.PENDING_TENANT_SCOPING.

See backend/app/compliance_reports.py and backend/app/incident_integrations.py for the SQLite side
of this same migration (both sides must stay in sync). Everything that predates orgs belongs to
org_default.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_23"
down_revision = "20261010_22"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"
TABLES = ("compliance_reports", "expiring_approval_links", "callback_evidence")


def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column("org_id", sa.Text(), nullable=True,
                                       server_default=sa.text(f"'{DEFAULT_ORG_ID}'")))
        op.execute(
            sa.text(f"UPDATE {table} SET org_id = :org_id WHERE org_id IS NULL")
            .bindparams(org_id=DEFAULT_ORG_ID)
        )
        op.alter_column(table, "org_id", nullable=False)


def downgrade():
    for table in reversed(TABLES):
        op.drop_column(table, "org_id")
