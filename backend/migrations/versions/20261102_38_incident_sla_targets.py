"""P7.5 investigation workspace, step 4: incident response targets (SLA) per organization.

One row per org and severity (backend/app/incident_sla.py). No rows means "No SLA set": there are
no defaults (owner decision 2, 2026-10-16). Org-scoped and registered with the tenant guard.
"""
from alembic import op

revision = "20261102_38"
down_revision = "20261016_37"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE public.incident_sla_targets (
            org_id text NOT NULL,
            severity text NOT NULL,
            acknowledge_minutes integer,
            resolve_minutes integer,
            updated_by text NOT NULL,
            updated_at text NOT NULL,
            PRIMARY KEY (org_id, severity),
            CHECK (severity IN ('CRITICAL', 'HIGH')),
            CHECK (acknowledge_minutes IS NULL OR acknowledge_minutes BETWEEN 1 AND 525600),
            CHECK (resolve_minutes IS NULL OR resolve_minutes BETWEEN 1 AND 525600),
            CHECK (acknowledge_minutes IS NOT NULL OR resolve_minutes IS NOT NULL)
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS public.incident_sla_targets")
