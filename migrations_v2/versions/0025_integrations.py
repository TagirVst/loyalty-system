"""integration foundation

Revision ID: 0025_integrations
Revises: 0024_refund_points_debt
"""
from alembic import op
import sqlalchemy as sa

revision = "0025_integrations"
down_revision = "0024_refund_points_debt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_clients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("api_key_fingerprint", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_integration_clients_org_name"),
        sa.UniqueConstraint("api_key_fingerprint", name="uq_integration_clients_api_key_fingerprint"),
    )
    op.create_index("ix_integration_clients_organization_id", "integration_clients", ["organization_id"])
    op.create_index("ix_integration_clients_provider", "integration_clients", ["provider"])
    op.create_index("ix_integration_clients_api_key_fingerprint", "integration_clients", ["api_key_fingerprint"], unique=True)

    op.create_table(
        "integration_webhook_inbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("integration_client_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("external_event_id", sa.String(160), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_client_id"], ["integration_clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_client_id", "external_event_id", name="uq_integration_webhook_client_event"),
    )
    op.create_index("ix_integration_webhook_organization_id", "integration_webhook_inbox", ["organization_id"])
    op.create_index("ix_integration_webhook_integration_client_id", "integration_webhook_inbox", ["integration_client_id"])
    op.create_index("ix_integration_webhook_provider", "integration_webhook_inbox", ["provider"])
    op.create_index("ix_integration_webhook_status", "integration_webhook_inbox", ["status"])
    op.create_index("ix_integration_webhook_status_received", "integration_webhook_inbox", ["status", "received_at"])

    op.create_table(
        "external_order_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("external_order_id", sa.String(160), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("external_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders_v2.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "provider", "external_order_id", name="uq_external_order_mapping"),
    )
    op.create_index("ix_external_order_mappings_organization_id", "external_order_mappings", ["organization_id"])
    op.create_index("ix_external_order_mappings_provider", "external_order_mappings", ["provider"])
    op.create_index("ix_external_order_mappings_order_id", "external_order_mappings", ["order_id"])


def downgrade() -> None:
    op.drop_table("external_order_mappings")
    op.drop_table("integration_webhook_inbox")
    op.drop_table("integration_clients")
