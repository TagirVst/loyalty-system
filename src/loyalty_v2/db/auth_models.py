from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from loyalty_v2.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StaffTerminal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "staff_terminals"
    __table_args__ = (
        UniqueConstraint("organization_id", "telegram_chat_id", name="uq_staff_terminals_org_chat"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class StaffSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "staff_sessions"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    terminal_id: Mapped[UUID] = mapped_column(ForeignKey("staff_terminals.id", ondelete="RESTRICT"), nullable=False, index=True)
    staff_id: Mapped[UUID] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StaffPinThrottle(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "staff_pin_throttles"
    __table_args__ = (
        UniqueConstraint("organization_id", "terminal_id", name="uq_staff_pin_throttle_terminal"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    terminal_id: Mapped[UUID] = mapped_column(ForeignKey("staff_terminals.id", ondelete="CASCADE"), nullable=False, index=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lock_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
