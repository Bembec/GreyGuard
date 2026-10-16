"""P7.5 time ranges: per-org time indexes for the evidence lists.

The evidence lists now accept a time range (backend/app/time_range.py). tool_requests already has
(status, timestamp) indexes; audit_events and security_alerts had no time index, so a ranged read
would scan the org's whole history. The application creates the same indexes on SQLite
(database.initialize_database, alerts.initialize_alert_database), hence IF NOT EXISTS here.
"""
from alembic import op

revision = "20261016_33"
down_revision = "20261015_32"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE INDEX IF NOT EXISTS idx_audit_events_org_time ON public.audit_events (org_id, "timestamp")')
    op.execute("CREATE INDEX IF NOT EXISTS idx_alert_org_created ON public.security_alerts (org_id, created_at)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS public.idx_alert_org_created")
    op.execute("DROP INDEX IF EXISTS public.idx_audit_events_org_time")
