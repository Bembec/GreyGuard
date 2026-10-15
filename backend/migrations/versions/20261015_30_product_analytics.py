"""P5: privacy-safe product analytics - daily page-view counts per org and path, and each org's
opt-out. No user, session, IP, payload or URL parameter is stored. See
backend/app/product_analytics.py for the SQLite side of this same migration.
"""
from alembic import op

revision = "20261015_30"
down_revision = "20261015_29"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE public.product_usage_daily (
        org_id text NOT NULL, day text NOT NULL, path text NOT NULL, views integer NOT NULL,
        PRIMARY KEY (org_id, day, path))""")
    op.execute("""CREATE TABLE public.product_analytics_settings (
        org_id text PRIMARY KEY, enabled integer NOT NULL, updated_by text NOT NULL, updated_at text NOT NULL)""")


def downgrade():
    op.execute("DROP TABLE product_analytics_settings")
    op.execute("DROP TABLE product_usage_daily")
