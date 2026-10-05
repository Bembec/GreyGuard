"""Create PostgreSQL migration control evidence table."""
from alembic import op
import sqlalchemy as sa
revision="20261005_01";down_revision=None;branch_labels=None;depends_on=None
def upgrade():
    op.create_table("greyguard_migration_control",sa.Column("migration_id",sa.String(80),primary_key=True),sa.Column("applied_at",sa.DateTime(timezone=True),nullable=False),sa.Column("source_commit",sa.String(64),nullable=False),sa.Column("source_backup_sha256",sa.String(64),nullable=False),sa.Column("verified",sa.Boolean(),nullable=False,server_default=sa.false()))
def downgrade():
    op.drop_table("greyguard_migration_control")
