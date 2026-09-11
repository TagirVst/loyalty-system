from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.admin_analytics_service import AdminAnalyticsService
from loyalty_v2.application.auth_service import Permission
from loyalty_v2.application.principal import PrincipalService
from loyalty_v2.db.session import get_session

router = APIRouter(prefix="/api/v2/admin/analytics", tags=["admin-analytics"])
principals = PrincipalService()
analytics = AdminAnalyticsService()


@router.get("/summary")
async def summary(
    staff_session_id: UUID,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    location_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    principal = await principals.staff(session, staff_session_id=staff_session_id)
    principal.require(Permission.ADMIN_ACCESS)
    end = ends_at or datetime.now(timezone.utc)
    start = starts_at or (end - timedelta(days=30))
    if start >= end:
        raise ValueError("starts_at must be before ends_at")
    if location_id is not None and location_id != principal.location_id:
        # Admins are organization-scoped, but explicit location filtering is validated by org in the query layer.
        pass
    item = await analytics.summary(session, organization_id=principal.organization_id, starts_at=start, ends_at=end, location_id=location_id)
    return {
        "period": {"starts_at": start, "ends_at": end},
        "location_id": location_id,
        "orders_count": item.orders_count,
        "gross_amount_minor": item.gross_amount_minor,
        "paid_amount_minor": item.paid_amount_minor,
        "redeemed_points": item.redeemed_points,
        "points_earned": item.points_earned,
        "qualification_amount_minor": item.qualification_amount_minor,
        "refunds_count": item.refunds_count,
        "refunded_gross_minor": item.refunded_gross_minor,
        "refunded_paid_minor": item.refunded_paid_minor,
        "restored_points": item.restored_points,
        "reversed_earned_points": item.reversed_earned_points,
        "points_debt_created": item.points_debt_created,
        "active_customers": item.active_customers,
        "net_paid_minor": item.paid_amount_minor - item.refunded_paid_minor,
    }


@router.get("/tiers")
async def tiers(staff_session_id: UUID, session: AsyncSession = Depends(get_session)) -> list[dict]:
    principal = await principals.staff(session, staff_session_id=staff_session_id)
    principal.require(Permission.ADMIN_ACCESS)
    return await analytics.tier_distribution(session, organization_id=principal.organization_id)
