"""Install-operator role: add administrators.install_operator.

A global account flag (like break_glass), orthogonal to every per-org role. It gates the
install-wide controls no single tenant may own - administrator accounts, org creation, SSO
configuration, rate limits, observability, the SSRF allowlist - which were previously gated by
PLATFORM_ADMIN, a role P2.1 made per-org. See backend/app/admin_auth.py for the SQLite side of
this same migration (run from initialize_admin_auth() - both sides must stay in sync).

Before orgs existed every PLATFORM_ADMIN ran the whole install, so existing ones are backfilled
as operators: nobody loses access on upgrade.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261010_18"
down_revision = "20261010_17"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("administrators", sa.Column("install_operator", sa.Integer(), nullable=False,
                                              server_default=sa.text("0")))
    op.execute("UPDATE administrators SET install_operator = 1 WHERE role = 'PLATFORM_ADMIN'")


def downgrade():
    op.drop_column("administrators", "install_operator")
