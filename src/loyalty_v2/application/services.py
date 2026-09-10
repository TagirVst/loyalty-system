from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.db.models import (
    Customer,
    CustomerLoyaltyState,
    LedgerEntryType,
    LoyaltyTier,
    PointsAccount,
    PointsLedgerEntry,
)


class DomainError(Exception):
    code = "DOMAIN_ERROR"


class CustomerAlreadyExists(DomainError):
    code = "CUSTOMER_ALREADY_EXISTS"


class CustomerNotFound(DomainError):
    code = "CUSTOMER_NOT_FOUND"


class InvalidPointsAmount(DomainError):
    code = "INVALID_POINTS_AMOUNT"


class InsufficientPoints(DomainError):
    code = "INSUFFICIENT_POINTS"


class NoActiveTier(DomainError):
    code = "NO_ACTIVE_TIER"


@dataclass(frozen=True, slots=True)
class RegisteredCustomer:
    customer: Customer
    account: PointsAccount
    loyalty_state: CustomerLoyaltyState


class TierService:
    async def tier_for_spend(
        self, session: AsyncSession, organization_id: UUID, spend_minor: int
    ) -> LoyaltyTier:
        stmt = (
            select(LoyaltyTier)
            .where(
                LoyaltyTier.organization_id == organization_id,
                LoyaltyTier.is_active.is_(True),
                LoyaltyTier.minimum_spend_minor <= spend_minor,
            )
            .order_by(LoyaltyTier.minimum_spend_minor.desc(), LoyaltyTier.sort_order.desc())
            .limit(1)
        )
        tier = await session.scalar(stmt)
        if tier is None:
            raise NoActiveTier("Organization has no active tier for this spend")
        return tier


class CustomerService:
    def __init__(self, tier_service: TierService | None = None) -> None:
        self.tiers = tier_service or TierService()

    async def register(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        telegram_id: int,
        first_name: str,
        phone: str,
        birth_date: date,
    ) -> RegisteredCustomer:
        existing = await session.scalar(
            select(Customer.id).where(
                Customer.organization_id == organization_id,
                (Customer.telegram_id == telegram_id) | (Customer.phone == phone),
            )
        )
        if existing is not None:
            raise CustomerAlreadyExists("Telegram identity or phone is already registered")

        base_tier = await self.tiers.tier_for_spend(session, organization_id, 0)
        customer = Customer(
            organization_id=organization_id,
            telegram_id=telegram_id,
            first_name=first_name.strip(),
            phone=phone,
            birth_date=birth_date,
        )
        session.add(customer)
        await session.flush()

        account = PointsAccount(
            organization_id=organization_id,
            customer_id=customer.id,
            balance=0,
        )
        loyalty_state = CustomerLoyaltyState(
            organization_id=organization_id,
            customer_id=customer.id,
            automatic_tier_id=base_tier.id,
            qualification_spend_minor=0,
        )
        session.add_all([account, loyalty_state])
        await session.flush()
        return RegisteredCustomer(customer, account, loyalty_state)


class PointsService:
    async def _locked_account(
        self, session: AsyncSession, organization_id: UUID, customer_id: UUID
    ) -> PointsAccount:
        stmt = (
            select(PointsAccount)
            .where(
                PointsAccount.organization_id == organization_id,
                PointsAccount.customer_id == customer_id,
            )
            .with_for_update()
        )
        account = await session.scalar(stmt)
        if account is None:
            raise CustomerNotFound("Points account not found")
        return account

    async def apply(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        customer_id: UUID,
        delta: int,
        entry_type: LedgerEntryType,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> PointsLedgerEntry:
        if delta == 0:
            raise InvalidPointsAmount("Points delta cannot be zero")

        if idempotency_key:
            existing = await session.scalar(
                select(PointsLedgerEntry).where(
                    PointsLedgerEntry.organization_id == organization_id,
                    PointsLedgerEntry.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return existing

        account = await self._locked_account(session, organization_id, customer_id)
        new_balance = account.balance + delta
        if new_balance < 0:
            raise InsufficientPoints("Points balance cannot become negative")

        account.balance = new_balance
        account.version += 1
        entry = PointsLedgerEntry(
            organization_id=organization_id,
            customer_id=customer_id,
            account_id=account.id,
            entry_type=entry_type.value,
            delta=delta,
            balance_after=new_balance,
            reference_type=reference_type,
            reference_id=reference_id,
            reason=reason,
            idempotency_key=idempotency_key,
            created_at=datetime.now(timezone.utc),
        )
        session.add(entry)
        await session.flush()
        return entry
