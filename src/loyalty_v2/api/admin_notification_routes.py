from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.auth_service import Permission
from loyalty_v2.application.notification_service import NotificationService
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.application.services import DomainError
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/api/v2/admin/notifications", tags=["admin-notifications"])
principals = PrincipalService()
notifications = NotificationService()


class SegmentBroadcastRequest(BaseModel):
    staff_session_id: UUID
    segment_code: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=4000)
    campaign_key: str = Field(min_length=1, max_length=100)


async def _admin(session: AsyncSession, staff_session_id: UUID):
    p = await principals.staff(session, staff_session_id=staff_session_id)
    p.require(Permission.ADMIN_ACCESS)
    return p


@router.post("/segment", status_code=202)
async def broadcast_segment(body: SegmentBroadcastRequest, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with session.begin():
            p = await _admin(session, body.staff_session_id)
            queued = await notifications.enqueue_segment(session, organization_id=p.organization_id, segment_code=body.segment_code, body=body.body, campaign_key=body.campaign_key)
        return {"queued": queued, "segment_code": body.segment_code, "campaign_key": body.campaign_key}
    except DomainError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN if exc.code == "PERMISSION_DENIED" else status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": exc.code, "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "NOTIFICATION_INVALID", "message": str(exc)}) from exc
