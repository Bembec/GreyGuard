"""P2.2 policy batch: org-scope policy versions, change control, emergency controls, adapters and
rollouts.

See backend/app/policy_control.py and backend/app/policy_integrations.py for the SQLite side of
this same migration (both sides must stay in sync).

Every policy table gains org_id; everything that predates orgs belongs to org_default. Three
reshapes:
- policy_versions.version_number was globally UNIQUE, so two orgs could never both have a
  version 1: now UNIQUE(version_number, org_id). Its primary key - the target of the change-event,
  test-case and supersedes foreign keys - is unchanged.
- policy_emergency_controls was a singleton (PK control_id, CHECK control_id = 1): now a
  composite (control_id, org_id) key, as simulation_config in batch 8.
- policy_adapters held one fixed row per adapter type: now a composite (adapter_type, org_id)
  key, as adapter_configs in batch 2.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_22"
down_revision = "20261010_21"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"
TABLES = (
    "policy_versions",
    "policy_change_events",
    "policy_test_cases",
    "policy_emergency_controls",
    "policy_emergency_events",
    "policy_adapters",
    "policy_rollouts",
    "policy_integration_events",
)
COMPOSITE_KEYS = {
    "policy_emergency_controls": ("control_id",),
    "policy_adapters": ("adapter_type",),
}


def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column("org_id", sa.Text(), nullable=True,
                                       server_default=sa.text(f"'{DEFAULT_ORG_ID}'")))
        op.execute(
            sa.text(f"UPDATE {table} SET org_id = :org_id WHERE org_id IS NULL")
            .bindparams(org_id=DEFAULT_ORG_ID)
        )
        op.alter_column(table, "org_id", nullable=False)
    op.drop_constraint("policy_versions_version_number_key", "policy_versions", type_="unique")
    op.create_unique_constraint("policy_versions_version_number_key", "policy_versions",
                                ["version_number", "org_id"])
    for table, key in COMPOSITE_KEYS.items():
        op.drop_constraint(f"{table}_pkey", table, type_="primary")
        op.create_primary_key(f"{table}_pkey", table, [*key, "org_id"])


def downgrade():
    # Same caveat as prior batches' composite-key downgrades: only safe to reverse if at most one
    # org's worth of rows exists.
    for table, key in COMPOSITE_KEYS.items():
        op.drop_constraint(f"{table}_pkey", table, type_="primary")
        op.create_primary_key(f"{table}_pkey", table, list(key))
    op.drop_constraint("policy_versions_version_number_key", "policy_versions", type_="unique")
    op.create_unique_constraint("policy_versions_version_number_key", "policy_versions", ["version_number"])
    for table in reversed(TABLES):
        op.drop_column(table, "org_id")
