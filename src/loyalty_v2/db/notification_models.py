from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from loyalty_v2.db.base import Base, UUIDPrimaryKeyMixin


class CustomerNotificationPreference(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "customer_notification_preferences"
    __table_args__ = (UniqueConstraint("customer_id", name="uq_notification_preferences_customer"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    service_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    marketing_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class NotificationOutbox(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        CheckConstraint("(recipient_type = 'customer' AND customer_id IS NOT NULL AND recipient_address IS NULL) OR (recipient_type = 'staff_chat' AND customer_id IS NULL AND recipient_address IS NOT NULL)", name="notification_recipient_shape"),
        Index("uq_notification_outbox_org_idempotency", "organization_id", "idempotency_key", unique=True, postgresql_where=text("idempotency_key IS NOT NULL")),
        Index("ix_notification_outbox_due", "status", "next_attempt_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_type: Mapped[str] = mapped_column(String(20), nullable=False, default="customer")
    customer_id: Mapped[UUID | None] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=True, index=True)
    recipient_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="telegram")
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="service")
    template_code: Mapped[str | None] = mapped_column(String(80))
    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(String(1000))
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
