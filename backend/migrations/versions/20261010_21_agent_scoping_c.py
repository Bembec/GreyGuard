"""P2.2 agent scoping, batch C: org-scope alerts, alert notes, notifications and notification
retention.

See backend/app/alerts.py and backend/app/notifications.py for the SQLite side of this same
migration (both sides must stay in sync).

security_alerts, alert_notes, security_notifications, notification_retention_events and
notification_retention_tombstones gain a deliberately NULLABLE org_id: NULL marks install-level
records derived from evidence that belongs to no tenant (visible only to install operators).
Everything that predates orgs is backfilled to org_default.

notification_retention_policy was a singleton (PK id, CHECK id = 1); it is reshaped to a
composite (id, org_id) primary key so each org holds its own policy, as simulation_config was in
batch 8.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_21"
down_revision = "20261010_20"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"
NULLABLE_TABLES = (
    "security_alerts",
    "alert_notes",
    "security_notifications",
    "notification_retention_events",
    "notification_retention_tombstones",
)


def _backfill(table):
    op.execute(
        sa.text(f"UPDATE {table} SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )


def upgrade():
    for table in NULLABLE_TABLES:
        op.add_column(table, sa.Column("org_id", sa.Text(), nullable=True))
        _backfill(table)

    op.add_column("notification_retention_policy", sa.Column(
        "org_id", sa.Text(), nullable=True, server_default=sa.text(f"'{DEFAULT_ORG_ID}'")))
    _backfill("notification_retention_policy")
    op.alter_column("notification_retention_policy", "org_id", nullable=False)
    op.drop_constraint("notification_retention_policy_pkey", "notification_retention_policy", type_="primary")
    op.create_primary_key("notification_retention_policy_pkey", "notification_retention_policy", ["id", "org_id"])


def downgrade():
    op.drop_constraint("notification_retention_policy_pkey", "notification_retention_policy", type_="primary")
    # Same caveat as prior batches' composite-key downgrades: only safe to reverse if at most one
    # org's worth of rows exists.
    op.create_primary_key("notification_retention_policy_pkey", "notification_retention_policy", ["id"])
    op.drop_column("notification_retention_policy", "org_id")
    for table in reversed(NULLABLE_TABLES):
        op.drop_column(table, "org_id")
