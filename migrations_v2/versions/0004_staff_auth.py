"""Add staff terminal authentication tables.

Revision ID: 0004_staff_auth
Revises: 0003_orders_and_identification
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_staff_auth"
down_revision = "0003_orders_and_identification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_terminals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "telegram_chat_id", name="uq_staff_terminals_org_chat"),
    )
    op.create_index("ix_staff_terminals_organization_id", "staff_terminals", ["organization_id"])
    op.create_index("ix_staff_terminals_location_id", "staff_terminals", ["location_id"])

    op.create_table(
        "staff_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("terminal_id", sa.Uuid(), nullable=False),
        sa.Column("staff_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("authenticated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["terminal_id"], ["staff_terminals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_sessions_terminal_id", "staff_sessions", ["terminal_id"])
    op.create_index("ix_staff_sessions_staff_id", "staff_sessions", ["staff_id"])
    op.create_index("ix_staff_sessions_status", "staff_sessions", ["status"])

    op.create_table(
        "staff_pin_throttles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("terminal_id", sa.Uuid(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("lock_level", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["terminal_id"], ["staff_terminals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "terminal_id", name="uq_staff_pin_throttle_terminal"),
    )


def downgrade() -> None:
    op.drop_table("staff_pin_throttles")
    op.drop_table("staff_sessions")
    op.drop_table("staff_terminals")
