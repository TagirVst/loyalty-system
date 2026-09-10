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

    async def run(self, session: AsyncSession, *, organization_id: UUID, reward_definition_id: UUID, now: datetime | None = None, limit: int = 1000) -> BirthdayJobResult:
        now = now or datetime.now(timezone.utc)
        scanned = issued = 0
        after_id: UUID | None = None
        while True:
            stmt = select(Customer.id).where(Customer.organization_id == organization_id, Customer.is_blocked.is_(False))
            if after_id is not None:
                stmt = stmt.where(Customer.id > after_id)
            batch = (await session.scalars(stmt.order_by(Customer.id.asc()).limit(limit))).all()
            if not batch:
                break
            for customer_id in batch:
                reward = await self.rewards.issue_birthday_if_due(session, organization_id=organization_id, customer_id=customer_id, reward_definition_id=reward_definition_id, now=now)
                scanned += 1
                if reward is not None:
                    issued += 1
            after_id = batch[-1]
            if len(batch) < limit:
                break
        return BirthdayJobResult(scanned=scanned, issued=issued)
