"""notification templates

Revision ID: 0019_notification_templates
Revises: 0018_notifications
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_notification_templates"
down_revision = "0018_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("notification_templates",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False), sa.Column("kind", sa.String(32), nullable=False, server_default="service"),
        sa.Column("channel", sa.String(32), nullable=False, server_default="telegram"), sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_notification_templates_org_code"))
    op.create_index("ix_notification_templates_organization_id", "notification_templates", ["organization_id"])


def downgrade() -> None:
    op.drop_table("notification_templates")
