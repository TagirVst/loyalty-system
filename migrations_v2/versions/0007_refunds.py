"""Add refunds.

Revision ID: 0007_refunds
Revises: 0006_order_loyalty_effects
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_refunds"
down_revision = "0006_order_loyalty_effects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refunds_v2",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("actor_staff_id", sa.Uuid(), nullable=False),
        sa.Column("refund_type", sa.String(16), nullable=False),
        sa.Column("gross_refund_minor", sa.BigInteger(), nullable=False),
        sa.Column("paid_refund_minor", sa.BigInteger(), nullable=False),
        sa.Column("restored_points", sa.BigInteger(), nullable=False),
        sa.Column("reversed_earned_points", sa.BigInteger(), nullable=False),
        sa.Column("qualification_reversal_minor", sa.BigInteger(), nullable=False),
        sa.Column("calculation_snapshot", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders_v2.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_staff_id"], ["staff.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_refunds_v2_org_idempotency"),
    )
    op.create_index("ix_refunds_v2_order_id", "refunds_v2", ["order_id"])


def downgrade() -> None:
    op.drop_table("refunds_v2")
