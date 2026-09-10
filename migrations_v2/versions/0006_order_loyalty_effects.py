"""Persist selected rewards and loyalty effect snapshots.

Revision ID: 0006_order_loyalty_effects
Revises: 0005_rewards_campaigns
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_order_loyalty_effects"
down_revision = "0005_rewards_campaigns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_drafts", sa.Column("selected_reward_ids", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("order_quotes", sa.Column("loyalty_effects_snapshot", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("orders_v2", sa.Column("loyalty_effects_snapshot", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("orders_v2", "loyalty_effects_snapshot")
    op.drop_column("order_quotes", "loyalty_effects_snapshot")
    op.drop_column("order_drafts", "selected_reward_ids")
