"""Add reward and campaign tables.

Revision ID: 0005_rewards_campaigns
Revises: 0004_staff_auth
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_rewards_campaigns"
down_revision = "0004_staff_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reward_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("reward_type", sa.String(32), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("stackable", sa.Boolean(), nullable=False),
        sa.Column("default_validity_days", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_reward_definitions_org_code"),
    )
    op.create_index("ix_reward_definitions_organization_id", "reward_definitions", ["organization_id"])

    op.create_table(
        "customer_rewards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("reward_definition_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_remaining", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reward_definition_id"], ["reward_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_rewards_customer_id", "customer_rewards", ["customer_id"])
    op.create_index("ix_customer_rewards_status", "customer_rewards", ["status"])
    op.create_index("ix_customer_rewards_valid_until", "customer_rewards", ["valid_until"])

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("stackable", sa.Boolean(), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("effects", sa.JSON(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_campaigns_org_code"),
    )
    op.create_index("ix_campaigns_organization_id", "campaigns", ["organization_id"])
    op.create_index("ix_campaigns_starts_at", "campaigns", ["starts_at"])
    op.create_index("ix_campaigns_ends_at", "campaigns", ["ends_at"])


def downgrade() -> None:
    op.drop_table("campaigns")
    op.drop_table("customer_rewards")
    op.drop_table("reward_definitions")
