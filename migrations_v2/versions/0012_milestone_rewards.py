"""Add category counters and milestone rewards.

Revision ID: 0012_milestone_rewards
Revises: 0011_sale_categories
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_milestone_rewards"
down_revision = "0011_sale_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_category_counters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("sale_categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("lifetime_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("net_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "customer_id", "category_id", name="uq_customer_category_counter"),
        sa.CheckConstraint("lifetime_count >= 0", name="customer_category_lifetime_nonnegative"),
        sa.CheckConstraint("net_count >= 0", name="customer_category_net_nonnegative"),
    )
    op.create_index("ix_customer_category_counters_customer_id", "customer_category_counters", ["customer_id"])
    op.create_index("ix_customer_category_counters_category_id", "customer_category_counters", ["category_id"])

    op.create_table(
        "milestone_reward_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("sale_categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("threshold_count", sa.Integer(), nullable=False),
        sa.Column("reward_definition_id", sa.Uuid(), sa.ForeignKey("reward_definitions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("repeatable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "code", name="uq_milestone_reward_rule_code"),
        sa.CheckConstraint("threshold_count > 0", name="milestone_threshold_positive"),
    )
    op.create_index("ix_milestone_reward_rules_category_id", "milestone_reward_rules", ["category_id"])

    op.create_table(
        "milestone_issuances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.Uuid(), sa.ForeignKey("milestone_reward_rules.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("milestone_number", sa.Integer(), nullable=False),
        sa.Column("customer_reward_id", sa.Uuid(), sa.ForeignKey("customer_rewards.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_order_id", sa.Uuid(), sa.ForeignKey("orders_v2.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "customer_id", "rule_id", "milestone_number", name="uq_milestone_issuance_once"),
        sa.CheckConstraint("milestone_number > 0", name="milestone_number_positive"),
    )
    op.create_index("ix_milestone_issuances_customer_id", "milestone_issuances", ["customer_id"])
    op.create_index("ix_milestone_issuances_rule_id", "milestone_issuances", ["rule_id"])


def downgrade() -> None:
    op.drop_table("milestone_issuances")
    op.drop_table("milestone_reward_rules")
    op.drop_table("customer_category_counters")
