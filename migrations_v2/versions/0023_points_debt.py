"""points debt accounting

Revision ID: 0023_points_debt
Revises: 0022_identification_fingerprints
"""
from alembic import op
import sqlalchemy as sa

revision = "0023_points_debt"
down_revision = "0022_identification_fingerprints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("points_accounts", sa.Column("debt", sa.BigInteger(), nullable=False, server_default="0"))
    op.create_check_constraint("points_debt_nonnegative", "points_accounts", "debt >= 0")
    op.add_column("points_ledger_entries", sa.Column("debt_applied", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("points_ledger_entries", sa.Column("debt_after", sa.BigInteger(), nullable=False, server_default="0"))
    op.create_check_constraint("ledger_debt_applied_nonnegative", "points_ledger_entries", "debt_applied >= 0")
    op.create_check_constraint("ledger_debt_after_nonnegative", "points_ledger_entries", "debt_after >= 0")


def downgrade() -> None:
    op.drop_constraint("ledger_debt_after_nonnegative", "points_ledger_entries", type_="check")
    op.drop_constraint("ledger_debt_applied_nonnegative", "points_ledger_entries", type_="check")
    op.drop_column("points_ledger_entries", "debt_after")
    op.drop_column("points_ledger_entries", "debt_applied")
    op.drop_constraint("points_debt_nonnegative", "points_accounts", type_="check")
    op.drop_column("points_accounts", "debt")
