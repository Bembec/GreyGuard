"""P2.2 batch 1: add org_id to simulation_runs, capability_removals,
capability_removal_steps and universal_control_events; reshape
universal_capability_controls' primary key from (capability) to (capability, org_id).

First real batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks -
chosen as the proving batch for being small and having almost no foreign-key fan-out. See
backend/app/{adversarial_simulations,capability_removal,universal_controls}.py for the SQLite
side of this same migration (ALTER-TABLE-style imperative DDL, run from each module's own
initialize_*() - both sides must stay in sync).

universal_capability_controls is not a per-resource table in the usual sense: it has exactly
five rows (one per named capability in universal_controls.CAPABILITIES), globally, keyed by
`capability` alone. Simply adding org_id without reshaping the key would let two organizations
collide on the same capability name - Postgres can reshape this via ALTER (unlike SQLite, which
has no ALTER-the-primary-key and instead rebuilds the table - see the SQLite-side code), so this
migration drops the old single-column primary key and replaces it with a composite
(capability, org_id) key, after backfilling every existing row into the default org.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_04"
down_revision = "20261009_03"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"

SIMPLE_TABLES = (
    "simulation_runs",
    "capability_removals",
    "capability_removal_steps",
    "universal_control_events",
)


def upgrade():
    for table in SIMPLE_TABLES:
        op.add_column(table, sa.Column("org_id", sa.Text(), nullable=True))
        op.execute(
            sa.text(f"UPDATE {table} SET org_id = :org_id WHERE org_id IS NULL")
            .bindparams(org_id=DEFAULT_ORG_ID)
        )
        op.alter_column(table, "org_id", nullable=False)

    op.add_column("universal_capability_controls", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE universal_capability_controls SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("universal_capability_controls", "org_id", nullable=False)
    op.drop_constraint("universal_capability_controls_pkey", "universal_capability_controls", type_="primary")
    op.create_primary_key(
        "universal_capability_controls_pkey", "universal_capability_controls", ["capability", "org_id"],
    )


def downgrade():
    op.drop_constraint("universal_capability_controls_pkey", "universal_capability_controls", type_="primary")
    # Downgrading only makes sense if at most one org's worth of rows exists - the same
    # assumption every downgrade in this codebase makes about reversing a tenant-scoping
    # migration, since collapsing N orgs' rows back onto a single-column key is lossy by
    # definition and not something a migration can safely resolve on your behalf.
    op.create_primary_key(
        "universal_capability_controls_pkey", "universal_capability_controls", ["capability"],
    )
    op.drop_column("universal_capability_controls", "org_id")
    for table in SIMPLE_TABLES:
        op.drop_column(table, "org_id")
