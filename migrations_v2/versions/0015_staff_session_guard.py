"""Enforce one active staff session per terminal.

Revision ID: 0015_staff_session_guard
Revises: 0014_audit_logs
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_staff_session_guard"
down_revision = "0014_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_staff_sessions_active_terminal",
        "staff_sessions",
        ["terminal_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_staff_sessions_active_terminal", table_name="staff_sessions")
