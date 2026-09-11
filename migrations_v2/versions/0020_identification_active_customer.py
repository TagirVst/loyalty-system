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
    # Alembic creates alembic_version.version_num as VARCHAR(32) by default.
    # This revision ID is longer than 32 characters, so widen the column before
    # Alembic records this revision at the end of the migration transaction.
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.create_index(
        "uq_identification_active_customer_scope",
        "identification_sessions",
        ["organization_id", "customer_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    # Keep version_num widened: shrinking while the current long revision value
    # is stored would make downgrade itself impossible.
    op.drop_index("uq_identification_active_customer_scope", table_name="identification_sessions")
