from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.db.models import CustomerLoyaltyState, LoyaltyTier
from loyalty_v2.db.order_models import Order
from loyalty_v2.db.refund_models import Refund


@dataclass(frozen=True, slots=True)
class AnalyticsSummary:
    orders_count: int
    gross_amount_minor: int
    paid_amount_minor: int
    redeemed_points: int
    points_earned: int
    qualification_amount_minor: int
    refunds_count: int
    refunded_gross_minor: int
    refunded_paid_minor: int
    restored_points: int
    reversed_earned_points: int
    points_debt_created: int
    active_customers: int


class AdminAnalyticsService:
    async def summary(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
        location_id: UUID | None = None,
    ) -> AnalyticsSummary:
        order_filters = [
            Order.organization_id == organization_id,
            Order.confirmed_at >= starts_at,
            Order.confirmed_at < ends_at,
        ]
        if location_id is not None:
            order_filters.append(Order.location_id == location_id)

        order_row = (await session.execute(
            select(
                func.count(Order.id),
                func.coalesce(func.sum(Order.gross_amount_minor), 0),
                func.coalesce(func.sum(Order.paid_amount_minor), 0),
                func.coalesce(func.sum(Order.redeemed_points), 0),
                func.coalesce(func.sum(Order.points_earned), 0),
                func.coalesce(func.sum(Order.qualification_amount_minor), 0),
                func.count(func.distinct(Order.customer_id)),
            ).where(*order_filters)
        )).one()

        refund_stmt = (
            select(
                func.count(Refund.id),
                func.coalesce(func.sum(Refund.gross_refund_minor), 0),
                func.coalesce(func.sum(Refund.paid_refund_minor), 0),
                func.coalesce(func.sum(Refund.restored_points), 0),
                func.coalesce(func.sum(Refund.reversed_earned_points), 0),
                func.coalesce(func.sum(Refund.points_debt_created), 0),
            )
            .join(Order, Order.id == Refund.order_id)
            .where(
                Refund.organization_id == organization_id,
                Refund.created_at >= starts_at,
                Refund.created_at < ends_at,
            )
        )
        if location_id is not None:
            refund_stmt = refund_stmt.where(Order.location_id == location_id)
        refund_row = (await session.execute(refund_stmt)).one()

        return AnalyticsSummary(
            orders_count=int(order_row[0]),
            gross_amount_minor=int(order_row[1]),
            paid_amount_minor=int(order_row[2]),
            redeemed_points=int(order_row[3]),
            points_earned=int(order_row[4]),
            qualification_amount_minor=int(order_row[5]),
            active_customers=int(order_row[6]),
            refunds_count=int(refund_row[0]),
            refunded_gross_minor=int(refund_row[1]),
            refunded_paid_minor=int(refund_row[2]),
            restored_points=int(refund_row[3]),
            reversed_earned_points=int(refund_row[4]),
            points_debt_created=int(refund_row[5]),
        )

    async def tier_distribution(self, session: AsyncSession, *, organization_id: UUID) -> list[dict]:
        rows = (await session.execute(
            select(LoyaltyTier.id, LoyaltyTier.name, func.count(CustomerLoyaltyState.customer_id))
            .join(CustomerLoyaltyState, CustomerLoyaltyState.automatic_tier_id == LoyaltyTier.id)
            .where(LoyaltyTier.organization_id == organization_id)
            .group_by(LoyaltyTier.id, LoyaltyTier.name, LoyaltyTier.sort_order)
            .order_by(LoyaltyTier.sort_order.asc())
        )).all()
        return [{"tier_id": tier_id, "name": name, "customers": int(count)} for tier_id, name, count in rows]
