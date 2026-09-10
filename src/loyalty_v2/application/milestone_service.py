from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.reward_service import RewardService, RewardStatus
from loyalty_v2.db.category_models import SaleCategory
from loyalty_v2.db.milestone_models import CustomerCategoryCounter, MilestoneIssuance, MilestoneRewardRule
from loyalty_v2.db.reward_models import CustomerReward


@dataclass(frozen=True, slots=True)
class MilestoneResult:
    issued_reward_ids: tuple[UUID, ...]


class MilestoneService:
    def __init__(self) -> None:
        self.rewards = RewardService()

    async def apply_sale(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, order_id: UUID, category_counts: dict[str, int]) -> MilestoneResult:
        issued: list[UUID] = []
        for code, count in sorted(category_counts.items()):
            if count <= 0:
                continue
            category = await session.scalar(select(SaleCategory).where(SaleCategory.organization_id == organization_id, SaleCategory.code == code, SaleCategory.is_active.is_(True)))
            if category is None:
                continue
            counter = await session.scalar(select(CustomerCategoryCounter).where(CustomerCategoryCounter.organization_id == organization_id, CustomerCategoryCounter.customer_id == customer_id, CustomerCategoryCounter.category_id == category.id).with_for_update())
            if counter is None:
                counter = CustomerCategoryCounter(organization_id=organization_id, customer_id=customer_id, category_id=category.id, lifetime_count=0, net_count=0)
                session.add(counter)
                await session.flush()
            before = counter.net_count
            counter.lifetime_count += count
            counter.net_count += count
            counter.version += 1
            rules = (await session.scalars(select(MilestoneRewardRule).where(MilestoneRewardRule.organization_id == organization_id, MilestoneRewardRule.category_id == category.id, MilestoneRewardRule.is_active.is_(True)).order_by(MilestoneRewardRule.id.asc()))).all()
            for rule in rules:
                first = before // rule.threshold_count + 1
                last = counter.net_count // rule.threshold_count
                if not rule.repeatable:
                    first, last = 1, min(last, 1)
                for milestone_number in range(first, last + 1):
                    existing = await session.scalar(select(MilestoneIssuance).where(MilestoneIssuance.organization_id == organization_id, MilestoneIssuance.customer_id == customer_id, MilestoneIssuance.rule_id == rule.id, MilestoneIssuance.milestone_number == milestone_number).with_for_update())
                    if existing:
                        if existing.revoked:
                            reward = await session.get(CustomerReward, existing.customer_reward_id)
                            if reward is not None and reward.status == RewardStatus.REVOKED.value and reward.consumed_at is None:
                                now = datetime.now(timezone.utc)
                                if reward.valid_until is None or reward.valid_until > now:
                                    reward.status = RewardStatus.ACTIVE.value if reward.valid_from <= now else RewardStatus.ISSUED.value
                                    reward.quantity_remaining = 1
                                    reward.revoked_at = None
                                    existing.revoked = False
                                    issued.append(reward.id)
                        continue
                    reward = await self.rewards.issue(session, organization_id=organization_id, customer_id=customer_id, reward_definition_id=rule.reward_definition_id, source_type="milestone", source_id=rule.id)
                    session.add(MilestoneIssuance(organization_id=organization_id, customer_id=customer_id, rule_id=rule.id, milestone_number=milestone_number, customer_reward_id=reward.id, source_order_id=order_id))
                    issued.append(reward.id)
        await session.flush()
        return MilestoneResult(tuple(issued))

    async def apply_refund(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, order_id: UUID, category_counts: dict[str, int]) -> None:
        del order_id
        now = datetime.now(timezone.utc)
        for code, count in sorted(category_counts.items()):
            if count <= 0:
                continue
            category = await session.scalar(select(SaleCategory).where(SaleCategory.organization_id == organization_id, SaleCategory.code == code))
            if category is None:
                continue
            counter = await session.scalar(select(CustomerCategoryCounter).where(CustomerCategoryCounter.organization_id == organization_id, CustomerCategoryCounter.customer_id == customer_id, CustomerCategoryCounter.category_id == category.id).with_for_update())
            if counter is None:
                continue
            counter.net_count = max(0, counter.net_count - count)
            counter.version += 1
            rules = (await session.scalars(select(MilestoneRewardRule).where(MilestoneRewardRule.organization_id == organization_id, MilestoneRewardRule.category_id == category.id))).all()
            for rule in rules:
                issuances = (await session.scalars(select(MilestoneIssuance).where(MilestoneIssuance.organization_id == organization_id, MilestoneIssuance.customer_id == customer_id, MilestoneIssuance.rule_id == rule.id, MilestoneIssuance.revoked.is_(False)).with_for_update())).all()
                for issuance in issuances:
                    if counter.net_count >= issuance.milestone_number * rule.threshold_count:
                        continue
                    reward = await session.get(CustomerReward, issuance.customer_reward_id)
                    if reward is not None and reward.status in {RewardStatus.ACTIVE.value, RewardStatus.ISSUED.value} and reward.quantity_remaining > 0:
                        reward.status = RewardStatus.REVOKED.value
                        reward.quantity_remaining = 0
                        reward.revoked_at = now
                    issuance.revoked = True
        await session.flush()
