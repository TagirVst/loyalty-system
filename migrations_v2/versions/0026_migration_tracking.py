"""migration tracking

Revision ID: 0026_migration_tracking
Revises: 0025_integrations
"""
from alembic import op
import sqlalchemy as sa

revision = "0026_migration_tracking"
down_revision = "0025_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "migration_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_migration_runs_organization_id", "migration_runs", ["organization_id"])
    op.create_index("ix_migration_runs_status", "migration_runs", ["status"])

    op.create_table(
        "legacy_customer_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("source_customer_id", sa.String(160), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("opening_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "source", "source_customer_id", name="uq_legacy_customer_mapping_source"),
    )
    op.create_index("ix_legacy_customer_mappings_organization_id", "legacy_customer_mappings", ["organization_id"])
    op.create_index("ix_legacy_customer_mapping_customer", "legacy_customer_mappings", ["organization_id", "customer_id"])


def downgrade() -> None:
    op.drop_table("legacy_customer_mappings")
    op.drop_table("migration_runs")
