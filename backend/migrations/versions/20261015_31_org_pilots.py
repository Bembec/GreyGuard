"""P5: paid-pilot records (P4 decision D2) - one per org, with operator confirmations and the
conversion decision. No fee, price or payment detail is stored. See backend/app/pilots.py for the
SQLite side of this same migration.
"""
from alembic import op

revision = "20261015_31"
down_revision = "20261015_30"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE public.org_pilots (
        org_id text PRIMARY KEY, status text NOT NULL, started_at text NOT NULL, ends_at text NOT NULL,
        decision_due_at text NOT NULL, extended integer NOT NULL DEFAULT 0, confirmations_json text NOT NULL,
        created_by text NOT NULL, decided_at text, decided_by text, decision text, decision_reason text)""")


def downgrade():
    op.execute("DROP TABLE org_pilots")
