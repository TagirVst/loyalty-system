from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.customer_policy_service import CustomerPolicyService
from loyalty_v2.application.services import CustomerNotFound
from loyalty_v2.db.models import Customer, CustomerLoyaltyState, PointsAccount, PointsLedgerEntry
from loyalty_v2.db.reward_models import CustomerReward, RewardDefinition


@dataclass(frozen=True, slots=True)
class ClientHome:
    customer: Customer
    balance: int
    tier_name: str
    cashback_basis_points: int
    qualification_spend_minor: int
    next_tier_name: str | None
    next_tier_minimum_spend_minor: int | None


class ClientService:
    def __init__(self) -> None:
        self.policies = CustomerPolicyService()

    async def home(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID) -> ClientHome:
        customer = await session.scalar(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
        if customer is None or customer.is_blocked:
            raise CustomerNotFound("Customer is unavailable")
        account = await session.scalar(select(PointsAccount).where(PointsAccount.organization_id == organization_id, PointsAccount.customer_id == customer_id))
        state = await session.scalar(select(CustomerLoyaltyState).where(CustomerLoyaltyState.organization_id == organization_id, CustomerLoyaltyState.customer_id == customer_id))
        if account is None or state is None:
            raise CustomerNotFound("Customer loyalty state is unavailable")
        policy = await self.policies.resolve(session, organization_id=organization_id, customer_id=customer_id)
        from loyalty_v2.db.models import LoyaltyTier
        next_tier = await session.scalar(
            select(LoyaltyTier).where(
                LoyaltyTier.organization_id == organization_id,
                LoyaltyTier.is_active.is_(True),
                LoyaltyTier.minimum_spend_minor > state.qualification_spend_minor,
            ).order_by(LoyaltyTier.minimum_spend_minor.asc()).limit(1)
        )
        return ClientHome(
            customer=customer,
            balance=account.balance,
            tier_name=policy.effective_tier.name,
            cashback_basis_points=policy.effective_tier.cashback_basis_points,
            qualification_spend_minor=state.qualification_spend_minor,
            next_tier_name=next_tier.name if next_tier else None,
            next_tier_minimum_spend_minor=next_tier.minimum_spend_minor if next_tier else None,
        )

    async def rewards(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID) -> list[tuple[CustomerReward, RewardDefinition]]:
        now = datetime.now(timezone.utc)
        rows = await session.execute(
            select(CustomerReward, RewardDefinition)
            .join(RewardDefinition, RewardDefinition.id == CustomerReward.reward_definition_id)
            .where(
                CustomerReward.organization_id == organization_id,
                CustomerReward.customer_id == customer_id,
                CustomerReward.status == "active",
                CustomerReward.quantity_remaining > 0,
                CustomerReward.valid_from <= now,
                (CustomerReward.valid_until.is_(None)) | (CustomerReward.valid_until > now),
                RewardDefinition.is_active.is_(True),
            ).order_by(CustomerReward.valid_until.asc().nullslast(), CustomerReward.issued_at.desc())
        )
        return list(rows.all())

    async def history(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, limit: int = 20) -> list[PointsLedgerEntry]:
        return list((await session.scalars(
            select(PointsLedgerEntry).where(
                PointsLedgerEntry.organization_id == organization_id,
                PointsLedgerEntry.customer_id == customer_id,
            ).order_by(PointsLedgerEntry.created_at.desc()).limit(max(1, min(limit, 100)))
        )).all())
