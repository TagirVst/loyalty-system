"""identification code fingerprints

Revision ID: 0022_identification_fingerprints
Revises: 0021_config_versions
"""
from alembic import op
import sqlalchemy as sa

revision = "0022_identification_fingerprints"
down_revision = "0021_config_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE identification_sessions SET status = 'expired' WHERE status = 'active'")
    op.drop_index("uq_identification_active_code_scope", table_name="identification_sessions")
    op.add_column("identification_sessions", sa.Column("code_fingerprint", sa.String(64), nullable=True))
    op.create_index("ix_identification_sessions_code_fingerprint", "identification_sessions", ["code_fingerprint"])
    op.create_index(
        "uq_identification_active_code_scope",
        "identification_sessions",
        ["organization_id", "code_fingerprint"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.alter_column("identification_sessions", "code", existing_type=sa.String(5), nullable=True)
    op.execute("UPDATE identification_sessions SET code = NULL")


def downgrade() -> None:
    op.drop_index("uq_identification_active_code_scope", table_name="identification_sessions")
    op.drop_index("ix_identification_sessions_code_fingerprint", table_name="identification_sessions")
    op.drop_column("identification_sessions", "code_fingerprint")
    op.execute("UPDATE identification_sessions SET code = '00000' WHERE code IS NULL")
    op.alter_column("identification_sessions", "code", existing_type=sa.String(5), nullable=False)
    op.create_index(
        "uq_identification_active_code_scope",
        "identification_sessions",
        ["organization_id", "code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
