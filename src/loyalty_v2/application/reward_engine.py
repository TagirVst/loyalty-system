from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.db.reward_models import Campaign, CustomerReward, RewardDefinition


@dataclass(frozen=True, slots=True)
class RewardEffect:
    customer_reward_id: UUID
    discount_minor: int


@dataclass(frozen=True, slots=True)
class CampaignEffect:
    campaign_id: UUID
    discount_minor: int
    cashback_multiplier: int


@dataclass(frozen=True, slots=True)
class LoyaltyEffects:
    reward_effects: tuple[RewardEffect, ...]
    campaign_effects: tuple[CampaignEffect, ...]
    total_discount_minor: int
    cashback_multiplier: int


class RewardCampaignEngine:
    async def resolve(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        customer_id: UUID,
        gross_amount_minor: int,
        selected_reward_ids: list[UUID] | None = None,
        now: datetime | None = None,
    ) -> LoyaltyEffects:
        now = now or datetime.now(timezone.utc)
        reward_effects: list[RewardEffect] = []
        campaign_effects: list[CampaignEffect] = []
        total_discount = 0
        cashback_multiplier = 1

        if selected_reward_ids:
            rows = (
                await session.execute(
                    select(CustomerReward, RewardDefinition)
                    .join(RewardDefinition, RewardDefinition.id == CustomerReward.reward_definition_id)
                    .where(
                        CustomerReward.organization_id == organization_id,
                        CustomerReward.customer_id == customer_id,
                        CustomerReward.id.in_(selected_reward_ids),
                        CustomerReward.status == "active",
                        CustomerReward.quantity_remaining > 0,
                        RewardDefinition.is_active.is_(True),
                    )
                    .with_for_update(of=CustomerReward)
                )
            ).all()
            found = {customer_reward.id for customer_reward, _ in rows}
            if found != set(selected_reward_ids):
                raise ValueError("One or more selected rewards are unavailable")

            definitions = [definition for _, definition in rows]
            non_stackable = [definition for definition in definitions if not definition.stackable]
            if non_stackable and len(definitions) > 1:
                raise ValueError("Selected rewards are not stackable")

            for customer_reward, definition in rows:
                if customer_reward.valid_from > now:
                    raise ValueError("Reward is not active yet")
                if customer_reward.valid_until and customer_reward.valid_until < now:
                    raise ValueError("Reward has expired")
                discount = self._reward_discount(definition, gross_amount_minor)
                reward_effects.append(RewardEffect(customer_reward.id, discount))
                total_discount += discount

        campaigns = (
            await session.scalars(
                select(Campaign)
                .where(
                    Campaign.organization_id == organization_id,
                    Campaign.is_active.is_(True),
                    (Campaign.starts_at.is_(None) | (Campaign.starts_at <= now)),
                    (Campaign.ends_at.is_(None) | (Campaign.ends_at >= now)),
                )
                .order_by(Campaign.priority.asc(), Campaign.id.asc())
            )
        ).all()

        applicable = [c for c in campaigns if self._campaign_matches(c, gross_amount_minor)]
        resolved: list[Campaign] = []
        for campaign in applicable:
            if not resolved:
                resolved.append(campaign)
                if not campaign.stackable:
                    break
                continue
            if not campaign.stackable:
                resolved = [campaign]
                break
            if all(item.stackable for item in resolved):
                resolved.append(campaign)

        for campaign in resolved:
            effect = campaign.effects or {}
            discount = int(effect.get("discount_minor", 0) or 0)
            percent = int(effect.get("discount_percent", 0) or 0)
            if percent > 0:
                discount += gross_amount_minor * percent // 100
            multiplier = int(effect.get("cashback_multiplier", 1) or 1)
            multiplier = max(multiplier, 1)
            campaign_effects.append(CampaignEffect(campaign.id, discount, multiplier))
            total_discount += discount
            cashback_multiplier *= multiplier

        total_discount = min(total_discount, gross_amount_minor)
        return LoyaltyEffects(tuple(reward_effects), tuple(campaign_effects), total_discount, cashback_multiplier)

    @staticmethod
    def _reward_discount(definition: RewardDefinition, gross_amount_minor: int) -> int:
        config = definition.config or {}
        if definition.reward_type == "fixed_discount":
            return min(max(int(config.get("amount_minor", 0) or 0), 0), gross_amount_minor)
        if definition.reward_type == "percent_discount":
            percent = max(min(int(config.get("percent", 0) or 0), 100), 0)
            return gross_amount_minor * percent // 100
        if definition.reward_type == "free_item_value":
            return min(max(int(config.get("value_minor", 0) or 0), 0), gross_amount_minor)
        return 0

    @staticmethod
    def _campaign_matches(campaign: Campaign, gross_amount_minor: int) -> bool:
        conditions = campaign.conditions or {}
        minimum = int(conditions.get("minimum_spend_minor", 0) or 0)
        maximum_raw = conditions.get("maximum_spend_minor")
        if gross_amount_minor < minimum:
            return False
        if maximum_raw is not None and gross_amount_minor > int(maximum_raw):
            return False
        return True
