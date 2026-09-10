from __future__ import annotations

from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from loyalty_v2.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CustomerCategoryCounter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_category_counters"
    __table_args__ = (
        UniqueConstraint("organization_id", "customer_id", "category_id", name="uq_customer_category_counter"),
        CheckConstraint("lifetime_count >= 0", name="customer_category_lifetime_nonnegative"),
        CheckConstraint("net_count >= 0", name="customer_category_net_nonnegative"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("sale_categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    lifetime_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    net_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class MilestoneRewardRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "milestone_reward_rules"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_milestone_reward_rule_code"),
        CheckConstraint("threshold_count > 0", name="milestone_threshold_positive"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("sale_categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    threshold_count: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_definition_id: Mapped[UUID] = mapped_column(ForeignKey("reward_definitions.id", ondelete="RESTRICT"), nullable=False)
    repeatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MilestoneIssuance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "milestone_issuances"
    __table_args__ = (
        UniqueConstraint("organization_id", "customer_id", "rule_id", "milestone_number", name="uq_milestone_issuance_once"),
        CheckConstraint("milestone_number > 0", name="milestone_number_positive"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id: Mapped[UUID] = mapped_column(ForeignKey("milestone_reward_rules.id", ondelete="RESTRICT"), nullable=False, index=True)
    milestone_number: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_reward_id: Mapped[UUID] = mapped_column(ForeignKey("customer_rewards.id", ondelete="RESTRICT"), nullable=False)
    source_order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders_v2.id", ondelete="RESTRICT"), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
