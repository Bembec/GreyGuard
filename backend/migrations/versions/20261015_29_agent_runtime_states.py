"""P3 HA: agent runtime state moves from per-process memory into the database.

Creates agent_runtime_states (org-scoped). Existing state in the backend's state file is imported
at startup by main.initialize_greyguard() without overwriting anything already in the table. See
backend/app/database.py for the SQLite side of this same migration.
"""
from alembic import op

revision = "20261015_29"
down_revision = "20261015_28"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE public.agent_runtime_states (
        agent_name text PRIMARY KEY, org_id text NOT NULL DEFAULT 'org_default',
        agent_status text NOT NULL DEFAULT 'ACTIVE', risk_score integer NOT NULL DEFAULT 0,
        blocked_attempts integer NOT NULL DEFAULT 0, updated_at text NOT NULL)""")
    op.execute("CREATE INDEX idx_agent_runtime_states_org ON agent_runtime_states (org_id)")


def downgrade():
    op.execute("DROP TABLE agent_runtime_states")
