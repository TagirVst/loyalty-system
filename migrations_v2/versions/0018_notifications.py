"""notification outbox and preferences

Revision ID: 0018_notifications
Revises: 0017_customer_sessions
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_notifications"
down_revision = "0017_customer_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("customer_notification_preferences",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("organization_id", sa.Uuid(), nullable=False), sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("marketing_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("customer_id", name="uq_notification_preferences_customer"))
    op.create_index("ix_customer_notification_preferences_organization_id", "customer_notification_preferences", ["organization_id"])
    op.create_index("ix_customer_notification_preferences_customer_id", "customer_notification_preferences", ["customer_id"])
    op.create_table("notification_outbox",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_type", sa.String(20), nullable=False, server_default="customer"), sa.Column("customer_id", sa.Uuid(), nullable=True), sa.Column("recipient_address", sa.String(255), nullable=True),
        sa.Column("channel", sa.String(32), nullable=False, server_default="telegram"), sa.Column("kind", sa.String(32), nullable=False, server_default="service"),
        sa.Column("template_code", sa.String(80)), sa.Column("subject", sa.String(200)), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"), sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"), sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_error", sa.String(1000)), sa.Column("idempotency_key", sa.String(160)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True)), sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("(recipient_type = 'customer' AND customer_id IS NOT NULL AND recipient_address IS NULL) OR (recipient_type = 'staff_chat' AND customer_id IS NULL AND recipient_address IS NOT NULL)", name="notification_recipient_shape"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_notification_outbox_organization_id", "notification_outbox", ["organization_id"])
    op.create_index("ix_notification_outbox_customer_id", "notification_outbox", ["customer_id"])
    op.create_index("ix_notification_outbox_status", "notification_outbox", ["status"])
    op.create_index("ix_notification_outbox_due", "notification_outbox", ["status", "next_attempt_at"])
    op.create_index("uq_notification_outbox_org_idempotency", "notification_outbox", ["organization_id", "idempotency_key"], unique=True, postgresql_where=sa.text("idempotency_key IS NOT NULL"))


def downgrade() -> None:
    op.drop_table("notification_outbox")
    op.drop_table("customer_notification_preferences")
