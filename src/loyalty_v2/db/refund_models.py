from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from loyalty_v2.db.base import Base, UUIDPrimaryKeyMixin


class Refund(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "refunds_v2"
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key", name="uq_refunds_v2_org_idempotency"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders_v2.id", ondelete="RESTRICT"), nullable=False, index=True)
    actor_staff_id: Mapped[UUID] = mapped_column(ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False, index=True)
    refund_type: Mapped[str] = mapped_column(String(16), nullable=False)
    gross_refund_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paid_refund_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restored_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reversed_earned_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    qualification_reversal_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    calculation_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
