"""notification delivery lease

Revision ID: 0027_notification_delivery_lease
Revises: 0026_migration_tracking
"""
from alembic import op
import sqlalchemy as sa

revision = "0027_notification_delivery_lease"
down_revision = "0026_migration_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notification_outbox", sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_notification_outbox_lease", "notification_outbox", ["status", "lease_until"])


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_lease", table_name="notification_outbox")
    op.drop_column("notification_outbox", "lease_until")
