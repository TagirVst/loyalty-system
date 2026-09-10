from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.reward_service import RewardService


@dataclass(frozen=True, slots=True)
class RewardLifecycleResult:
    activated: int
    expired: int


class RewardLifecycleJob:
    def __init__(self) -> None:
        self.rewards = RewardService()

    async def run(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        now: datetime | None = None,
        batch_size: int = 500,
    ) -> RewardLifecycleResult:
        now = now or datetime.now(timezone.utc)
        activated = await self.rewards.activate_due(
            session, organization_id=organization_id, now=now, limit=batch_size
        )
        expired = await self.rewards.expire_due(
            session, organization_id=organization_id, now=now, limit=batch_size
        )
        return RewardLifecycleResult(activated=activated, expired=expired)
