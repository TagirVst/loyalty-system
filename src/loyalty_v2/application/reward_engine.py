from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.segment_service import SegmentService
from loyalty_v2.db.reward_models import Campaign, CustomerReward, RewardDefinition

@dataclass(frozen=True, slots=True)
class RewardEffect:
    customer_reward_id: UUID
    reward_definition_version: int
    discount_minor: int

@dataclass(frozen=True, slots=True)
class CampaignEffect:
    campaign_id: UUID
    campaign_version: int
    discount_minor: int
    cashback_multiplier: int

@dataclass(frozen=True, slots=True)
class LoyaltyEffects:
    reward_effects: tuple[RewardEffect, ...]
    campaign_effects: tuple[CampaignEffect, ...]
    total_discount_minor: int
    cashback_multiplier: int

class RewardCampaignEngine:
    def __init__(self) -> None: self.segments = SegmentService()

    async def resolve(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, gross_amount_minor: int, selected_reward_ids: list[UUID] | None = None, category_counts: dict[str,int] | None = None, now: datetime | None = None) -> LoyaltyEffects:
        now = now or datetime.now(timezone.utc)
        categories={str(k):max(int(v),0) for k,v in (category_counts or {}).items() if int(v)>0}; reward_categories=dict(categories)
        reward_effects:list[RewardEffect]=[]; campaign_effects:list[CampaignEffect]=[]; total_discount=0; cashback_multiplier=1
        if selected_reward_ids:
            rows=(await session.execute(select(CustomerReward,RewardDefinition).join(RewardDefinition,RewardDefinition.id==CustomerReward.reward_definition_id).where(CustomerReward.organization_id==organization_id,CustomerReward.customer_id==customer_id,CustomerReward.id.in_(selected_reward_ids),CustomerReward.status=="active",CustomerReward.quantity_remaining>0).order_by(CustomerReward.id.asc()).with_for_update(of=CustomerReward))).all()
            if {cr.id for cr,_ in rows} != set(selected_reward_ids): raise ValueError("One or more selected rewards are unavailable")
            if any(not bool((cr.definition_snapshot or {}).get("stackable", d.stackable)) for cr,d in rows) and len(rows)>1: raise ValueError("Selected rewards are not stackable")
            for cr,d in rows:
                if cr.valid_from>now: raise ValueError("Reward is not active yet")
                if cr.valid_until and cr.valid_until<=now: raise ValueError("Reward has expired")
                snapshot=cr.definition_snapshot or {"reward_type":d.reward_type,"config":d.config,"stackable":d.stackable}
                discount=self._reward_discount_snapshot(snapshot,gross_amount_minor,reward_categories)
                reward_effects.append(RewardEffect(cr.id,cr.reward_definition_version,discount)); total_discount+=discount
        campaigns=(await session.scalars(select(Campaign).where(Campaign.organization_id==organization_id,Campaign.is_active.is_(True),(Campaign.starts_at.is_(None)|(Campaign.starts_at<=now)),(Campaign.ends_at.is_(None)|(Campaign.ends_at>=now))).order_by(Campaign.priority.asc(),Campaign.id.asc()))).all()
        needs_segments=any((c.conditions or {}).get("segment_codes") for c in campaigns); segment_codes=await self.segments.active_codes_for_customer(session,organization_id=organization_id,customer_id=customer_id,now=now) if needs_segments else set()
        applicable=[c for c in campaigns if self._campaign_matches(c,gross_amount_minor,categories,segment_codes)]; resolved:list[Campaign]=[]
        for campaign in applicable:
            if not resolved:
                resolved.append(campaign)
                if not campaign.stackable: break
            elif campaign.stackable: resolved.append(campaign)
        for campaign in resolved:
            effect=campaign.effects or {}; discount=max(int(effect.get("discount_minor",0) or 0),0); percent=max(min(int(effect.get("discount_percent",0) or 0),100),0)
            if percent: discount += gross_amount_minor*percent//100
            category_code=effect.get("category_code"); per_item_minor=max(int(effect.get("category_discount_per_item_minor",0) or 0),0)
            if category_code and per_item_minor: discount += categories.get(str(category_code),0)*per_item_minor
            multiplier=max(int(effect.get("cashback_multiplier",1) or 1),1)
            campaign_effects.append(CampaignEffect(campaign.id,campaign.config_version,discount,multiplier)); total_discount+=discount; cashback_multiplier*=multiplier
        return LoyaltyEffects(tuple(reward_effects),tuple(campaign_effects),min(total_discount,gross_amount_minor),cashback_multiplier)

    @staticmethod
    def _reward_discount_snapshot(snapshot: dict, gross_amount_minor:int, categories:dict[str,int] | None = None) -> int:
        categories = categories if categories is not None else {}
        config=snapshot.get("config") or {}; t=str(snapshot.get("reward_type") or "")
        if t=="fixed_discount": return min(max(int(config.get("amount_minor",0) or 0),0),gross_amount_minor)
        if t=="percent_discount": return gross_amount_minor*max(min(int(config.get("percent",0) or 0),100),0)//100
        if t=="free_item_value": return min(max(int(config.get("value_minor",0) or 0),0),gross_amount_minor)
        if t=="free_category_item":
            code=str(config.get("category_code") or ""); count=categories.get(code,0)
            if count<=0: raise ValueError("Required reward category quantity is not available in order")
            categories[code]=count-1; return min(max(int(config.get("value_minor",0) or 0),0),gross_amount_minor)
        if t=="category_discount":
            code=str(config.get("category_code") or ""); per_item=max(int(config.get("amount_per_item_minor",0) or 0),0); return min(categories.get(code,0)*per_item,gross_amount_minor)
        return 0

    @staticmethod
    def _reward_discount(definition: RewardDefinition, gross_amount_minor:int, categories:dict[str,int] | None = None) -> int:
        return RewardCampaignEngine._reward_discount_snapshot({"reward_type":definition.reward_type,"config":definition.config},gross_amount_minor,categories)

    @staticmethod
    def _campaign_matches(campaign: Campaign, gross_amount_minor:int, categories:dict[str,int] | None = None, customer_segment_codes:set[str]|None=None) -> bool:
        categories = categories or {}
        c=campaign.conditions or {}; minimum=int(c.get("minimum_spend_minor",0) or 0); maximum=c.get("maximum_spend_minor")
        if gross_amount_minor<minimum or (maximum is not None and gross_amount_minor>int(maximum)): return False
        code=c.get("category_code")
        if code is not None and categories.get(str(code),0)<max(int(c.get("minimum_category_count",1) or 1),1): return False
        for key,value in (c.get("category_counts") or {}).items():
            if categories.get(str(key),0)<int(value): return False
        required_segments={str(x) for x in (c.get("segment_codes") or [])}
        if required_segments and not required_segments.issubset(customer_segment_codes or set()): return False
        return True
