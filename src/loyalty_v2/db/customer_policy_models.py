from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from loyalty_v2.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CustomerTierOverride(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_tier_overrides"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    tier_id: Mapped[UUID] = mapped_column(ForeignKey("loyalty_tiers.id", ondelete="RESTRICT"), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by_staff_id: Mapped[UUID] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class CustomerRedemptionOverride(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_redemption_overrides"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    max_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by_staff_id: Mapped[UUID] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class CustomerProfileChange(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "customer_profile_changes"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(255))
    new_value: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
