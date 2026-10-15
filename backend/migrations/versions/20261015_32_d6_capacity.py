"""P4 decision D6: capacity counts only active agents and enabled integrations; archive metadata;
explicit plans required; Dedicated limits from the contract.

- archived_at / archived_by / archive_reason on agent_identities and the three destination tables
  (archiving frees capacity and keeps the record as history - nothing is deleted).
- org_entitlements.contract_limits_json for Dedicated contracts.
- entitlement_schema_marks, and the one-time transitional backfill: on an install that already has
  data, every existing org without a plan gets an explicit, audited TRANSITIONAL assignment, so
  nothing that worked before stops. A fresh install's orgs start UNASSIGNED.

See backend/app/entitlements.py (_migrate_existing_orgs) for the SQLite side; the mark stops the
application from running the backfill again.
"""
from alembic import op

revision = "20261015_32"
down_revision = "20261015_31"
branch_labels = None
depends_on = None

ARCHIVE_TABLES = ("agent_identities", "export_destinations", "incident_destinations", "notification_destinations")


def upgrade():
    for table in ARCHIVE_TABLES:
        op.execute(f"ALTER TABLE public.{table} ADD COLUMN archived_at text, ADD COLUMN archived_by text, ADD COLUMN archive_reason text")
    op.execute("ALTER TABLE public.org_entitlements ADD COLUMN contract_limits_json text")
    op.execute("CREATE TABLE public.entitlement_schema_marks (mark text PRIMARY KEY, applied_at text NOT NULL)")
    op.execute("""
        DO $$
        DECLARE has_data boolean;
        BEGIN
            has_data := EXISTS (SELECT 1 FROM agent_identities)
                OR EXISTS (SELECT 1 FROM export_destinations)
                OR EXISTS (SELECT 1 FROM incident_destinations)
                OR EXISTS (SELECT 1 FROM notification_destinations)
                OR (SELECT COUNT(*) FROM organizations WHERE status != 'DELETED') > 1;
            IF has_data THEN
                INSERT INTO entitlement_events (org_id, timestamp, actor, event_type, detail_json)
                SELECT o.org_id, to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'), 'migration:d6', 'PLAN_ASSIGNED',
                       '{"plan": "TRANSITIONAL", "reason": "Existed before plans were required; pre-D6 behaviour preserved until an operator assigns a plan.", "status": "ACTIVE"}'
                FROM organizations o
                WHERE o.status != 'DELETED' AND NOT EXISTS (SELECT 1 FROM org_entitlements e WHERE e.org_id = o.org_id);
                INSERT INTO org_entitlements (org_id, plan, status, trial_ends_at, updated_by, updated_at)
                SELECT o.org_id, 'TRANSITIONAL', 'ACTIVE', NULL, 'migration:d6',
                       to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
                FROM organizations o
                WHERE o.status != 'DELETED' AND NOT EXISTS (SELECT 1 FROM org_entitlements e WHERE e.org_id = o.org_id);
            END IF;
            INSERT INTO entitlement_schema_marks (mark, applied_at)
            VALUES ('d6_explicit_plans', to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'));
        END $$;
    """)


def downgrade():
    # Transitional assignments are removed with the mark; their audit events stay as history.
    op.execute("DELETE FROM org_entitlements WHERE plan = 'TRANSITIONAL'")
    op.execute("DROP TABLE entitlement_schema_marks")
    op.execute("ALTER TABLE public.org_entitlements DROP COLUMN contract_limits_json")
    for table in ARCHIVE_TABLES:
        op.execute(f"ALTER TABLE public.{table} DROP COLUMN archive_reason, DROP COLUMN archived_by, DROP COLUMN archived_at")
