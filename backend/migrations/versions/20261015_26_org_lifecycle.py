"""P2.5: organization lifecycle - offboarding records, the lifecycle log and audit erasures.

Creates org_offboarding and org_lifecycle_events (install-level: they describe an org and must
outlive its deletion) and audit_integrity_erasures (install-level: which sealed audit events an
authorized deletion - retention or organization deletion - removed, so the install-wide integrity
chain still verifies). See backend/app/org_lifecycle.py and backend/app/audit_integrity.py for
the SQLite side of this same migration (both sides must stay in sync).
"""
from alembic import op

revision = "20261015_26"
down_revision = "20261015_25"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE public.org_offboarding (
        org_id text PRIMARY KEY, started_at text NOT NULL, started_by text NOT NULL, reason text NOT NULL,
        deletion_eligible_at text NOT NULL, actions_json text NOT NULL)""")
    op.execute("""CREATE TABLE public.org_lifecycle_events (
        event_id bigserial PRIMARY KEY, org_id text NOT NULL, timestamp text NOT NULL,
        actor text NOT NULL, event_type text NOT NULL, detail_json text NOT NULL)""")
    op.execute("CREATE INDEX idx_org_lifecycle_events_org ON org_lifecycle_events (org_id, event_id)")
    op.execute("""CREATE TABLE public.audit_integrity_erasures (
        source_table text NOT NULL, source_id text NOT NULL, erased_at text NOT NULL,
        erased_by text NOT NULL, reason text NOT NULL, PRIMARY KEY (source_table, source_id))""")


def downgrade():
    op.execute("DROP TABLE audit_integrity_erasures")
    op.execute("DROP TABLE org_lifecycle_events")
    op.execute("DROP TABLE org_offboarding")
