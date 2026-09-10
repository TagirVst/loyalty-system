from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.admin_config_service import AdminConfigService
from loyalty_v2.application.auth_service import Permission
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/api/v2/admin/config", tags=["admin-config"])
principals = PrincipalService()
configs = AdminConfigService()


class AdminRequest(BaseModel):
    staff_session_id: UUID


class CreateCategoryRequest(AdminRequest):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    is_active: bool = True


class UpdateCategoryRequest(AdminRequest):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    is_active: bool | None = None


class CreateRewardRequest(AdminRequest):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    reward_type: str = Field(min_length=1, max_length=32)
    config: dict = Field(default_factory=dict)
    stackable: bool = True
    default_validity_days: int | None = Field(default=None, gt=0)
    is_active: bool = True


class UpdateRewardRequest(AdminRequest):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    config: dict | None = None
    stackable: bool | None = None
    default_validity_days: int | None = Field(default=None, gt=0)
    set_validity: bool = False
    is_active: bool | None = None


class CreateCampaignRequest(AdminRequest):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    priority: int = Field(default=100, ge=0)
    stackable: bool = True
    conditions: dict = Field(default_factory=dict)
    effects: dict = Field(default_factory=dict)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True


class UpdateCampaignRequest(AdminRequest):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    priority: int | None = Field(default=None, ge=0)
    stackable: bool | None = None
    conditions: dict | None = None
    effects: dict | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    set_window: bool = False
    is_active: bool | None = None


class CreateMilestoneRequest(AdminRequest):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    category_id: UUID
    threshold_count: int = Field(gt=0)
    reward_definition_id: UUID
    repeatable: bool = True
    is_active: bool = True


class UpdateMilestoneRequest(AdminRequest):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    threshold_count: int | None = Field(default=None, gt=0)
    repeatable: bool | None = None
    is_active: bool | None = None


async def _admin(session: AsyncSession, staff_session_id: UUID):
    principal = await principals.staff(session, staff_session_id=staff_session_id)
    principal.require(Permission.ADMIN_ACCESS)
    return principal


def _domain_error(exc: DomainError) -> HTTPException:
    code = exc.code
    if code == "PERMISSION_DENIED": http_status = status.HTTP_403_FORBIDDEN
    elif code == "STAFF_SESSION_INVALID": http_status = status.HTTP_401_UNAUTHORIZED
    elif code == "CONFIG_NOT_FOUND": http_status = status.HTTP_404_NOT_FOUND
    else: http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(http_status, detail={"code": code, "message": str(exc)})


def _conflict(exc: IntegrityError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail={"code": "CONFIG_CONFLICT", "message": "Configuration code or relation already exists"})


def _category(x): return {"id": x.id, "code": x.code, "name": x.name, "is_active": x.is_active}
def _reward(x): return {"id": x.id, "code": x.code, "name": x.name, "reward_type": x.reward_type, "config": x.config, "stackable": x.stackable, "default_validity_days": x.default_validity_days, "is_active": x.is_active}
def _campaign(x): return {"id": x.id, "code": x.code, "name": x.name, "priority": x.priority, "stackable": x.stackable, "conditions": x.conditions, "effects": x.effects, "starts_at": x.starts_at, "ends_at": x.ends_at, "is_active": x.is_active}
def _milestone(x): return {"id": x.id, "code": x.code, "name": x.name, "category_id": x.category_id, "threshold_count": x.threshold_count, "reward_definition_id": x.reward_definition_id, "repeatable": x.repeatable, "is_active": x.is_active}


