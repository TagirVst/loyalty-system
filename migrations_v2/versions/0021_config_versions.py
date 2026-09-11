"""version reward, campaign and milestone semantics

Revision ID: 0021_config_versions
Revises: 0020_identification_active_customer
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_config_versions"
down_revision = "0020_identification_active_customer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reward_definitions", sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("customer_rewards", sa.Column("reward_definition_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("customer_rewards", sa.Column("definition_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("campaigns", sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("milestone_reward_rules", sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("milestone_issuances", sa.Column("rule_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("milestone_issuances", sa.Column("threshold_count_snapshot", sa.Integer(), nullable=True))
    op.add_column("milestone_issuances", sa.Column("repeatable_snapshot", sa.Boolean(), nullable=True))
    op.execute("UPDATE milestone_issuances mi SET threshold_count_snapshot = mr.threshold_count, repeatable_snapshot = mr.repeatable FROM milestone_reward_rules mr WHERE mi.rule_id = mr.id")
    op.alter_column("milestone_issuances", "threshold_count_snapshot", nullable=False)
    op.alter_column("milestone_issuances", "repeatable_snapshot", nullable=False)
    op.execute("UPDATE customer_rewards cr SET reward_definition_version = rd.config_version, definition_snapshot = json_build_object('code', rd.code, 'name', rd.name, 'reward_type', rd.reward_type, 'config', rd.config, 'stackable', rd.stackable, 'default_validity_days', rd.default_validity_days) FROM reward_definitions rd WHERE cr.reward_definition_id = rd.id")


def downgrade() -> None:
    op.drop_column("milestone_issuances", "repeatable_snapshot")
    op.drop_column("milestone_issuances", "threshold_count_snapshot")
    op.drop_column("milestone_issuances", "rule_version")
    op.drop_column("milestone_reward_rules", "config_version")
    op.drop_column("campaigns", "config_version")
    op.drop_column("customer_rewards", "definition_snapshot")
    op.drop_column("customer_rewards", "reward_definition_version")
    op.drop_column("reward_definitions", "config_version")
