from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.customer_policy_service import CustomerPolicyService
from loyalty_v2.db.models import CustomerLoyaltyState


class InactivityJob:
    """Idempotent batch job for inactivity penalty state."""

    def __init__(self) -> None:
        self.policies = CustomerPolicyService()

    async def run(self, session: AsyncSession, *, batch_size: int = 500) -> int:
        now = datetime.now(timezone.utc)
        customer_ids = (
            await session.scalars(
                select(CustomerLoyaltyState.customer_id)
                .where(CustomerLoyaltyState.last_purchase_at.is_not(None))
                .order_by(CustomerLoyaltyState.last_purchase_at.asc())
                .limit(batch_size)
            )
        ).all()
        changed = 0
        for customer_id in customer_ids:
            state = await session.scalar(select(CustomerLoyaltyState).where(CustomerLoyaltyState.customer_id == customer_id))
            if state is None:
                continue
            before = state.inactivity_steps
            await self.policies.apply_inactivity(
                session,
                organization_id=state.organization_id,
                customer_id=customer_id,
                now=now,
            )
            if state.inactivity_steps != before:
                changed += 1
        return changed
