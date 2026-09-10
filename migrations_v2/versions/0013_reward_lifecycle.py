"""Harden reward lifecycle and birthday issuance.

Revision ID: 0013_reward_lifecycle
Revises: 0012_milestone_rewards
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_reward_lifecycle"
down_revision = "0012_milestone_rewards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customer_rewards", sa.Column("source_key", sa.String(160), nullable=True))
    op.add_column("customer_rewards", sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customer_rewards", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customer_rewards", sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_customer_rewards_source_key", "customer_rewards", ["source_key"])
    op.create_index(
        "uq_customer_rewards_org_customer_source_key",
        "customer_rewards",
        ["organization_id", "customer_id", "source_key"],
        unique=True,
        postgresql_where=sa.text("source_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_customer_rewards_org_customer_source_key", table_name="customer_rewards")
    op.drop_index("ix_customer_rewards_source_key", table_name="customer_rewards")
    op.drop_column("customer_rewards", "expired_at")
    op.drop_column("customer_rewards", "revoked_at")
    op.drop_column("customer_rewards", "consumed_at")
    op.drop_column("customer_rewards", "source_key")
