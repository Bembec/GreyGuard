"""Decision records version 2: how the agent authenticated (owner decision, 2026-10-16).

Adds authentication_method (AGENT_KEY, CLIENT_CERTIFICATE or NOT_RECORDED) for new records. Version-1
rows keep NULL and keep verifying against their version-1 fingerprint. Adding a column is not an
UPDATE, so the append-only trigger is unaffected and stays in force.
"""
from alembic import op

revision = "20261016_35"
down_revision = "20261016_34"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE public.decision_records ADD COLUMN authentication_method text")


def downgrade():
    op.execute("ALTER TABLE public.decision_records DROP COLUMN authentication_method")
