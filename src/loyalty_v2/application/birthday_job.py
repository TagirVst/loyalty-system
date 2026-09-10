from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.reward_service import RewardService
from loyalty_v2.db.models import Customer


@dataclass(frozen=True, slots=True)
class BirthdayJobResult:
    scanned: int
    issued: int


class BirthdayRewardJob:
    def __init__(self) -> None:
        self.rewards = RewardService()

    async def run(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        reward_definition_id: UUID,
        now: datetime | None = None,
        limit: int = 1000,
    ) -> BirthdayJobResult:
        now = now or datetime.now(timezone.utc)
        customer_ids = (await session.scalars(
            select(Customer.id).where(
                Customer.organization_id == organization_id,
                Customer.is_blocked.is_(False),
            ).order_by(Customer.id.asc()).limit(limit)
        )).all()
        issued = 0
        for customer_id in customer_ids:
            reward = await self.rewards.issue_birthday_if_due(
                session,
                organization_id=organization_id,
                customer_id=customer_id,
                reward_definition_id=reward_definition_id,
                now=now,
            )
            if reward is not None:
                issued += 1
        return BirthdayJobResult(scanned=len(customer_ids), issued=issued)
