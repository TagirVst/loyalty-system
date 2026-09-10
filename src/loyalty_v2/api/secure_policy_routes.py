from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.auth_service import Permission
from loyalty_v2.application.customer_policy_service import CustomerPolicyService
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/api/v2")
principals = PrincipalService()
policies = CustomerPolicyService()


class AdminScopedRequest(BaseModel):
    staff_session_id: UUID


class TierOverrideRequest(AdminScopedRequest):
    tier_id: UUID
    reason: str = Field(min_length=1, max_length=500)
    ends_at: datetime | None = None


class RedemptionOverrideRequest(AdminScopedRequest):
    max_percent: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=500)
    ends_at: datetime


class BlockCustomerRequest(AdminScopedRequest):
    blocked: bool


def domain_error(exc: DomainError) -> HTTPException:
    code = exc.code
    http_status = status.HTTP_403_FORBIDDEN if code == "PERMISSION_DENIED" else status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(http_status, detail={"code": code, "message": str(exc)})


@router.post("/admin/customers/{customer_id}/tier-override")
async def set_tier_override(customer_id: UUID, body: TierOverrideRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.ADMIN_ACCESS)
            item = await policies.set_tier_override(
                session,
                organization_id=principal.organization_id,
                customer_id=customer_id,
                tier_id=body.tier_id,
                staff_id=principal.staff_id,
                reason=body.reason,
                ends_at=body.ends_at,
            )
    except DomainError as exc:
        raise domain_error(exc) from exc
    return {"id": item.id, "tier_id": item.tier_id, "ends_at": item.ends_at}


@router.post("/admin/customers/{customer_id}/redemption-override")
async def set_redemption_override(customer_id: UUID, body: RedemptionOverrideRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.ADMIN_ACCESS)
            item = await policies.set_redemption_override(
                session,
                organization_id=principal.organization_id,
                customer_id=customer_id,
                max_percent=body.max_percent,
                staff_id=principal.staff_id,
                reason=body.reason,
                ends_at=body.ends_at,
            )
    except DomainError as exc:
        raise domain_error(exc) from exc
    return {"id": item.id, "max_percent": item.max_percent, "ends_at": item.ends_at}


@router.post("/admin/customers/{customer_id}/blocked")
async def set_customer_blocked(customer_id: UUID, body: BlockCustomerRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.ADMIN_ACCESS)
            customer = await policies.set_blocked(
                session,
                organization_id=principal.organization_id,
                customer_id=customer_id,
                blocked=body.blocked,
            )
    except DomainError as exc:
        raise domain_error(exc) from exc
    return {"customer_id": customer.id, "blocked": customer.is_blocked}
