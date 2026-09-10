"""Add V2 order flow tables.

Revision ID: 0003_orders_and_identification
Revises: 0002_points_idempotency
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_orders_and_identification"
down_revision = "0002_points_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identification_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=5), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_identification_sessions_customer_id", "identification_sessions", ["customer_id"])
    op.create_index("ix_identification_sessions_code", "identification_sessions", ["code"])
    op.create_index("ix_identification_sessions_status", "identification_sessions", ["status"])
    op.create_index("ix_identification_sessions_expires_at", "identification_sessions", ["expires_at"])
    op.create_index(
        "uq_identification_active_code_scope",
        "identification_sessions",
        ["organization_id", "code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "order_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("identification_session_id", sa.Uuid(), nullable=True),
        sa.Column("gross_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("requested_points", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("gross_amount_minor > 0", name="ck_order_drafts_gross_amount_positive"),
        sa.CheckConstraint("requested_points >= 0", name="ck_order_drafts_requested_points_nonnegative"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["identification_session_id"], ["identification_sessions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "order_quotes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("tier_id", sa.Uuid(), nullable=False),
        sa.Column("gross_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("amount_after_rewards_minor", sa.BigInteger(), nullable=False),
        sa.Column("max_redeemable_points", sa.BigInteger(), nullable=False),
        sa.Column("redeemed_points", sa.BigInteger(), nullable=False),
        sa.Column("paid_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("points_to_earn", sa.BigInteger(), nullable=False),
        sa.Column("qualification_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("potential_tier_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["draft_id"], ["order_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tier_id"], ["loyalty_tiers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["potential_tier_id"], ["loyalty_tiers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "orders_v2",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("quote_id", sa.Uuid(), nullable=False),
        sa.Column("gross_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("redeemed_points", sa.BigInteger(), nullable=False),
        sa.Column("paid_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("points_earned", sa.BigInteger(), nullable=False),
        sa.Column("qualification_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("tier_before_id", sa.Uuid(), nullable=False),
        sa.Column("tier_after_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["draft_id"], ["order_drafts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["quote_id"], ["order_quotes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tier_before_id"], ["loyalty_tiers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tier_after_id"], ["loyalty_tiers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_orders_v2_org_idempotency"),
    )


def downgrade() -> None:
    op.drop_table("orders_v2")
    op.drop_table("order_quotes")
    op.drop_table("order_drafts")
    op.drop_table("identification_sessions")
