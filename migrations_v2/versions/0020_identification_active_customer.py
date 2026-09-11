"""one active identification session per customer

Revision ID: 0020_identification_active_customer
Revises: 0019_notification_templates
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_identification_active_customer"
down_revision = "0019_notification_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_identification_active_customer_scope",
        "identification_sessions",
        ["organization_id", "customer_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_identification_active_customer_scope", table_name="identification_sessions")
