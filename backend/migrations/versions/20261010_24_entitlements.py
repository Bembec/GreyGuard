"""P2.3: plans, entitlements, trials and overrides.

Creates org_entitlements (one row per org that has been assigned a plan - an org without a row
is UNASSIGNED and nothing is enforced), entitlement_overrides and entitlement_events. See
backend/app/entitlements.py for the SQLite side of this same migration (both sides must stay in
sync). The plan catalogue and meters live in code; only assignments, overrides and their audit
trail are stored.
"""
from alembic import op

revision = "20261010_24"
down_revision = "20261010_23"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE public.org_entitlements (
        org_id text PRIMARY KEY, plan text NOT NULL, status text NOT NULL,
        trial_ends_at text, updated_by text NOT NULL, updated_at text NOT NULL)""")
    op.execute("""CREATE TABLE public.entitlement_overrides (
        override_id text PRIMARY KEY, org_id text NOT NULL, override_key text NOT NULL,
        value_json text NOT NULL, reason text NOT NULL, created_by text NOT NULL,
        created_at text NOT NULL, expires_at text, revoked_at text, revoked_by text)""")
    op.execute("""CREATE TABLE public.entitlement_events (
        event_id bigserial PRIMARY KEY, org_id text NOT NULL, timestamp text NOT NULL,
        actor text NOT NULL, event_type text NOT NULL, detail_json text NOT NULL)""")
    op.execute("CREATE INDEX idx_entitlement_overrides_org ON entitlement_overrides (org_id)")
    op.execute("CREATE INDEX idx_entitlement_events_org ON entitlement_events (org_id, event_id)")


def downgrade():
    op.execute("DROP TABLE entitlement_events")
    op.execute("DROP TABLE entitlement_overrides")
    op.execute("DROP TABLE org_entitlements")
