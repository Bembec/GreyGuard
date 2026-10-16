"""P7.5 investigation workspace: the full action record of each incident.

One row per status change, assignment, note, containment action and export
(backend/app/alerts.record_incident_event). Append-only: the trigger refuses every UPDATE; DELETE
stays possible for organization deletion. org_id is nullable exactly as security_alerts.org_id is:
NULL belongs to an install-level incident.
"""
from alembic import op

revision = "20261016_36"
down_revision = "20261016_35"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE public.incident_events (
            id bigserial PRIMARY KEY,
            alert_id text NOT NULL,
            org_id text,
            "timestamp" text NOT NULL,
            actor text NOT NULL,
            event_type text NOT NULL,
            detail_json text NOT NULL
        )
    """)
    op.execute("CREATE INDEX idx_incident_events_alert ON public.incident_events (org_id, alert_id, id)")
    op.execute("""
        CREATE FUNCTION public.incident_events_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'incident events are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER incident_events_append_only
        BEFORE UPDATE ON public.incident_events
        FOR EACH ROW EXECUTE FUNCTION public.incident_events_append_only()
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS incident_events_append_only ON public.incident_events")
    op.execute("DROP FUNCTION IF EXISTS public.incident_events_append_only()")
    op.execute("DROP TABLE IF EXISTS public.incident_events")
