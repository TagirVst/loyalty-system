from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.db.category_models import SaleCategory
from loyalty_v2.db.engagement_models import CustomerSegment
from loyalty_v2.db.milestone_models import CustomerCategoryCounter
from loyalty_v2.db.models import CustomerLoyaltyState, LoyaltyTier, PointsAccount


class SegmentService:
    async def active_codes_for_customer(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, now: datetime | None = None) -> set[str]:
        now = now or datetime.now(timezone.utc)
        state = await session.scalar(select(CustomerLoyaltyState).where(CustomerLoyaltyState.organization_id == organization_id, CustomerLoyaltyState.customer_id == customer_id))
        account = await session.scalar(select(PointsAccount).where(PointsAccount.organization_id == organization_id, PointsAccount.customer_id == customer_id))
        if state is None or account is None:
            return set()
        tier = await session.scalar(select(LoyaltyTier).where(LoyaltyTier.id == state.automatic_tier_id, LoyaltyTier.organization_id == organization_id))
        counters = (await session.execute(
            select(SaleCategory.code, CustomerCategoryCounter.net_count)
            .join(SaleCategory, SaleCategory.id == CustomerCategoryCounter.category_id)
            .where(CustomerCategoryCounter.organization_id == organization_id, CustomerCategoryCounter.customer_id == customer_id)
        )).all()
        category_counts = {str(code): int(count) for code, count in counters}
        segments = (await session.scalars(select(CustomerSegment).where(CustomerSegment.organization_id == organization_id, CustomerSegment.is_active.is_(True)))).all()
        return {segment.code for segment in segments if self.matches(segment.conditions or {}, state=state, account=account, tier=tier, category_counts=category_counts, now=now)}

    @staticmethod
    def matches(conditions: dict, *, state, account, tier, category_counts: dict[str, int], now: datetime) -> bool:
        min_spend = int(conditions.get("minimum_qualification_spend_minor", 0) or 0)
        if state.qualification_spend_minor < min_spend:
            return False
        min_balance = int(conditions.get("minimum_points_balance", 0) or 0)
        if account.balance < min_balance:
            return False
        tier_names = [str(x).lower() for x in conditions.get("tier_names", [])]
        if tier_names and (tier is None or tier.name.lower() not in tier_names):
            return False
        inactive_days = conditions.get("inactive_days_at_least")
        if inactive_days is not None:
            if state.last_purchase_at is None or state.last_purchase_at > now - timedelta(days=int(inactive_days)):
                return False
        active_days = conditions.get("purchased_within_days")
        if active_days is not None:
            if state.last_purchase_at is None or state.last_purchase_at < now - timedelta(days=int(active_days)):
                return False
        for code, minimum in (conditions.get("category_counts") or {}).items():
            if category_counts.get(str(code), 0) < int(minimum):
                return False
        return True
