"""P3: customer-hosted gateway nodes and their event log.

Creates gateway_nodes (enrollment-token and node-credential hashes only, never the secrets) and
gateway_events, both org-scoped from creation. See backend/app/gateways.py for the SQLite side of
this same migration (both sides must stay in sync).
"""
from alembic import op

revision = "20261015_27"
down_revision = "20261015_26"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE public.gateway_nodes (
        node_id text PRIMARY KEY, org_id text NOT NULL, name text NOT NULL, status text NOT NULL,
        enrollment_token_hash text UNIQUE, enrollment_expires_at text, credential_hash text UNIQUE,
        max_offline_seconds integer NOT NULL, created_by text NOT NULL, created_at text NOT NULL,
        enrolled_at text, last_seen_at text, applied_digest text, node_version text,
        revoked_at text, revoked_by text, revoke_reason text, UNIQUE (org_id, name))""")
    op.execute("""CREATE TABLE public.gateway_events (
        event_id bigserial PRIMARY KEY, org_id text NOT NULL, node_id text NOT NULL,
        timestamp text NOT NULL, actor text NOT NULL, event_type text NOT NULL, detail_json text NOT NULL)""")
    op.execute("CREATE INDEX idx_gateway_events_org ON gateway_events (org_id, event_id)")


def downgrade():
    op.execute("DROP TABLE gateway_events")
    op.execute("DROP TABLE gateway_nodes")
