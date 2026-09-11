from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.audit_service import AuditService
from loyalty_v2.application.services import CustomerNotFound
from loyalty_v2.db.customer_policy_models import CustomerRedemptionOverride, CustomerTierOverride
from loyalty_v2.db.models import Customer


class AdminOverrideService:
    def __init__(self) -> None:
        self.audit = AuditService()

    async def clear(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        customer_id: UUID,
        actor_staff_id: UUID,
        clear_tier: bool,
        clear_redemption: bool,
        reason: str,
    ) -> dict[str, int]:
        customer = await session.scalar(select(Customer.id).where(Customer.id == customer_id, Customer.organization_id == organization_id))
        if customer is None:
            raise CustomerNotFound("Customer not found")
        tier_count = redemption_count = 0
        if clear_tier:
            rows = (await session.scalars(select(CustomerTierOverride).where(
                CustomerTierOverride.organization_id == organization_id,
                CustomerTierOverride.customer_id == customer_id,
                CustomerTierOverride.is_active.is_(True),
            ).with_for_update())).all()
            for item in rows:
                item.is_active = False
                tier_count += 1
        if clear_redemption:
            rows = (await session.scalars(select(CustomerRedemptionOverride).where(
                CustomerRedemptionOverride.organization_id == organization_id,
                CustomerRedemptionOverride.customer_id == customer_id,
                CustomerRedemptionOverride.is_active.is_(True),
            ).with_for_update())).all()
            for item in rows:
                item.is_active = False
                redemption_count += 1
        await self.audit.record(
            session,
            organization_id=organization_id,
            actor_staff_id=actor_staff_id,
            action="customer.overrides.clear",
            object_type="customer",
            object_id=customer_id,
            metadata={"tier_overrides_cleared": tier_count, "redemption_overrides_cleared": redemption_count, "reason": reason},
        )
        await session.flush()
        return {"tier": tier_count, "redemption": redemption_count}
