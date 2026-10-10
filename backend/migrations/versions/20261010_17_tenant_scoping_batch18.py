"""P2.2 batch 18: add a nullable org_id to outbound_delivery_evidence.

Eighteenth batch of the tenant-scoping sweep tenant_guard.py's ORG_SCOPED_TABLES tracks. See
backend/app/outbound_delivery.py for the SQLite side of this same migration (imperative DDL run
from initialize_outbound_delivery() - both sides must stay in sync).

Unlike every earlier batch, org_id stays NULLABLE: NULL marks an install-level event with no
tenant behind it (enterprise SSO login handshakes and changes to the install-wide SSRF allowlist),
rather than misattributing it to org_default, which is a real tenant. Pre-existing evidence from
every other subsystem predates orgs and is backfilled to org_default.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_17"
down_revision = "20261010_16"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "org_default"
INSTALL_LEVEL_SUBSYSTEMS = ("ENTERPRISE_SSO", "SSRF_ALLOWLIST")


def upgrade():
    op.add_column("outbound_delivery_evidence", sa.Column("org_id", sa.Text(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE outbound_delivery_evidence SET org_id = :org_id "
            "WHERE subsystem NOT IN :install_level"
        ).bindparams(
            sa.bindparam("org_id", DEFAULT_ORG_ID),
            sa.bindparam("install_level", INSTALL_LEVEL_SUBSYSTEMS, expanding=True),
        )
    )


def downgrade():
    op.drop_column("outbound_delivery_evidence", "org_id")
