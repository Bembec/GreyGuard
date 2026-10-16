"""Decision records version 3: the audit event written for the same decision.

Adds audit_event_id, so an incident derived from a policy audit event links to its request exactly
(alerts.sync_alerts_from_events). audit_events itself is not altered: a new column there would change
the content its integrity chain has already sealed. Older rows keep NULL and keep verifying against
their own version's fingerprint. Adding a column is not an UPDATE; the append-only trigger stays.
"""
from alembic import op

revision = "20261016_37"
down_revision = "20261016_36"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE public.decision_records ADD COLUMN audit_event_id bigint")
    op.execute("CREATE INDEX idx_decision_records_audit_event ON public.decision_records (org_id, audit_event_id)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS public.idx_decision_records_audit_event")
    op.execute("ALTER TABLE public.decision_records DROP COLUMN audit_event_id")
