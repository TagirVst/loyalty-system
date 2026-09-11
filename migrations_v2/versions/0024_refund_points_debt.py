"""refund points debt

Revision ID: 0024_refund_points_debt
Revises: 0023_points_debt
"""
from alembic import op
import sqlalchemy as sa

revision = "0024_refund_points_debt"
down_revision = "0023_points_debt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refunds_v2", sa.Column("points_debt_created", sa.BigInteger(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("refunds_v2", "points_debt_created")
