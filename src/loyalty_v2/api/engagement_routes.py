from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.admin_customer_service import AdminCustomerService
from loyalty_v2.application.audit_service import AuditService
from loyalty_v2.application.auth_service import Permission
from loyalty_v2.application.feedback_service import FeedbackError, FeedbackService
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.engagement_models import CustomerFeedback, CustomerSegment
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/api/v2", tags=["engagement"])
principals = PrincipalService()
feedback = FeedbackService()
audit = AuditService()
admin_customers = AdminCustomerService()


class AdminScoped(BaseModel):
    staff_session_id: UUID


class SegmentCreate(AdminScoped):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=160)
    conditions: dict = Field(default_factory=dict)
    is_active: bool = True


class SegmentUpdate(AdminScoped):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    conditions: dict | None = None
    is_active: bool | None = None


class FeedbackSettingsUpdate(AdminScoped):
    positive_from_rating: int = Field(ge=1, le=5)
    notify_admins_on_rating_at_most: int = Field(ge=1, le=5)
    external_review_url: str | None = Field(default=None, max_length=1000)


class FeedbackResolve(AdminScoped):
    resolution_note: str = Field(min_length=1, max_length=5000)


async def _admin(session: AsyncSession, staff_session_id: UUID):
    p = await principals.staff(session, staff_session_id=staff_session_id)
    p.require(Permission.ADMIN_ACCESS)
    return p


def _err(exc: DomainError) -> HTTPException:
    code = exc.code
    if code == "PERMISSION_DENIED": http = status.HTTP_403_FORBIDDEN
    elif code == "STAFF_SESSION_INVALID": http = status.HTTP_401_UNAUTHORIZED
    elif code == "CUSTOMER_NOT_FOUND": http = status.HTTP_404_NOT_FOUND
    else: http = status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(http, detail={"code": code, "message": str(exc)})


def _feedback_item(x: CustomerFeedback) -> dict:
    return {"id": x.id, "customer_id": x.customer_id, "order_id": x.order_id, "rating": x.rating, "comment": x.comment, "status": x.status, "routed_to_admins": x.routed_to_admins, "external_review_offered": x.external_review_offered, "created_at": x.created_at, "resolved_at": x.resolved_at, "resolved_by_staff_id": x.resolved_by_staff_id, "resolution_note": x.resolution_note}


@router.get("/admin/segments")
async def list_segments(staff_session_id: UUID, session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        p = await _admin(session, staff_session_id)
        rows = (await session.scalars(select(CustomerSegment).where(CustomerSegment.organization_id == p.organization_id).order_by(CustomerSegment.name.asc()))).all()
        return [{"id": x.id, "code": x.code, "name": x.name, "conditions": x.conditions, "is_active": x.is_active} for x in rows]
    except DomainError as exc: raise _err(exc) from exc


@router.post("/admin/segments", status_code=201)
async def create_segment(body: SegmentCreate, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = CustomerSegment(organization_id=p.organization_id, code=body.code, name=body.name, conditions=body.conditions, is_active=body.is_active)
            session.add(item); await session.flush()
            await audit.record(session, organization_id=p.organization_id, actor_staff_id=p.staff_id, action="create", object_type="customer_segment", object_id=item.id, after={"code": item.code, "name": item.name, "conditions": item.conditions, "is_active": item.is_active})
        return {"id": item.id, "code": item.code, "name": item.name, "conditions": item.conditions, "is_active": item.is_active}
    except DomainError as exc: raise _err(exc) from exc


@router.patch("/admin/segments/{segment_id}")
async def update_segment(segment_id: UUID, body: SegmentUpdate, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await session.scalar(select(CustomerSegment).where(CustomerSegment.id == segment_id, CustomerSegment.organization_id == p.organization_id).with_for_update())
            if item is None: raise FeedbackError("Segment not found")
            before = {"name": item.name, "conditions": item.conditions, "is_active": item.is_active}
            if body.name is not None: item.name = body.name
            if body.conditions is not None: item.conditions = body.conditions
            if body.is_active is not None: item.is_active = body.is_active
            await session.flush()
            await audit.record(session, organization_id=p.organization_id, actor_staff_id=p.staff_id, action="update", object_type="customer_segment", object_id=item.id, before=before, after={"name": item.name, "conditions": item.conditions, "is_active": item.is_active})
        return {"id": item.id, "code": item.code, "name": item.name, "conditions": item.conditions, "is_active": item.is_active}
    except DomainError as exc: raise _err(exc) from exc


@router.get("/admin/feedback")
async def list_feedback(staff_session_id: UUID, unresolved_only: bool = True, session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        p = await _admin(session, staff_session_id)
        stmt = select(CustomerFeedback).where(CustomerFeedback.organization_id == p.organization_id)
        if unresolved_only: stmt = stmt.where(CustomerFeedback.status != "resolved")
        rows = (await session.scalars(stmt.order_by(CustomerFeedback.created_at.desc()).limit(200))).all()
        return [_feedback_item(x) for x in rows]
    except DomainError as exc: raise _err(exc) from exc


@router.get("/admin/customers/{customer_id}/feedback")
async def customer_feedback(customer_id: UUID, staff_session_id: UUID, session: AsyncSession = Depends(get_session)) -> list[dict]:
    try:
        p = await _admin(session, staff_session_id)
        await admin_customers.summary(session, organization_id=p.organization_id, customer_id=customer_id)
        return [_feedback_item(x) for x in await admin_customers.feedback(session, organization_id=p.organization_id, customer_id=customer_id)]
    except DomainError as exc: raise _err(exc) from exc


@router.post("/admin/feedback/{feedback_id}/resolve")
async def resolve_feedback(feedback_id: UUID, body: FeedbackResolve, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await feedback.resolve(session, organization_id=p.organization_id, feedback_id=feedback_id, staff_id=p.staff_id, resolution_note=body.resolution_note)
            await audit.record(session, organization_id=p.organization_id, actor_staff_id=p.staff_id, action="resolve", object_type="customer_feedback", object_id=item.id, after={"status": item.status, "resolution_note": item.resolution_note})
        return {"id": item.id, "status": item.status, "resolved_at": item.resolved_at}
    except DomainError as exc: raise _err(exc) from exc


@router.put("/admin/feedback-settings")
async def update_feedback_settings(body: FeedbackSettingsUpdate, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            item = await feedback.settings(session, organization_id=p.organization_id)
            before = {"positive_from_rating": item.positive_from_rating, "notify_admins_on_rating_at_most": item.notify_admins_on_rating_at_most, "external_review_url": item.external_review_url}
            item.positive_from_rating = body.positive_from_rating
            item.notify_admins_on_rating_at_most = body.notify_admins_on_rating_at_most
            item.external_review_url = body.external_review_url
            await session.flush()
            await audit.record(session, organization_id=p.organization_id, actor_staff_id=p.staff_id, action="update", object_type="feedback_settings", object_id=item.id, before=before, after={"positive_from_rating": item.positive_from_rating, "notify_admins_on_rating_at_most": item.notify_admins_on_rating_at_most, "external_review_url": item.external_review_url})
        return {"positive_from_rating": item.positive_from_rating, "notify_admins_on_rating_at_most": item.notify_admins_on_rating_at_most, "external_review_url": item.external_review_url}
    except DomainError as exc: raise _err(exc) from exc
