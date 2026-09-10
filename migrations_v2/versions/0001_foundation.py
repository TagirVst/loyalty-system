"""V2 foundation schema.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-09-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("default_currency_code", sa.String(length=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_table(
        "locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_locations_organization_id_organizations", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_locations"),
        sa.UniqueConstraint("organization_id", "code", name="uq_locations_organization_code"),
    )
    op.create_index("ix_locations_organization_id", "locations", ["organization_id"])

    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("birth_date_change_count", sa.Integer(), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), nullable=False),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_customers_organization_id_organizations", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
        sa.UniqueConstraint("organization_id", "telegram_id", name="uq_customers_org_telegram"),
        sa.UniqueConstraint("organization_id", "phone", name="uq_customers_org_phone"),
    )
    op.create_index("ix_customers_organization_id", "customers", ["organization_id"])

    op.create_table(
        "staff",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("pin_hash", sa.String(length=255), nullable=True),
        sa.Column("pin_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], name="fk_staff_location_id_locations", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_staff_organization_id_organizations", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_staff"),
        sa.UniqueConstraint("organization_id", "pin_fingerprint", name="uq_staff_org_pin_fingerprint"),
    )
    op.create_index("ix_staff_location_id", "staff", ["location_id"])
    op.create_index("ix_staff_organization_id", "staff", ["organization_id"])

    op.create_table(
        "loyalty_tiers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("minimum_spend_minor", sa.BigInteger(), nullable=False),
        sa.Column("cashback_basis_points", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("minimum_spend_minor >= 0", name="ck_loyalty_tiers_minimum_spend_nonnegative"),
        sa.CheckConstraint("cashback_basis_points >= 0", name="ck_loyalty_tiers_cashback_nonnegative"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_loyalty_tiers_organization_id_organizations", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_loyalty_tiers"),
        sa.UniqueConstraint("organization_id", "name", name="uq_loyalty_tiers_org_name"),
        sa.UniqueConstraint("organization_id", "sort_order", name="uq_loyalty_tiers_org_sort_order"),
    )
    op.create_index("ix_loyalty_tiers_organization_id", "loyalty_tiers", ["organization_id"])

    op.create_table(
        "customer_loyalty_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("automatic_tier_id", sa.Uuid(), nullable=False),
        sa.Column("qualification_spend_minor", sa.BigInteger(), nullable=False),
        sa.Column("last_purchase_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("inactivity_steps", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("qualification_spend_minor >= 0", name="ck_customer_loyalty_states_qualification_spend_nonnegative"),
        sa.ForeignKeyConstraint(["automatic_tier_id"], ["loyalty_tiers.id"], name="fk_customer_loyalty_states_automatic_tier_id_loyalty_tiers", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_customer_loyalty_states_customer_id_customers", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_customer_loyalty_states_organization_id_organizations", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_customer_loyalty_states"),
        sa.UniqueConstraint("customer_id", name="uq_customer_loyalty_state_customer"),
    )
    op.create_index("ix_customer_loyalty_states_customer_id", "customer_loyalty_states", ["customer_id"])
    op.create_index("ix_customer_loyalty_states_organization_id", "customer_loyalty_states", ["organization_id"])

    op.create_table(
        "points_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("balance >= 0", name="ck_points_accounts_balance_nonnegative"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_points_accounts_customer_id_customers", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_points_accounts_organization_id_organizations", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_points_accounts"),
        sa.UniqueConstraint("customer_id", name="uq_points_accounts_customer"),
    )
    op.create_index("ix_points_accounts_customer_id", "points_accounts", ["customer_id"])
    op.create_index("ix_points_accounts_organization_id", "points_accounts", ["organization_id"])

    op.create_table(
        "points_ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("delta", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("delta <> 0", name="ck_points_ledger_entries_delta_nonzero"),
        sa.ForeignKeyConstraint(["account_id"], ["points_accounts.id"], name="fk_points_ledger_entries_account_id_points_accounts", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_points_ledger_entries_customer_id_customers", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_points_ledger_entries_organization_id_organizations", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_points_ledger_entries"),
    )
    op.create_index("ix_points_ledger_entries_account_id", "points_ledger_entries", ["account_id"])
    op.create_index("ix_points_ledger_entries_created_at", "points_ledger_entries", ["created_at"])
    op.create_index("ix_points_ledger_entries_customer_id", "points_ledger_entries", ["customer_id"])
    op.create_index("ix_points_ledger_entries_entry_type", "points_ledger_entries", ["entry_type"])
    op.create_index("ix_points_ledger_entries_idempotency_key", "points_ledger_entries", ["idempotency_key"])
    op.create_index("ix_points_ledger_entries_organization_id", "points_ledger_entries", ["organization_id"])


def downgrade() -> None:
    op.drop_table("points_ledger_entries")
    op.drop_table("points_accounts")
    op.drop_table("customer_loyalty_states")
    op.drop_table("loyalty_tiers")
    op.drop_table("staff")
    op.drop_table("customers")
    op.drop_table("locations")
    op.drop_table("organizations")
