from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import DomainError
from loyalty_v2.db.category_models import SaleCategory
from loyalty_v2.db.milestone_models import MilestoneRewardRule
from loyalty_v2.db.reward_models import Campaign, RewardDefinition


class ConfigNotFound(DomainError):
    code = "CONFIG_NOT_FOUND"


class ConfigInvalid(DomainError):
    code = "CONFIG_INVALID"


class AdminConfigService:
    async def list_categories(self, session: AsyncSession, organization_id: UUID) -> list[SaleCategory]:
        return list((await session.scalars(select(SaleCategory).where(SaleCategory.organization_id == organization_id).order_by(SaleCategory.name.asc()))).all())

    async def create_category(self, session: AsyncSession, *, organization_id: UUID, code: str, name: str, is_active: bool = True) -> SaleCategory:
        item = SaleCategory(organization_id=organization_id, code=self._code(code), name=self._name(name), is_active=is_active)
        session.add(item); await session.flush(); return item

    async def update_category(self, session: AsyncSession, *, organization_id: UUID, category_id: UUID, name: str | None = None, is_active: bool | None = None) -> SaleCategory:
        item = await self._owned(session, SaleCategory, organization_id, category_id)
        if name is not None: item.name = self._name(name)
        if is_active is not None: item.is_active = is_active
        await session.flush(); return item

    async def list_rewards(self, session: AsyncSession, organization_id: UUID) -> list[RewardDefinition]:
        return list((await session.scalars(select(RewardDefinition).where(RewardDefinition.organization_id == organization_id).order_by(RewardDefinition.name.asc()))).all())

    async def create_reward(self, session: AsyncSession, *, organization_id: UUID, code: str, name: str, reward_type: str, config: dict, stackable: bool, default_validity_days: int | None, is_active: bool = True) -> RewardDefinition:
        self._validate_reward(reward_type, config, default_validity_days)
        item = RewardDefinition(organization_id=organization_id, code=self._code(code), name=self._name(name), reward_type=reward_type, config=config, stackable=stackable, default_validity_days=default_validity_days, is_active=is_active)
        session.add(item); await session.flush(); return item

    async def update_reward(self, session: AsyncSession, *, organization_id: UUID, reward_id: UUID, name: str | None = None, config: dict | None = None, stackable: bool | None = None, default_validity_days: int | None = None, set_validity: bool = False, is_active: bool | None = None) -> RewardDefinition:
        item = await self._owned(session, RewardDefinition, organization_id, reward_id)
        new_config = item.config if config is None else config
        new_validity = item.default_validity_days if not set_validity else default_validity_days
        self._validate_reward(item.reward_type, new_config, new_validity)
        if name is not None: item.name = self._name(name)
        if config is not None: item.config = config
        if stackable is not None: item.stackable = stackable
        if set_validity: item.default_validity_days = default_validity_days
        if is_active is not None: item.is_active = is_active
        await session.flush(); return item

    async def list_campaigns(self, session: AsyncSession, organization_id: UUID) -> list[Campaign]:
        return list((await session.scalars(select(Campaign).where(Campaign.organization_id == organization_id).order_by(Campaign.priority.asc(), Campaign.name.asc()))).all())

    async def create_campaign(self, session: AsyncSession, *, organization_id: UUID, code: str, name: str, priority: int, stackable: bool, conditions: dict, effects: dict, starts_at: datetime | None, ends_at: datetime | None, is_active: bool = True) -> Campaign:
        self._validate_campaign(priority, starts_at, ends_at)
        item = Campaign(organization_id=organization_id, code=self._code(code), name=self._name(name), priority=priority, stackable=stackable, conditions=conditions, effects=effects, starts_at=starts_at, ends_at=ends_at, is_active=is_active)
        session.add(item); await session.flush(); return item

    async def update_campaign(self, session: AsyncSession, *, organization_id: UUID, campaign_id: UUID, name: str | None = None, priority: int | None = None, stackable: bool | None = None, conditions: dict | None = None, effects: dict | None = None, starts_at: datetime | None = None, ends_at: datetime | None = None, set_window: bool = False, is_active: bool | None = None) -> Campaign:
        item = await self._owned(session, Campaign, organization_id, campaign_id)
        p = item.priority if priority is None else priority
        s = item.starts_at if not set_window else starts_at
        e = item.ends_at if not set_window else ends_at
        self._validate_campaign(p, s, e)
        if name is not None: item.name = self._name(name)
        if priority is not None: item.priority = priority
        if stackable is not None: item.stackable = stackable
        if conditions is not None: item.conditions = conditions
        if effects is not None: item.effects = effects
        if set_window: item.starts_at, item.ends_at = starts_at, ends_at
        if is_active is not None: item.is_active = is_active
        await session.flush(); return item

    async def list_milestones(self, session: AsyncSession, organization_id: UUID) -> list[MilestoneRewardRule]:
        return list((await session.scalars(select(MilestoneRewardRule).where(MilestoneRewardRule.organization_id == organization_id).order_by(MilestoneRewardRule.name.asc()))).all())

    async def create_milestone(self, session: AsyncSession, *, organization_id: UUID, code: str, name: str, category_id: UUID, threshold_count: int, reward_definition_id: UUID, repeatable: bool, is_active: bool = True) -> MilestoneRewardRule:
        if threshold_count <= 0: raise ConfigInvalid("threshold_count must be positive")
        category = await self._owned(session, SaleCategory, organization_id, category_id)
        reward = await self._owned(session, RewardDefinition, organization_id, reward_definition_id)
        if not category.is_active or not reward.is_active: raise ConfigInvalid("Category and reward definition must be active")
        item = MilestoneRewardRule(organization_id=organization_id, code=self._code(code), name=self._name(name), category_id=category_id, threshold_count=threshold_count, reward_definition_id=reward_definition_id, repeatable=repeatable, is_active=is_active)
        session.add(item); await session.flush(); return item

    async def update_milestone(self, session: AsyncSession, *, organization_id: UUID, rule_id: UUID, name: str | None = None, threshold_count: int | None = None, repeatable: bool | None = None, is_active: bool | None = None) -> MilestoneRewardRule:
        item = await self._owned(session, MilestoneRewardRule, organization_id, rule_id)
        if threshold_count is not None:
            if threshold_count <= 0: raise ConfigInvalid("threshold_count must be positive")
            item.threshold_count = threshold_count
        if name is not None: item.name = self._name(name)
        if repeatable is not None: item.repeatable = repeatable
        if is_active is not None: item.is_active = is_active
        await session.flush(); return item

    async def _owned(self, session: AsyncSession, model, organization_id: UUID, object_id: UUID):
        item = await session.scalar(select(model).where(model.id == object_id, model.organization_id == organization_id))
        if item is None: raise ConfigNotFound("Configuration object not found")
        return item

    @staticmethod
    def _code(value: str) -> str:
        value = value.strip().lower()
        if not value or len(value) > 80 or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in value):
            raise ConfigInvalid("Invalid code")
        return value

    @staticmethod
    def _name(value: str) -> str:
        value = value.strip()
        if not value or len(value) > 160: raise ConfigInvalid("Invalid name")
        return value

    @staticmethod
    def _validate_campaign(priority: int, starts_at: datetime | None, ends_at: datetime | None) -> None:
        if priority < 0: raise ConfigInvalid("priority must be nonnegative")
        if starts_at and ends_at and ends_at <= starts_at: raise ConfigInvalid("Campaign end must be after start")

    @staticmethod
    def _validate_reward(reward_type: str, config: dict, validity_days: int | None) -> None:
        allowed = {"fixed_discount", "percent_discount", "free_item_value", "free_category_item", "category_discount"}
        if reward_type not in allowed: raise ConfigInvalid("Unsupported reward_type")
        if validity_days is not None and validity_days <= 0: raise ConfigInvalid("default_validity_days must be positive")
        if not isinstance(config, dict): raise ConfigInvalid("config must be an object")
