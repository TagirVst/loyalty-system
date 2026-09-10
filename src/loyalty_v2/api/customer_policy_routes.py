from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.auth_service import Permission, StaffAuthService
from loyalty_v2.application.customer_policy_service import CustomerPolicyService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/v2")
auth = StaffAuthService()
policies = CustomerPolicyService()


class TierOverrideRequest(BaseModel):
    organization_id: UUID
    staff_session_id: UUID
    tier_id: UUID
    reason: str = Field(min_length=1, max_length=500)
    ends_at: datetime | None = None


class RedemptionOverrideRequest(BaseModel):
    organization_id: UUID
    staff_session_id: UUID
    max_percent: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=500)
    ends_at: datetime


class BlockCustomerRequest(BaseModel):
    organization_id: UUID
    staff_session_id: UUID
    blocked: bool


class ChangePhoneRequest(BaseModel):
    organization_id: UUID
    new_phone: str = Field(min_length=7, max_length=32)


class ChangeBirthDateRequest(BaseModel):
    organization_id: UUID
    new_birth_date: date


def domain_error(exc: DomainError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code, "message": str(exc)})


@router.post("/admin/customers/{customer_id}/tier-override")
async def set_tier_override(customer_id: UUID, body: TierOverrideRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            _, staff = await auth.require(session, staff_session_id=body.staff_session_id, permission=Permission.ADMIN_ACCESS)
            item = await policies.set_tier_override(session, organization_id=body.organization_id, customer_id=customer_id, tier_id=body.tier_id, staff_id=staff.id, reason=body.reason, ends_at=body.ends_at)
    except DomainError as exc:
        raise domain_error(exc) from exc
    return {"id": item.id, "tier_id": item.tier_id, "ends_at": item.ends_at}


@router.post("/admin/customers/{customer_id}/redemption-override")
async def set_redemption_override(customer_id: UUID, body: RedemptionOverrideRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            _, staff = await auth.require(session, staff_session_id=body.staff_session_id, permission=Permission.ADMIN_ACCESS)
            item = await policies.set_redemption_override(session, organization_id=body.organization_id, customer_id=customer_id, max_percent=body.max_percent, staff_id=staff.id, reason=body.reason, ends_at=body.ends_at)
    except DomainError as exc:
        raise domain_error(exc) from exc
    return {"id": item.id, "max_percent": item.max_percent, "ends_at": item.ends_at}


@router.post("/admin/customers/{customer_id}/blocked")
async def set_customer_blocked(customer_id: UUID, body: BlockCustomerRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            await auth.require(session, staff_session_id=body.staff_session_id, permission=Permission.ADMIN_ACCESS)
            customer = await policies.set_blocked(session, organization_id=body.organization_id, customer_id=customer_id, blocked=body.blocked)
    except DomainError as exc:
        raise domain_error(exc) from exc
    return {"customer_id": customer.id, "blocked": customer.is_blocked}


@router.post("/customers/{customer_id}/phone")
async def change_phone(customer_id: UUID, body: ChangePhoneRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            customer = await policies.change_phone(session, organization_id=body.organization_id, customer_id=customer_id, new_phone=body.new_phone)
    except DomainError as exc:
        raise domain_error(exc) from exc
    return {"customer_id": customer.id, "phone": customer.phone}


@router.post("/customers/{customer_id}/birth-date")
async def change_birth_date(customer_id: UUID, body: ChangeBirthDateRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            customer = await policies.change_birth_date(session, organization_id=body.organization_id, customer_id=customer_id, new_birth_date=body.new_birth_date)
    except DomainError as exc:
        raise domain_error(exc) from exc
    return {"customer_id": customer.id, "birth_date": customer.birth_date, "change_count": customer.birth_date_change_count}
