from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import DomainError
from loyalty_v2.db.models import Customer
from loyalty_v2.db.reward_models import CustomerReward, RewardDefinition


class RewardUnavailable(DomainError):
    code = "REWARD_UNAVAILABLE"


class RewardAlreadyIssued(DomainError):
    code = "REWARD_ALREADY_ISSUED"


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
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> CustomerReward:
        definition = await session.scalar(
            select(RewardDefinition).where(
                RewardDefinition.id == reward_definition_id,
                RewardDefinition.organization_id == organization_id,
                RewardDefinition.is_active.is_(True),
            )
        )
        if definition is None:
            raise RewardUnavailable("Reward definition is unavailable")

        now = datetime.now(timezone.utc)
        valid_from = valid_from or now
        if valid_until is None and definition.default_validity_days is not None:
            valid_until = valid_from + timedelta(days=definition.default_validity_days)

        reward = CustomerReward(
            organization_id=organization_id,
            customer_id=customer_id,
            reward_definition_id=definition.id,
            quantity_remaining=1,
            status="active",
            valid_from=valid_from,
            valid_until=valid_until,
            source_type=source_type,
            source_id=source_id,
        )
        session.add(reward)
        await session.flush()
        return reward

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
            )
        )
        if customer is None:
            raise RewardUnavailable("Customer is unavailable")

        birthday_this_year = customer.birth_date.replace(year=now.year)
        start_date = birthday_this_year - timedelta(days=3)
        end_date = start_date + timedelta(days=7)
        if not (start_date <= now.date() < end_date):
            return None

        source_marker = f"birthday:{now.year}"
        existing = await session.scalar(
            select(CustomerReward.id).where(
                CustomerReward.organization_id == organization_id,
                CustomerReward.customer_id == customer_id,
                CustomerReward.reward_definition_id == reward_definition_id,
                CustomerReward.source_type == source_marker,
            )
        )
        if existing is not None:
            return None

        valid_from = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        valid_until = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc)
        return await self.issue(
            session,
            organization_id=organization_id,
            customer_id=customer_id,
            reward_definition_id=reward_definition_id,
            source_type=source_marker,
            valid_from=valid_from,
            valid_until=valid_until,
        )
