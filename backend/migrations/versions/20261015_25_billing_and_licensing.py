"""P2.4: provider-neutral billing, billing-event evidence and self-hosted licence leases.

Creates billing_accounts (one row per org linked to a billing provider - opaque provider
references only, never card data) and billing_events (the per-org hash-chained billing evidence),
both org-scoped; and license_install, license_leases and license_events, which are install-level
(a lease covers the whole install). See backend/app/billing.py and backend/app/licensing.py for
the SQLite side of this same migration (both sides must stay in sync). The install row of
license_install is created by licensing.initialize_licensing() at startup, not here, so every
install gets its own random install_id.
"""
from alembic import op

revision = "20261015_25"
down_revision = "20261010_24"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE public.billing_accounts (
        org_id text PRIMARY KEY, provider text NOT NULL, customer_ref text NOT NULL,
        subscription_ref text NOT NULL UNIQUE, plan text NOT NULL, billing_state text NOT NULL,
        billing_email text NOT NULL, past_due_since text, grace_ends_at text,
        created_at text NOT NULL, updated_at text NOT NULL)""")
    op.execute("""CREATE TABLE public.billing_events (
        event_id bigserial PRIMARY KEY, org_id text NOT NULL, provider text NOT NULL,
        provider_event_id text NOT NULL, event_type text NOT NULL, actor text NOT NULL,
        recorded_at text NOT NULL, detail_json text NOT NULL, previous_hash text NOT NULL,
        record_hash text NOT NULL, UNIQUE (provider, provider_event_id), UNIQUE (org_id, previous_hash))""")
    op.execute("CREATE INDEX idx_billing_events_org ON billing_events (org_id, event_id)")
    op.execute("""CREATE TABLE public.license_install (
        singleton integer PRIMARY KEY CHECK (singleton = 1), install_id text NOT NULL,
        clock_high_water text NOT NULL, created_at text NOT NULL)""")
    op.execute("""CREATE TABLE public.license_leases (
        lease_id text PRIMARY KEY, licensee text NOT NULL, plan text NOT NULL, issued_at text NOT NULL,
        expires_at text NOT NULL, grace_days integer NOT NULL, token text NOT NULL,
        installed_at text NOT NULL, installed_by text NOT NULL)""")
    op.execute("""CREATE TABLE public.license_events (
        event_id bigserial PRIMARY KEY, timestamp text NOT NULL, actor text NOT NULL,
        event_type text NOT NULL, detail_json text NOT NULL)""")


def downgrade():
    op.execute("DROP TABLE license_events")
    op.execute("DROP TABLE license_leases")
    op.execute("DROP TABLE license_install")
    op.execute("DROP TABLE billing_events")
    op.execute("DROP TABLE billing_accounts")
