from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from loyalty_v2.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StaffRole(StrEnum):
    BARISTA = "barista"
    ADMIN = "admin"


class LedgerEntryType(StrEnum):
    EARN = "earn"
    REDEEM = "redeem"
    REFUND = "refund"
    REVERSAL = "reversal"
    MANUAL = "manual"
    EXPIRE = "expire"
    CAMPAIGN = "campaign"
    MIGRATION = "migration"


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    default_currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_locations_organization_code"),)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Moscow")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("organization_id", "phone", name="uq_customers_org_phone"),)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    first_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_date_change_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Staff(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "staff"
    __table_args__ = (UniqueConstraint("organization_id", "pin_fingerprint", name="uq_staff_org_pin_fingerprint"),)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id: Mapped[UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    pin_hash: Mapped[str | None] = mapped_column(String(255))
    pin_fingerprint: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LoyaltyTier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "loyalty_tiers"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_loyalty_tiers_org_name"),
        UniqueConstraint("organization_id", "sort_order", name="uq_loyalty_tiers_org_sort_order"),
        CheckConstraint("minimum_spend_minor >= 0", name="minimum_spend_nonnegative"),
        CheckConstraint("cashback_basis_points >= 0", name="cashback_nonnegative"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_spend_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cashback_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CustomerLoyaltyState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_loyalty_states"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_customer_loyalty_state_customer"),
        CheckConstraint("qualification_spend_minor >= 0", name="qualification_spend_nonnegative"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    automatic_tier_id: Mapped[UUID] = mapped_column(ForeignKey("loyalty_tiers.id", ondelete="RESTRICT"), nullable=False)
    qualification_spend_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_purchase_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inactivity_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PointsAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "points_accounts"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_points_accounts_customer"),
        CheckConstraint("balance >= 0", name="balance_nonnegative"),
        CheckConstraint("debt >= 0", name="points_debt_nonnegative"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    debt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class PointsLedgerEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "points_ledger_entries"
    __table_args__ = (
        CheckConstraint("delta <> 0", name="delta_nonzero"),
        CheckConstraint("debt_applied >= 0", name="ledger_debt_applied_nonnegative"),
        CheckConstraint("debt_after >= 0", name="ledger_debt_after_nonnegative"),
        Index("uq_points_ledger_entries_org_idempotency", "organization_id", "idempotency_key", unique=True, postgresql_where=text("idempotency_key IS NOT NULL")),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("points_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    delta: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    debt_applied: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    debt_after: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reference_type: Mapped[str | None] = mapped_column(String(64))
    reference_id: Mapped[UUID | None] = mapped_column(nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, server_default=func.now())
