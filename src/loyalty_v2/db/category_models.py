from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, String, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from loyalty_v2.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SaleCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sale_categories"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_sale_categories_org_code"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
