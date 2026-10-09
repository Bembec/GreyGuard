"""P2.2 batch 4: add org_id to service_accounts, service_account_keys, and
service_account_events; reshape service_accounts' unique constraint from (name) to
(name, org_id).

Fourth batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks. See
backend/app/service_accounts.py for the SQLite side of this same migration (ALTER-TABLE-style
imperative DDL, run from initialize_service_accounts() - both sides must stay in sync).

service_accounts has a different fixed-shape problem than batches 1-2's fixed-row-set primary
keys: it has a plain `UNIQUE (name)` constraint (case-insensitive, citext on PostgreSQL) that
would let two orgs collide on the same human-chosen account name. Reshaped to
`UNIQUE (name, org_id)` after backfilling every existing row into the default org.

service_account_keys and service_account_events needed only plain backfilled ADD COLUMNs -
they're always looked up by account_id (service_account_keys) or written alongside it
(service_account_events), never by a name a human picked, so no uniqueness reshape applies to
either.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_07"
down_revision = "20261009_06"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"

SIMPLE_TABLES = ("service_account_keys", "service_account_events")


def upgrade():
    for table in SIMPLE_TABLES:
        op.add_column(table, sa.Column("org_id", sa.Text(), nullable=True))
        op.execute(
            sa.text(f"UPDATE {table} SET org_id = :org_id WHERE org_id IS NULL")
            .bindparams(org_id=DEFAULT_ORG_ID)
        )
        op.alter_column(table, "org_id", nullable=False)

    op.add_column("service_accounts", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE service_accounts SET org_id = :org_id WHERE org_id IS NULL")
        .bindparams(org_id=DEFAULT_ORG_ID)
    )
    op.alter_column("service_accounts", "org_id", nullable=False)
    op.drop_constraint("service_accounts_name_key", "service_accounts", type_="unique")
    op.create_unique_constraint("service_accounts_name_key", "service_accounts", ["name", "org_id"])


def downgrade():
    op.drop_constraint("service_accounts_name_key", "service_accounts", type_="unique")
    # Same caveat as prior batches' composite-key downgrades: only safe to reverse if at most
    # one org's worth of rows exists.
    op.create_unique_constraint("service_accounts_name_key", "service_accounts", ["name"])
    op.drop_column("service_accounts", "org_id")

    for table in reversed(SIMPLE_TABLES):
        op.drop_column(table, "org_id")
