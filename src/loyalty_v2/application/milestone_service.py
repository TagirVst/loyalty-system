from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.reward_service import RewardService
from loyalty_v2.db.category_models import SaleCategory
from loyalty_v2.db.milestone_models import CustomerCategoryCounter, MilestoneIssuance, MilestoneRewardRule
from loyalty_v2.db.reward_models import CustomerReward


@dataclass(frozen=True, slots=True)
class MilestoneResult:
    issued_reward_ids: tuple[UUID, ...]


class MilestoneService:
    def __init__(self) -> None:
        self.rewards = RewardService()

    async def apply_sale(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        customer_id: UUID,
        order_id: UUID,
        category_counts: dict[str, int],
    ) -> MilestoneResult:
        issued: list[UUID] = []
        for code, count in sorted(category_counts.items()):
            if count <= 0:
                continue
            category = await session.scalar(select(SaleCategory).where(
                SaleCategory.organization_id == organization_id,
                SaleCategory.code == code,
                SaleCategory.is_active.is_(True),
            ))
            if category is None:
                continue
            counter = await session.scalar(select(CustomerCategoryCounter).where(
                CustomerCategoryCounter.organization_id == organization_id,
                CustomerCategoryCounter.customer_id == customer_id,
                CustomerCategoryCounter.category_id == category.id,
            ).with_for_update())
            if counter is None:
                counter = CustomerCategoryCounter(
                    organization_id=organization_id,
                    customer_id=customer_id,
                    category_id=category.id,
                    lifetime_count=0,
                    net_count=0,
                )
                session.add(counter)
                await session.flush()
            before = counter.net_count
            counter.lifetime_count += count
            counter.net_count += count
            counter.version += 1

            rules = (await session.scalars(select(MilestoneRewardRule).where(
                MilestoneRewardRule.organization_id == organization_id,
                MilestoneRewardRule.category_id == category.id,
                MilestoneRewardRule.is_active.is_(True),
            ).order_by(MilestoneRewardRule.id.asc()))).all()
            for rule in rules:
                first = before // rule.threshold_count + 1
                last = counter.net_count // rule.threshold_count
                if not rule.repeatable:
                    first, last = 1, min(last, 1)
                for milestone_number in range(first, last + 1):
                    existing = await session.scalar(select(MilestoneIssuance.id).where(
                        MilestoneIssuance.organization_id == organization_id,
                        MilestoneIssuance.customer_id == customer_id,
                        MilestoneIssuance.rule_id == rule.id,
                        MilestoneIssuance.milestone_number == milestone_number,
                    ))
                    if existing:
                        continue
                    reward = await self.rewards.issue(
                        session,
                        organization_id=organization_id,
                        customer_id=customer_id,
                        reward_definition_id=rule.reward_definition_id,
                        source_type="milestone",
                        source_id=rule.id,
                    )
                    session.add(MilestoneIssuance(
                        organization_id=organization_id,
                        customer_id=customer_id,
                        rule_id=rule.id,
                        milestone_number=milestone_number,
                        customer_reward_id=reward.id,
                        source_order_id=order_id,
                    ))
                    issued.append(reward.id)
        await session.flush()
        return MilestoneResult(tuple(issued))

    async def apply_refund(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        customer_id: UUID,
        order_id: UUID,
        category_counts: dict[str, int],
    ) -> None:
        for code, count in sorted(category_counts.items()):
            if count <= 0:
                continue
            category = await session.scalar(select(SaleCategory).where(
                SaleCategory.organization_id == organization_id,
                SaleCategory.code == code,
            ))
            if category is None:
                continue
            counter = await session.scalar(select(CustomerCategoryCounter).where(
                CustomerCategoryCounter.organization_id == organization_id,
                CustomerCategoryCounter.customer_id == customer_id,
                CustomerCategoryCounter.category_id == category.id,
            ).with_for_update())
            if counter is None:
                continue
            counter.net_count = max(0, counter.net_count - count)
            counter.version += 1

        issuances = (await session.scalars(select(MilestoneIssuance).where(
            MilestoneIssuance.organization_id == organization_id,
            MilestoneIssuance.customer_id == customer_id,
            MilestoneIssuance.source_order_id == order_id,
            MilestoneIssuance.revoked.is_(False),
        ).with_for_update())).all()
        for issuance in issuances:
            reward = await session.get(CustomerReward, issuance.customer_reward_id)
            if reward is not None and reward.status == "active" and reward.quantity_remaining > 0:
                reward.status = "revoked"
                reward.quantity_remaining = 0
            issuance.revoked = True
        await session.flush()
