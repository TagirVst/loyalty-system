"""Add feedback and segment schema.

Revision ID: 0016_feedback_segments
Revises: 0015_staff_session_guard
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_feedback_segments"
down_revision = "0015_staff_session_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_segments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_customer_segments_org_code"),
    )
    op.create_index("ix_customer_segments_organization_id", "customer_segments", ["organization_id"])

    op.create_table(
        "feedback_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("positive_from_rating", sa.Integer(), nullable=False),
        sa.Column("external_review_url", sa.String(1000), nullable=True),
        sa.Column("notify_admins_on_rating_at_most", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_feedback_settings_org"),
    )
    op.create_index("ix_feedback_settings_organization_id", "feedback_settings", ["organization_id"])

    op.create_table(
        "customer_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("routed_to_admins", sa.Boolean(), nullable=False),
        sa.Column("external_review_offered", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_staff_id", sa.Uuid(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders_v2.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_staff_id"], ["staff.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="feedback_rating_range"),
    )
    op.create_index("ix_customer_feedback_organization_id", "customer_feedback", ["organization_id"])
    op.create_index("ix_customer_feedback_customer_id", "customer_feedback", ["customer_id"])
    op.create_index("ix_customer_feedback_order_id", "customer_feedback", ["order_id"])
    op.create_index("ix_customer_feedback_rating", "customer_feedback", ["rating"])
    op.create_index("ix_customer_feedback_status", "customer_feedback", ["status"])
    op.create_index("ix_customer_feedback_created_at", "customer_feedback", ["created_at"])


def downgrade() -> None:
    op.drop_table("customer_feedback")
    op.drop_table("feedback_settings")
    op.drop_table("customer_segments")
