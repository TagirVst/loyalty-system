from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from loyalty_v2.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CustomerSegment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_segments"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_customer_segments_org_code"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FeedbackSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feedback_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_feedback_settings_org"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    positive_from_rating: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    external_review_url: Mapped[str | None] = mapped_column(String(1000))
    notify_admins_on_rating_at_most: Mapped[int] = mapped_column(Integer, nullable=False, default=3)


class CustomerFeedback(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "customer_feedback"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders_v2.id", ondelete="SET NULL"), nullable=True, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="new", index=True)
    routed_to_admins: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    external_review_offered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_staff_id: Mapped[UUID | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text)
