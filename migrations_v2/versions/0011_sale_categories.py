"""Add configurable sale categories and order category snapshots.

Revision ID: 0011_sale_categories
Revises: 0010_customer_auth_identities
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_sale_categories"
down_revision = "0010_customer_auth_identities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sale_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_sale_categories_org_code"),
    )
    op.create_index("ix_sale_categories_organization_id", "sale_categories", ["organization_id"])
    op.add_column("order_drafts", sa.Column("category_counts", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("order_quotes", sa.Column("category_counts_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("orders_v2", sa.Column("category_counts_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))


def downgrade() -> None:
    op.drop_column("orders_v2", "category_counts_snapshot")
    op.drop_column("order_quotes", "category_counts_snapshot")
    op.drop_column("order_drafts", "category_counts")
    op.drop_table("sale_categories")
