from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.db.identity_models import CustomerAuthIdentity
from loyalty_v2.db.models import Customer, CustomerLoyaltyState, LedgerEntryType, LoyaltyTier, PointsAccount, PointsLedgerEntry

class DomainError(Exception): code = "DOMAIN_ERROR"
class CustomerAlreadyExists(DomainError): code = "CUSTOMER_ALREADY_EXISTS"
class CustomerNotFound(DomainError): code = "CUSTOMER_NOT_FOUND"
class InvalidPointsAmount(DomainError): code = "INVALID_POINTS_AMOUNT"
class InsufficientPoints(DomainError): code = "INSUFFICIENT_POINTS"
class NoActiveTier(DomainError): code = "NO_ACTIVE_TIER"

@dataclass(frozen=True, slots=True)
class RegisteredCustomer:
    customer: Customer
    account: PointsAccount
    loyalty_state: CustomerLoyaltyState

class TierService:
    async def tier_for_spend(self, session: AsyncSession, organization_id: UUID, spend_minor: int) -> LoyaltyTier:
        tier=await session.scalar(select(LoyaltyTier).where(LoyaltyTier.organization_id==organization_id,LoyaltyTier.is_active.is_(True),LoyaltyTier.minimum_spend_minor<=spend_minor).order_by(LoyaltyTier.minimum_spend_minor.desc(),LoyaltyTier.sort_order.desc()).limit(1))
        if tier is None: raise NoActiveTier("Organization has no active tier for this spend")
        return tier

class CustomerService:
    def __init__(self,tier_service:TierService|None=None)->None: self.tiers=tier_service or TierService()

    async def register(self,session:AsyncSession,*,organization_id:UUID,provider:str,external_subject:str,first_name:str,phone:str,birth_date:date)->RegisteredCustomer:
        provider=provider.strip().lower(); external_subject=external_subject.strip()
        if not provider or not external_subject: raise CustomerAlreadyExists("Authentication identity is required")
        identity_exists=await session.scalar(select(CustomerAuthIdentity.id).where(CustomerAuthIdentity.organization_id==organization_id,CustomerAuthIdentity.provider==provider,CustomerAuthIdentity.external_subject==external_subject,CustomerAuthIdentity.is_active.is_(True)))
        phone_exists=await session.scalar(select(Customer.id).where(Customer.organization_id==organization_id,Customer.phone==phone))
        if identity_exists is not None or phone_exists is not None: raise CustomerAlreadyExists("Authentication identity or phone is already registered")
        base_tier=await self.tiers.tier_for_spend(session,organization_id,0); legacy_telegram_id=int(external_subject) if provider=="telegram" and external_subject.isdigit() else None
        customer=Customer(organization_id=organization_id,telegram_id=legacy_telegram_id,first_name=first_name.strip(),phone=phone,birth_date=birth_date); session.add(customer); await session.flush()
        identity=CustomerAuthIdentity(organization_id=organization_id,customer_id=customer.id,provider=provider,external_subject=external_subject,is_verified=True,is_active=True,verified_at=datetime.now(timezone.utc))
        account=PointsAccount(organization_id=organization_id,customer_id=customer.id,balance=0,debt=0)
        loyalty_state=CustomerLoyaltyState(organization_id=organization_id,customer_id=customer.id,automatic_tier_id=base_tier.id,qualification_spend_minor=0)
        session.add_all([identity,account,loyalty_state]); await session.flush(); return RegisteredCustomer(customer,account,loyalty_state)

    async def by_identity(self,session:AsyncSession,*,organization_id:UUID,provider:str,external_subject:str)->Customer:
        identity=await session.scalar(select(CustomerAuthIdentity).where(CustomerAuthIdentity.organization_id==organization_id,CustomerAuthIdentity.provider==provider.strip().lower(),CustomerAuthIdentity.external_subject==external_subject.strip(),CustomerAuthIdentity.is_active.is_(True)))
        if identity is None: raise CustomerNotFound("Customer identity not found")
        customer=await session.scalar(select(Customer).where(Customer.id==identity.customer_id,Customer.organization_id==organization_id))
        if customer is None: raise CustomerNotFound("Customer not found")
        return customer

class PointsService:
    async def _locked_account(self,session:AsyncSession,organization_id:UUID,customer_id:UUID)->PointsAccount:
        account=await session.scalar(select(PointsAccount).where(PointsAccount.organization_id==organization_id,PointsAccount.customer_id==customer_id).with_for_update())
        if account is None: raise CustomerNotFound("Points account not found")
        return account

    async def _existing(self,session:AsyncSession,organization_id:UUID,idempotency_key:str|None)->PointsLedgerEntry|None:
        if not idempotency_key: return None
        return await session.scalar(select(PointsLedgerEntry).where(PointsLedgerEntry.organization_id==organization_id,PointsLedgerEntry.idempotency_key==idempotency_key))

    async def apply(self,session:AsyncSession,*,organization_id:UUID,customer_id:UUID,delta:int,entry_type:LedgerEntryType,reference_type:str|None=None,reference_id:UUID|None=None,reason:str|None=None,idempotency_key:str|None=None)->PointsLedgerEntry:
        if delta==0: raise InvalidPointsAmount("Points delta cannot be zero")
        existing=await self._existing(session,organization_id,idempotency_key)
        if existing is not None: return existing
        account=await self._locked_account(session,organization_id,customer_id)
        existing=await self._existing(session,organization_id,idempotency_key)
        if existing is not None: return existing
        debt_applied=0
        if delta>0:
            debt_applied=min(delta,account.debt); account.debt-=debt_applied; balance_delta=delta-debt_applied
        else:
            balance_delta=delta
        new_balance=account.balance+balance_delta
        if new_balance<0: raise InsufficientPoints("Points balance cannot become negative")
        account.balance=new_balance; account.version+=1
        entry=PointsLedgerEntry(organization_id=organization_id,customer_id=customer_id,account_id=account.id,entry_type=entry_type.value,delta=delta,balance_after=new_balance,debt_applied=debt_applied,debt_after=account.debt,reference_type=reference_type,reference_id=reference_id,reason=reason,idempotency_key=idempotency_key,created_at=datetime.now(timezone.utc))
        session.add(entry); await session.flush(); return entry

    async def add_debt(self,session:AsyncSession,*,organization_id:UUID,customer_id:UUID,amount:int,reference_type:str|None=None,reference_id:UUID|None=None,reason:str|None=None,idempotency_key:str|None=None)->PointsLedgerEntry:
        if amount<=0: raise InvalidPointsAmount("Debt amount must be positive")
        existing=await self._existing(session,organization_id,idempotency_key)
        if existing is not None: return existing
        account=await self._locked_account(session,organization_id,customer_id)
        existing=await self._existing(session,organization_id,idempotency_key)
        if existing is not None: return existing
        account.debt+=amount; account.version+=1
        entry=PointsLedgerEntry(organization_id=organization_id,customer_id=customer_id,account_id=account.id,entry_type=LedgerEntryType.REVERSAL.value,delta=-amount,balance_after=account.balance,debt_applied=0,debt_after=account.debt,reference_type=reference_type,reference_id=reference_id,reason=reason or "Unrecovered earned points converted to points debt",idempotency_key=idempotency_key,created_at=datetime.now(timezone.utc))
        session.add(entry); await session.flush(); return entry
