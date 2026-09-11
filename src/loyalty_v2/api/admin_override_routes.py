from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.admin_override_service import AdminOverrideService
from loyalty_v2.application.auth_service import Permission
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/api/v2/admin/customers", tags=["admin-customers"])
principals = PrincipalService()
overrides = AdminOverrideService()


class ClearOverridesRequest(BaseModel):
    staff_session_id: UUID
    clear_tier: bool = True
    clear_redemption: bool = True
    reason: str = Field(min_length=1, max_length=500)


@router.post("/{customer_id}/overrides/clear")
async def clear_overrides(customer_id: UUID, body: ClearOverridesRequest, session: AsyncSession = Depends(get_session)) -> dict:
    if not body.clear_tier and not body.clear_redemption:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "NO_OVERRIDE_SELECTED"})
    try:
        async with session.begin():
            principal = await principals.staff(session, staff_session_id=body.staff_session_id)
            principal.require(Permission.ADMIN_ACCESS)
            result = await overrides.clear(
                session,
                organization_id=principal.organization_id,
                customer_id=customer_id,
                actor_staff_id=principal.staff_id,
                clear_tier=body.clear_tier,
                clear_redemption=body.clear_redemption,
                reason=body.reason,
            )
        return {"customer_id": customer_id, "cleared": result}
    except DomainError as exc:
        code = status.HTTP_404_NOT_FOUND if exc.code == "CUSTOMER_NOT_FOUND" else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(code, detail={"code": exc.code, "message": str(exc)}) from exc
