from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from loyalty_v2.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RewardDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reward_definitions"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_reward_definitions_org_code"),)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_validity_days: Mapped[int | None] = mapped_column(Integer)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CustomerReward(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "customer_rewards"
    __table_args__ = (Index("uq_customer_rewards_org_customer_source_key", "organization_id", "customer_id", "source_key", unique=True, postgresql_where=text("source_key IS NOT NULL")),)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    reward_definition_id: Mapped[UUID] = mapped_column(ForeignKey("reward_definitions.id", ondelete="RESTRICT"), nullable=False, index=True)
    reward_definition_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    definition_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    quantity_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_id: Mapped[UUID | None] = mapped_column()
    source_key: Mapped[str | None] = mapped_column(String(160), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_campaigns_org_code"),)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    stackable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    effects: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
