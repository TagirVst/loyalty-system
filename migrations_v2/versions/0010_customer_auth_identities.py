"""Add provider-neutral customer auth identities.

Revision ID: 0010_customer_auth_identities
Revises: 0009_customer_policies
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_customer_auth_identities"
down_revision = "0009_customer_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_auth_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_subject", sa.String(255), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verified_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "provider", "external_subject", name="uq_customer_identity_subject"),
        sa.UniqueConstraint("customer_id", "provider", name="uq_customer_identity_provider"),
    )
    op.create_index("ix_customer_auth_identities_organization_id", "customer_auth_identities", ["organization_id"])
    op.create_index("ix_customer_auth_identities_customer_id", "customer_auth_identities", ["customer_id"])
    op.execute(sa.text("""
        INSERT INTO customer_auth_identities
            (id, organization_id, customer_id, provider, external_subject, is_verified, is_active, verified_at, created_at)
        SELECT gen_random_uuid(), organization_id, id, 'telegram', telegram_id::text, true, true, now(), now()
        FROM customers
        WHERE telegram_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """))
    op.drop_constraint("uq_customers_org_telegram", "customers", type_="unique")
    op.alter_column("customers", "telegram_id", existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    op.alter_column("customers", "telegram_id", existing_type=sa.BigInteger(), nullable=False)
    op.create_unique_constraint("uq_customers_org_telegram", "customers", ["organization_id", "telegram_id"])
    op.drop_table("customer_auth_identities")
