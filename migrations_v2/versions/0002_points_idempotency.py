"""Enforce points ledger idempotency per organization.

Revision ID: 0002_points_idempotency
Revises: 0001_foundation
"""

from alembic import op


revision = "0002_points_idempotency"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_points_ledger_entries_idempotency_key", table_name="points_ledger_entries")
    op.create_index(
        "uq_points_ledger_entries_org_idempotency",
        "points_ledger_entries",
        ["organization_id", "idempotency_key"],
        unique=True,
        postgresql_where="idempotency_key IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_points_ledger_entries_org_idempotency", table_name="points_ledger_entries")
    op.create_index(
        "ix_points_ledger_entries_idempotency_key",
        "points_ledger_entries",
        ["idempotency_key"],
        unique=False,
    )
