from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import DomainError
from loyalty_v2.db.category_models import SaleCategory
from loyalty_v2.db.milestone_models import MilestoneRewardRule
from loyalty_v2.db.reward_models import Campaign, RewardDefinition

class ConfigNotFound(DomainError): code = "CONFIG_NOT_FOUND"
class ConfigInvalid(DomainError): code = "CONFIG_INVALID"

class AdminConfigService:
    async def list_categories(self, session, organization_id): return list((await session.scalars(select(SaleCategory).where(SaleCategory.organization_id==organization_id).order_by(SaleCategory.name.asc()))).all())
    async def create_category(self, session, *, organization_id, code, name, is_active=True):
        item=SaleCategory(organization_id=organization_id,code=self._code(code),name=self._name(name),is_active=is_active); session.add(item); await session.flush(); return item
    async def update_category(self, session, *, organization_id, category_id, name=None, is_active=None):
        item=await self._owned(session,SaleCategory,organization_id,category_id)
        if name is not None: item.name=self._name(name)
        if is_active is not None: item.is_active=is_active
        await session.flush(); return item

    async def list_rewards(self, session, organization_id): return list((await session.scalars(select(RewardDefinition).where(RewardDefinition.organization_id==organization_id).order_by(RewardDefinition.name.asc()))).all())
    async def create_reward(self, session, *, organization_id, code, name, reward_type, config, stackable, default_validity_days, is_active=True):
        self._validate_reward(reward_type,config,default_validity_days); item=RewardDefinition(organization_id=organization_id,code=self._code(code),name=self._name(name),reward_type=reward_type,config=config,stackable=stackable,default_validity_days=default_validity_days,config_version=1,is_active=is_active); session.add(item); await session.flush(); return item
    async def update_reward(self, session, *, organization_id, reward_id, name=None, config=None, stackable=None, default_validity_days=None, set_validity=False, is_active=None):
        item=await self._owned(session,RewardDefinition,organization_id,reward_id); new_config=item.config if config is None else config; new_validity=item.default_validity_days if not set_validity else default_validity_days; self._validate_reward(item.reward_type,new_config,new_validity)
        semantic_changed = config is not None or stackable is not None or set_validity
        if name is not None: item.name=self._name(name)
        if config is not None: item.config=config
        if stackable is not None: item.stackable=stackable
        if set_validity: item.default_validity_days=default_validity_days
        if semantic_changed: item.config_version += 1
        if is_active is not None: item.is_active=is_active
        await session.flush(); return item

    async def list_campaigns(self, session, organization_id): return list((await session.scalars(select(Campaign).where(Campaign.organization_id==organization_id).order_by(Campaign.priority.asc(),Campaign.name.asc()))).all())
    async def create_campaign(self, session, *, organization_id, code, name, priority, stackable, conditions, effects, starts_at, ends_at, is_active=True):
        self._validate_campaign(priority,starts_at,ends_at); item=Campaign(organization_id=organization_id,code=self._code(code),name=self._name(name),priority=priority,stackable=stackable,conditions=conditions,effects=effects,config_version=1,starts_at=starts_at,ends_at=ends_at,is_active=is_active); session.add(item); await session.flush(); return item
    async def update_campaign(self, session, *, organization_id, campaign_id, name=None, priority=None, stackable=None, conditions=None, effects=None, starts_at=None, ends_at=None, set_window=False, is_active=None):
        item=await self._owned(session,Campaign,organization_id,campaign_id); p=item.priority if priority is None else priority; s=item.starts_at if not set_window else starts_at; e=item.ends_at if not set_window else ends_at; self._validate_campaign(p,s,e)
        semantic_changed = priority is not None or stackable is not None or conditions is not None or effects is not None or set_window
        if name is not None: item.name=self._name(name)
        if priority is not None: item.priority=priority
        if stackable is not None: item.stackable=stackable
        if conditions is not None: item.conditions=conditions
        if effects is not None: item.effects=effects
        if set_window: item.starts_at,item.ends_at=starts_at,ends_at
        if semantic_changed: item.config_version += 1
        if is_active is not None: item.is_active=is_active
        await session.flush(); return item

    async def list_milestones(self, session, organization_id): return list((await session.scalars(select(MilestoneRewardRule).where(MilestoneRewardRule.organization_id==organization_id).order_by(MilestoneRewardRule.name.asc()))).all())
    async def create_milestone(self, session, *, organization_id, code, name, category_id, threshold_count, reward_definition_id, repeatable, is_active=True):
        if threshold_count<=0: raise ConfigInvalid("threshold_count must be positive")
        category=await self._owned(session,SaleCategory,organization_id,category_id); reward=await self._owned(session,RewardDefinition,organization_id,reward_definition_id)
        if not category.is_active or not reward.is_active: raise ConfigInvalid("Category and reward definition must be active")
        item=MilestoneRewardRule(organization_id=organization_id,code=self._code(code),name=self._name(name),category_id=category_id,threshold_count=threshold_count,reward_definition_id=reward_definition_id,repeatable=repeatable,config_version=1,is_active=is_active); session.add(item); await session.flush(); return item
    async def update_milestone(self, session, *, organization_id, rule_id, name=None, threshold_count=None, repeatable=None, is_active=None):
        item=await self._owned(session,MilestoneRewardRule,organization_id,rule_id); semantic_changed=False
        if threshold_count is not None:
            if threshold_count<=0: raise ConfigInvalid("threshold_count must be positive")
            if threshold_count != item.threshold_count: item.threshold_count=threshold_count; semantic_changed=True
        if name is not None: item.name=self._name(name)
        if repeatable is not None and repeatable != item.repeatable: item.repeatable=repeatable; semantic_changed=True
        if semantic_changed: item.config_version += 1
        if is_active is not None: item.is_active=is_active
        await session.flush(); return item

    async def _owned(self, session, model, organization_id, object_id):
        item=await session.scalar(select(model).where(model.id==object_id,model.organization_id==organization_id))
        if item is None: raise ConfigNotFound("Configuration object not found")
        return item
    @staticmethod
    def _code(value):
        value=value.strip().lower()
        if not value or len(value)>80 or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in value): raise ConfigInvalid("Invalid code")
        return value
    @staticmethod
    def _name(value):
        value=value.strip()
        if not value or len(value)>160: raise ConfigInvalid("Invalid name")
        return value
    @staticmethod
    def _validate_campaign(priority,starts_at,ends_at):
        if priority<0: raise ConfigInvalid("priority must be nonnegative")
        if starts_at and ends_at and ends_at<=starts_at: raise ConfigInvalid("Campaign end must be after start")
    @staticmethod
    def _validate_reward(reward_type,config,validity_days):
        allowed={"fixed_discount","percent_discount","free_item_value","free_category_item","category_discount"}
        if reward_type not in allowed: raise ConfigInvalid("Unsupported reward_type")
        if validity_days is not None and validity_days<=0: raise ConfigInvalid("default_validity_days must be positive")
        if not isinstance(config,dict): raise ConfigInvalid("config must be an object")
