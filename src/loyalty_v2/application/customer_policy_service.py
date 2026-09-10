from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import DomainError, TierService
from loyalty_v2.db.customer_policy_models import CustomerProfileChange, CustomerRedemptionOverride, CustomerTierOverride
from loyalty_v2.db.models import Customer, CustomerLoyaltyState, LoyaltyTier

class CustomerPolicyError(DomainError): code = "CUSTOMER_POLICY_ERROR"
class BirthDateChangeNotAllowed(CustomerPolicyError): code = "BIRTH_DATE_CHANGE_NOT_ALLOWED"
class PhoneAlreadyUsed(CustomerPolicyError): code = "PHONE_ALREADY_USED"

@dataclass(frozen=True, slots=True)
class EffectiveLoyaltyPolicy:
    automatic_tier: LoyaltyTier
    effective_tier: LoyaltyTier
    redemption_percent: int
    tier_override_id: UUID | None
    redemption_override_id: UUID | None
    inactivity_steps: int

class CustomerPolicyService:
    def __init__(self) -> None: self.tiers = TierService()

    async def resolve(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, now: datetime | None = None) -> EffectiveLoyaltyPolicy:
        now = now or datetime.now(timezone.utc)
        state = await session.scalar(select(CustomerLoyaltyState).where(CustomerLoyaltyState.organization_id==organization_id, CustomerLoyaltyState.customer_id==customer_id))
        if state is None: raise CustomerPolicyError("Customer loyalty state missing")
        automatic_tier = await self.tiers.tier_for_spend(session, organization_id, state.qualification_spend_minor)
        effective_tier = automatic_tier
        tier_override = await session.scalar(select(CustomerTierOverride).where(CustomerTierOverride.organization_id==organization_id, CustomerTierOverride.customer_id==customer_id, CustomerTierOverride.is_active.is_(True), CustomerTierOverride.starts_at<=now, (CustomerTierOverride.ends_at.is_(None)) | (CustomerTierOverride.ends_at>now)).order_by(CustomerTierOverride.created_at.desc()).limit(1))
        if tier_override:
            tier = await session.scalar(select(LoyaltyTier).where(LoyaltyTier.id==tier_override.tier_id, LoyaltyTier.organization_id==organization_id, LoyaltyTier.is_active.is_(True)))
            if tier: effective_tier = tier
        elif state.inactivity_steps > 0:
            tiers = (await session.scalars(select(LoyaltyTier).where(LoyaltyTier.organization_id==organization_id, LoyaltyTier.is_active.is_(True)).order_by(LoyaltyTier.sort_order.asc()))).all()
            ids = [x.id for x in tiers]
            if automatic_tier.id in ids:
                effective_tier = tiers[max(0, ids.index(automatic_tier.id) - state.inactivity_steps)]
        redemption_override = await session.scalar(select(CustomerRedemptionOverride).where(CustomerRedemptionOverride.organization_id==organization_id, CustomerRedemptionOverride.customer_id==customer_id, CustomerRedemptionOverride.is_active.is_(True), CustomerRedemptionOverride.starts_at<=now, CustomerRedemptionOverride.ends_at>now).order_by(CustomerRedemptionOverride.created_at.desc()).limit(1))
        return EffectiveLoyaltyPolicy(automatic_tier=automatic_tier, effective_tier=effective_tier, redemption_percent=redemption_override.max_percent if redemption_override else 30, tier_override_id=tier_override.id if tier_override else None, redemption_override_id=redemption_override.id if redemption_override else None, inactivity_steps=state.inactivity_steps)

    async def set_tier_override(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, tier_id: UUID, staff_id: UUID, reason: str, ends_at: datetime | None) -> CustomerTierOverride:
        now = datetime.now(timezone.utc)
        customer = await session.scalar(select(Customer.id).where(Customer.id == customer_id, Customer.organization_id == organization_id))
        tier = await session.scalar(select(LoyaltyTier.id).where(LoyaltyTier.id == tier_id, LoyaltyTier.organization_id == organization_id, LoyaltyTier.is_active.is_(True)))
        if customer is None or tier is None:
            raise CustomerPolicyError("Customer or tier is unavailable")
        if ends_at is not None and ends_at <= now:
            raise CustomerPolicyError("Tier override end must be in the future")
        current=(await session.scalars(select(CustomerTierOverride).where(CustomerTierOverride.organization_id==organization_id, CustomerTierOverride.customer_id==customer_id, CustomerTierOverride.is_active.is_(True)).with_for_update())).all()
        for item in current: item.is_active=False
        override=CustomerTierOverride(organization_id=organization_id,customer_id=customer_id,tier_id=tier_id,starts_at=now,ends_at=ends_at,reason=reason,created_by_staff_id=staff_id); session.add(override); await session.flush(); return override

    async def set_redemption_override(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, max_percent: int, staff_id: UUID, reason: str, ends_at: datetime) -> CustomerRedemptionOverride:
        if not 0<=max_percent<=100 or ends_at<=datetime.now(timezone.utc): raise CustomerPolicyError("Invalid redemption override")
        customer = await session.scalar(select(Customer.id).where(Customer.id == customer_id, Customer.organization_id == organization_id))
        if customer is None: raise CustomerPolicyError("Customer not found")
        current=(await session.scalars(select(CustomerRedemptionOverride).where(CustomerRedemptionOverride.organization_id==organization_id,CustomerRedemptionOverride.customer_id==customer_id,CustomerRedemptionOverride.is_active.is_(True)).with_for_update())).all()
        for item in current: item.is_active=False
        override=CustomerRedemptionOverride(organization_id=organization_id,customer_id=customer_id,max_percent=max_percent,starts_at=datetime.now(timezone.utc),ends_at=ends_at,reason=reason,created_by_staff_id=staff_id); session.add(override); await session.flush(); return override

    async def apply_inactivity(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, now: datetime|None=None) -> int:
        now=now or datetime.now(timezone.utc); state=await session.scalar(select(CustomerLoyaltyState).where(CustomerLoyaltyState.organization_id==organization_id,CustomerLoyaltyState.customer_id==customer_id).with_for_update())
        if state is None or state.last_purchase_at is None: return 0
        required_steps=max(0,(now-state.last_purchase_at).days//365)
        if required_steps>state.inactivity_steps: state.inactivity_steps=required_steps; await session.flush()
        return state.inactivity_steps

    async def change_phone(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, new_phone: str) -> Customer:
        customer=await session.scalar(select(Customer).where(Customer.id==customer_id,Customer.organization_id==organization_id).with_for_update())
        if customer is None: raise CustomerPolicyError("Customer not found")
        duplicate=await session.scalar(select(Customer.id).where(Customer.organization_id==organization_id,Customer.phone==new_phone,Customer.id!=customer_id))
        if duplicate: raise PhoneAlreadyUsed("Phone is already registered")
        old=customer.phone; customer.phone=new_phone; session.add(CustomerProfileChange(organization_id=organization_id,customer_id=customer_id,field_name="phone",old_value=old,new_value=new_phone,source="customer",created_at=datetime.now(timezone.utc))); await session.flush(); return customer

    async def change_birth_date(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, new_birth_date: date) -> Customer:
        customer=await session.scalar(select(Customer).where(Customer.id==customer_id,Customer.organization_id==organization_id).with_for_update())
        if customer is None: raise CustomerPolicyError("Customer not found")
        if customer.birth_date_change_count>=1: raise BirthDateChangeNotAllowed("Birth date can only be changed once by customer")
        old=customer.birth_date; customer.birth_date=new_birth_date; customer.birth_date_change_count+=1; session.add(CustomerProfileChange(organization_id=organization_id,customer_id=customer_id,field_name="birth_date",old_value=old.isoformat(),new_value=new_birth_date.isoformat(),source="customer",created_at=datetime.now(timezone.utc))); await session.flush(); return customer

    async def set_blocked(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID, blocked: bool) -> Customer:
        customer=await session.scalar(select(Customer).where(Customer.id==customer_id,Customer.organization_id==organization_id).with_for_update())
        if customer is None: raise CustomerPolicyError("Customer not found")
        customer.is_blocked=blocked; customer.blocked_at=datetime.now(timezone.utc) if blocked else None; await session.flush(); return customer