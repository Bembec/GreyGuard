"""P3: public status page - incidents, incident updates and maintenance windows.

Install-level tables: they describe the operated service, never a tenant. See
backend/app/service_status.py for the SQLite side of this same migration.
"""
from alembic import op

revision = "20261015_28"
down_revision = "20261015_27"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE public.status_incidents (
        incident_id text PRIMARY KEY, title text NOT NULL, severity text NOT NULL, components_json text NOT NULL,
        state text NOT NULL, started_at text NOT NULL, acknowledged_at text, resolved_at text,
        created_by text NOT NULL)""")
    op.execute("""CREATE TABLE public.status_incident_updates (
        update_id bigserial PRIMARY KEY, incident_id text NOT NULL, timestamp text NOT NULL,
        state text NOT NULL, message text NOT NULL, author text NOT NULL)""")
    op.execute("""CREATE TABLE public.status_maintenance (
        maintenance_id text PRIMARY KEY, title text NOT NULL, components_json text NOT NULL,
        starts_at text NOT NULL, ends_at text NOT NULL, message text NOT NULL, created_by text NOT NULL,
        created_at text NOT NULL, cancelled_at text)""")


def downgrade():
    op.execute("DROP TABLE status_maintenance")
    op.execute("DROP TABLE status_incident_updates")
    op.execute("DROP TABLE status_incidents")
