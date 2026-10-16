"""P7.5 Control Graph: exact, append-only decision records for tool requests.

One row per new tool request, written when its decision is made: the policy version and source, a
stable matched rule id with its type, name and snapshot, the outcome, and SHA-256 fingerprints of
the deciding policy's content and of the record itself (backend/app/decision_provenance.py).

Append-only: the trigger refuses every UPDATE. DELETE stays possible on purpose, so organization
deletion and retention keep working as before. The application creates the same table and an
equivalent trigger on SQLite. audit_events is deliberately not altered: a new column there would
change the hashed content of rows the integrity chain has already sealed.
"""
from alembic import op

revision = "20261016_34"
down_revision = "20261016_33"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE public.decision_records (
            request_id text PRIMARY KEY,
            org_id text NOT NULL,
            agent_name text NOT NULL,
            action text NOT NULL,
            decided_at text NOT NULL,
            outcome text NOT NULL,
            policy_source text NOT NULL,
            policy_version_id text,
            policy_version_number integer,
            matched_rule_id text NOT NULL,
            rule_type text NOT NULL,
            rule_name text NOT NULL,
            rule_snapshot_json text NOT NULL,
            policy_fingerprint text,
            record_fingerprint text NOT NULL,
            schema_version integer NOT NULL
        )
    """)
    op.execute("CREATE INDEX idx_decision_records_org_agent ON public.decision_records (org_id, agent_name, decided_at)")
    op.execute("""
        CREATE FUNCTION public.decision_records_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'decision records are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER decision_records_append_only
        BEFORE UPDATE ON public.decision_records
        FOR EACH ROW EXECUTE FUNCTION public.decision_records_append_only()
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS decision_records_append_only ON public.decision_records")
    op.execute("DROP FUNCTION IF EXISTS public.decision_records_append_only()")
    op.execute("DROP TABLE IF EXISTS public.decision_records")
