"""customer auth sessions

Revision ID: 0017_customer_sessions
Revises: 0016_feedback_segments
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_customer_sessions"
down_revision = "0016_feedback_segments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("identity_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_session_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["identity_id"], ["customer_auth_identities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "provider", "external_session_key", name="uq_customer_session_external"),
    )
    op.create_index("ix_customer_sessions_organization_id", "customer_sessions", ["organization_id"])
    op.create_index("ix_customer_sessions_customer_id", "customer_sessions", ["customer_id"])
    op.create_index("ix_customer_sessions_identity_id", "customer_sessions", ["identity_id"])
    op.create_index("ix_customer_sessions_status", "customer_sessions", ["status"])


def downgrade() -> None:
    op.drop_table("customer_sessions")
