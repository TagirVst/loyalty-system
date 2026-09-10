from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.audit_service import AuditService
from loyalty_v2.application.customer_policy_service import CustomerPolicyService
from loyalty_v2.application.services import CustomerNotFound, PointsService
from loyalty_v2.db.category_models import SaleCategory
from loyalty_v2.db.customer_policy_models import CustomerRedemptionOverride, CustomerTierOverride
from loyalty_v2.db.milestone_models import CustomerCategoryCounter
from loyalty_v2.db.models import Customer, CustomerLoyaltyState, LedgerEntryType, LoyaltyTier, PointsAccount, PointsLedgerEntry
from loyalty_v2.db.order_models import Order
from loyalty_v2.db.reward_models import CustomerReward, RewardDefinition


@dataclass(frozen=True, slots=True)
class CustomerSummary:
    customer: Customer
    balance: int
    qualification_spend_minor: int
    automatic_tier: LoyaltyTier
    effective_tier: LoyaltyTier
    redemption_percent: int


class AdminCustomerService:
    def __init__(self) -> None:
        self.points = PointsService()
        self.policies = CustomerPolicyService()
        self.audit = AuditService()

    async def search(self, session: AsyncSession, *, organization_id: UUID, query: str, limit: int = 30) -> list[Customer]:
        q = query.strip()
        if not q:
            stmt = select(Customer).where(Customer.organization_id == organization_id).order_by(Customer.created_at.desc()).limit(limit)
        else:
            like = f"%{q}%"
            stmt = select(Customer).where(
                Customer.organization_id == organization_id,
                or_(Customer.first_name.ilike(like), Customer.phone.ilike(like)),
            ).order_by(Customer.first_name.asc(), Customer.id.asc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    async def summary(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID) -> CustomerSummary:
        customer = await session.scalar(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
        if customer is None:
            raise CustomerNotFound("Customer not found")
        account = await session.scalar(select(PointsAccount).where(PointsAccount.organization_id == organization_id, PointsAccount.customer_id == customer_id))
        state = await session.scalar(select(CustomerLoyaltyState).where(CustomerLoyaltyState.organization_id == organization_id, CustomerLoyaltyState.customer_id == customer_id))
        if account is None or state is None:
            raise CustomerNotFound("Customer loyalty state not found")
        policy = await self.policies.resolve(session, organization_id=organization_id, customer_id=customer_id)
        return CustomerSummary(customer, account.balance, state.qualification_spend_minor, policy.automatic_tier, policy.effective_tier, policy.redemption_percent)

    async def ledger(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, limit: int = 100) -> list[PointsLedgerEntry]:
        return list((await session.scalars(select(PointsLedgerEntry).where(
            PointsLedgerEntry.organization_id == organization_id,
            PointsLedgerEntry.customer_id == customer_id,
        ).order_by(PointsLedgerEntry.created_at.desc(), PointsLedgerEntry.id.desc()).limit(limit))).all())

    async def orders(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, limit: int = 100) -> list[Order]:
        return list((await session.scalars(select(Order).where(
            Order.organization_id == organization_id,
            Order.customer_id == customer_id,
        ).order_by(Order.confirmed_at.desc(), Order.id.desc()).limit(limit))).all())

    async def rewards(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, limit: int = 100):
        rows = await session.execute(select(CustomerReward, RewardDefinition).join(
            RewardDefinition, RewardDefinition.id == CustomerReward.reward_definition_id
        ).where(
            CustomerReward.organization_id == organization_id,
            CustomerReward.customer_id == customer_id,
        ).order_by(CustomerReward.issued_at.desc()).limit(limit))
        return rows.all()

    async def category_counters(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID):
        rows = await session.execute(select(CustomerCategoryCounter, SaleCategory).join(
            SaleCategory, SaleCategory.id == CustomerCategoryCounter.category_id
        ).where(
            CustomerCategoryCounter.organization_id == organization_id,
            CustomerCategoryCounter.customer_id == customer_id,
        ).order_by(SaleCategory.name.asc()))
        return rows.all()

    async def active_overrides(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID):
        now = datetime.now(timezone.utc)
        tier = await session.scalar(select(CustomerTierOverride).where(
            CustomerTierOverride.organization_id == organization_id,
            CustomerTierOverride.customer_id == customer_id,
            CustomerTierOverride.is_active.is_(True),
            CustomerTierOverride.starts_at <= now,
            or_(CustomerTierOverride.ends_at.is_(None), CustomerTierOverride.ends_at > now),
        ).order_by(CustomerTierOverride.created_at.desc()).limit(1))
        redemption = await session.scalar(select(CustomerRedemptionOverride).where(
            CustomerRedemptionOverride.organization_id == organization_id,
            CustomerRedemptionOverride.customer_id == customer_id,
            CustomerRedemptionOverride.is_active.is_(True),
            CustomerRedemptionOverride.starts_at <= now,
            CustomerRedemptionOverride.ends_at > now,
        ).order_by(CustomerRedemptionOverride.created_at.desc()).limit(1))
        return tier, redemption

    async def adjust_points(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, actor_staff_id: UUID, delta: int, reason: str, idempotency_key: str):
        entry = await self.points.apply(
            session,
            organization_id=organization_id,
            customer_id=customer_id,
            delta=delta,
            entry_type=LedgerEntryType.MANUAL,
            reference_type="admin_customer_adjustment",
            reference_id=actor_staff_id,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        await self.audit.record(session, organization_id=organization_id, actor_staff_id=actor_staff_id, action="customer.points.adjust", object_type="customer", object_id=customer_id, metadata={"delta": delta, "reason": reason, "ledger_entry_id": entry.id})
        return entry

    async def set_blocked(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, actor_staff_id: UUID, blocked: bool, reason: str):
        customer = await session.scalar(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id).with_for_update())
        if customer is None:
            raise CustomerNotFound("Customer not found")
        before = self.audit.snapshot(customer, ("is_blocked", "blocked_at"))
        customer.is_blocked = blocked
        customer.blocked_at = datetime.now(timezone.utc) if blocked else None
        await session.flush()
        after = self.audit.snapshot(customer, ("is_blocked", "blocked_at"))
        await self.audit.record(session, organization_id=organization_id, actor_staff_id=actor_staff_id, action="customer.block" if blocked else "customer.unblock", object_type="customer", object_id=customer_id, before=before, after=after, metadata={"reason": reason})
        return customer