@router.get("/categories")
async def list_categories(staff_session_id: UUID, session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        principal = await _admin(session, staff_session_id)
        return [_category(x) for x in await configs.list_categories(session, principal.organization_id)]
    except DomainError as exc: raise _domain_error(exc) from exc


@router.post("/categories", status_code=201)
async def create_category(body: CreateCategoryRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            principal = await _admin(session, body.staff_session_id)
            item = await configs.create_category(session, organization_id=principal.organization_id, code=body.code, name=body.name, is_active=body.is_active)
        return _category(item)
    except DomainError as exc: raise _domain_error(exc) from exc
    except IntegrityError as exc: raise _conflict(exc) from exc


@router.patch("/categories/{category_id}")
async def update_category(category_id: UUID, body: UpdateCategoryRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            principal = await _admin(session, body.staff_session_id)
            item = await configs.update_category(session, organization_id=principal.organization_id, category_id=category_id, name=body.name, is_active=body.is_active)
        return _category(item)
    except DomainError as exc: raise _domain_error(exc) from exc


@router.get("/rewards")
async def list_rewards(staff_session_id: UUID, session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        principal = await _admin(session, staff_session_id)
        return [_reward(x) for x in await configs.list_rewards(session, principal.organization_id)]
    except DomainError as exc: raise _domain_error(exc) from exc


@router.post("/rewards", status_code=201)
async def create_reward(body: CreateRewardRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await configs.create_reward(session, organization_id=p.organization_id, code=body.code, name=body.name, reward_type=body.reward_type, config=body.config, stackable=body.stackable, default_validity_days=body.default_validity_days, is_active=body.is_active)
        return _reward(item)
    except DomainError as exc: raise _domain_error(exc) from exc
    except IntegrityError as exc: raise _conflict(exc) from exc


@router.patch("/rewards/{reward_id}")
async def update_reward(reward_id: UUID, body: UpdateRewardRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await configs.update_reward(session, organization_id=p.organization_id, reward_id=reward_id, name=body.name, config=body.config, stackable=body.stackable, default_validity_days=body.default_validity_days, set_validity=body.set_validity, is_active=body.is_active)
        return _reward(item)
    except DomainError as exc: raise _domain_error(exc) from exc


@router.get("/campaigns")
async def list_campaigns(staff_session_id: UUID, session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        p = await _admin(session, staff_session_id)
        return [_campaign(x) for x in await configs.list_campaigns(session, p.organization_id)]
    except DomainError as exc: raise _domain_error(exc) from exc


@router.post("/campaigns", status_code=201)
async def create_campaign(body: CreateCampaignRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await configs.create_campaign(session, organization_id=p.organization_id, code=body.code, name=body.name, priority=body.priority, stackable=body.stackable, conditions=body.conditions, effects=body.effects, starts_at=body.starts_at, ends_at=body.ends_at, is_active=body.is_active)
        return _campaign(item)
    except DomainError as exc: raise _domain_error(exc) from exc
    except IntegrityError as exc: raise _conflict(exc) from exc


@router.patch("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: UUID, body: UpdateCampaignRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await configs.update_campaign(session, organization_id=p.organization_id, campaign_id=campaign_id, name=body.name, priority=body.priority, stackable=body.stackable, conditions=body.conditions, effects=body.effects, starts_at=body.starts_at, ends_at=body.ends_at, set_window=body.set_window, is_active=body.is_active)
        return _campaign(item)
    except DomainError as exc: raise _domain_error(exc) from exc


@router.get("/milestones")
async def list_milestones(staff_session_id: UUID, session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        p = await _admin(session, staff_session_id)
        return [_milestone(x) for x in await configs.list_milestones(session, p.organization_id)]
    except DomainError as exc: raise _domain_error(exc) from exc


@router.post("/milestones", status_code=201)
async def create_milestone(body: CreateMilestoneRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await configs.create_milestone(session, organization_id=p.organization_id, code=body.code, name=body.name, category_id=body.category_id, threshold_count=body.threshold_count, reward_definition_id=body.reward_definition_id, repeatable=body.repeatable, is_active=body.is_active)
        return _milestone(item)
    except DomainError as exc: raise _domain_error(exc) from exc
    except IntegrityError as exc: raise _conflict(exc) from exc


@router.patch("/milestones/{rule_id}")
async def update_milestone(rule_id: UUID, body: UpdateMilestoneRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await configs.update_milestone(session, organization_id=p.organization_id, rule_id=rule_id, name=body.name, threshold_count=body.threshold_count, repeatable=body.repeatable, is_active=body.is_active)
        return _milestone(item)
    except DomainError as exc: raise _domain_error(exc) from exc
