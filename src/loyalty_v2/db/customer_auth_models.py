from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from loyalty_v2.db.base import Base, UUIDPrimaryKeyMixin


class CustomerSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "customer_sessions"
    __table_args__ = (
        UniqueConstraint("organization_id", "provider", "external_session_key", name="uq_customer_session_external"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    identity_id: Mapped[UUID] = mapped_column(ForeignKey("customer_auth_identities.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_session_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
