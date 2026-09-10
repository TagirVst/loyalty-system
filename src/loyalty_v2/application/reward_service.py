from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import DomainError
from loyalty_v2.db.models import Customer
from loyalty_v2.db.reward_models import CustomerReward, RewardDefinition


class RewardStatus(StrEnum):
    ISSUED = "issued"
    ACTIVE = "active"
    CONSUMED = "consumed"
    REVOKED = "revoked"
    EXPIRED = "expired"


class RewardUnavailable(DomainError):
    code = "REWARD_UNAVAILABLE"


class RewardAlreadyIssued(DomainError):
    code = "REWARD_ALREADY_ISSUED"


def birthday_in_year(birth_date: date, year: int) -> date:
    """Map Feb 29 to Feb 28 in non-leap years; preserve all other birthdays."""
    try:
        return birth_date.replace(year=year)
    except ValueError:
        if birth_date.month == 2 and birth_date.day == 29:
            return date(year, 2, 28)
        raise


class RewardService:
    async def issue(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        customer_id: UUID,
        reward_definition_id: UUID,
        source_type: str | None = None,
        source_id: UUID | None = None,
        source_key: str | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        now: datetime | None = None,
    ) -> CustomerReward:
        now = now or datetime.now(timezone.utc)
        definition = await session.scalar(
            select(RewardDefinition).where(
                RewardDefinition.id == reward_definition_id,
                RewardDefinition.organization_id == organization_id,
                RewardDefinition.is_active.is_(True),
            )
        )
        if definition is None:
            raise RewardUnavailable("Reward definition is unavailable")
        customer = await session.scalar(
            select(Customer.id).where(
                Customer.id == customer_id,
                Customer.organization_id == organization_id,
                Customer.is_blocked.is_(False),
            )
        )
        if customer is None:
            raise RewardUnavailable("Customer is unavailable")
        if source_key:
            existing = await session.scalar(
                select(CustomerReward.id).where(
                    CustomerReward.organization_id == organization_id,
                    CustomerReward.customer_id == customer_id,
                    CustomerReward.source_key == source_key,
                )
            )
            if existing is not None:
                raise RewardAlreadyIssued("Reward source was already issued")
        valid_from = valid_from or now
        if valid_until is None and definition.default_validity_days is not None:
            valid_until = valid_from + timedelta(days=definition.default_validity_days)
        if valid_until is not None and valid_until <= valid_from:
            raise RewardUnavailable("Reward validity end must be after start")
        status = RewardStatus.ISSUED.value if valid_from > now else RewardStatus.ACTIVE.value
        reward = CustomerReward(
            organization_id=organization_id,
            customer_id=customer_id,
            reward_definition_id=definition.id,
            quantity_remaining=1,
            status=status,
            valid_from=valid_from,
            valid_until=valid_until,
            source_type=source_type,
            source_id=source_id,
            source_key=source_key,
        )
        session.add(reward)
        await session.flush()
        return reward

    async def refresh_status(self, session: AsyncSession, reward: CustomerReward, *, now: datetime | None = None) -> CustomerReward:
        now = now or datetime.now(timezone.utc)
        if reward.status in {RewardStatus.CONSUMED.value, RewardStatus.REVOKED.value, RewardStatus.EXPIRED.value}:
            return reward
        if reward.valid_until is not None and reward.valid_until <= now:
            reward.status = RewardStatus.EXPIRED.value
            reward.quantity_remaining = 0
            reward.expired_at = now
        elif reward.valid_from <= now:
            reward.status = RewardStatus.ACTIVE.value
        else:
            reward.status = RewardStatus.ISSUED.value
        return reward

    async def expire_due(self, session: AsyncSession, *, organization_id: UUID, now: datetime | None = None, limit: int = 500) -> int:
        now = now or datetime.now(timezone.utc)
        rewards = (await session.scalars(
            select(CustomerReward).where(
                CustomerReward.organization_id == organization_id,
                CustomerReward.status.in_([RewardStatus.ISSUED.value, RewardStatus.ACTIVE.value]),
                CustomerReward.valid_until.is_not(None),
                CustomerReward.valid_until <= now,
            ).order_by(CustomerReward.valid_until.asc()).limit(limit).with_for_update(skip_locked=True)
        )).all()
        for reward in rewards:
            await self.refresh_status(session, reward, now=now)
        await session.flush()
        return len(rewards)

    async def activate_due(self, session: AsyncSession, *, organization_id: UUID, now: datetime | None = None, limit: int = 500) -> int:
        now = now or datetime.now(timezone.utc)
        rewards = (await session.scalars(
            select(CustomerReward).where(
                CustomerReward.organization_id == organization_id,
                CustomerReward.status == RewardStatus.ISSUED.value,
                CustomerReward.valid_from <= now,
                (CustomerReward.valid_until.is_(None)) | (CustomerReward.valid_until > now),
            ).order_by(CustomerReward.valid_from.asc()).limit(limit).with_for_update(skip_locked=True)
        )).all()
        for reward in rewards:
            reward.status = RewardStatus.ACTIVE.value
        await session.flush()
        return len(rewards)

    async def issue_birthday_if_due(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        customer_id: UUID,
        reward_definition_id: UUID,
        now: datetime | None = None,
    ) -> CustomerReward | None:
        now = now or datetime.now(timezone.utc)
        customer = await session.scalar(
            select(Customer).where(
                Customer.id == customer_id,
                Customer.organization_id == organization_id,
                Customer.is_blocked.is_(False),
            ).with_for_update()
        )
        if customer is None:
            raise RewardUnavailable("Customer is unavailable")
        birthday = birthday_in_year(customer.birth_date, now.year)
        start_date = birthday - timedelta(days=3)
        end_date = start_date + timedelta(days=7)
        if not (start_date <= now.date() < end_date):
            return None
        source_key = f"birthday:{now.year}"
        existing = await session.scalar(
            select(CustomerReward.id).where(
                CustomerReward.organization_id == organization_id,
                CustomerReward.customer_id == customer_id,
                CustomerReward.source_key == source_key,
            )
        )
        if existing is not None:
            return None
        valid_from = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        valid_until = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
        try:
            return await self.issue(
                session,
                organization_id=organization_id,
                customer_id=customer_id,
                reward_definition_id=reward_definition_id,
                source_type="birthday",
                source_key=source_key,
                valid_from=valid_from,
                valid_until=valid_until,
                now=now,
            )
        except RewardAlreadyIssued:
            return None
