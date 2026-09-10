from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.customer_policy_service import CustomerPolicyService
from loyalty_v2.application.milestone_service import MilestoneService
from loyalty_v2.application.notification_service import NotificationService
from loyalty_v2.application.reward_engine import RewardCampaignEngine
from loyalty_v2.application.services import DomainError, PointsService, TierService
from loyalty_v2.db.category_models import SaleCategory
from loyalty_v2.db.models import Customer, CustomerLoyaltyState, LedgerEntryType, PointsAccount
from loyalty_v2.db.order_models import IdentificationSession, Order, OrderDraft, OrderQuote
from loyalty_v2.db.reward_models import CustomerReward

POINT_MINOR_VALUE = 100
IDENTIFICATION_TTL_SECONDS = 90
QUOTE_TTL_SECONDS = 120

class InvalidIdentificationCode(DomainError): code = "INVALID_IDENTIFICATION_CODE"
class IdentificationExpired(DomainError): code = "IDENTIFICATION_EXPIRED"
class DraftNotReady(DomainError): code = "DRAFT_NOT_READY"
class QuoteExpired(DomainError): code = "QUOTE_EXPIRED"
class QuoteStale(DomainError): code = "QUOTE_STALE"
class RedemptionLimitExceeded(DomainError): code = "REDEMPTION_LIMIT_EXCEEDED"
class RewardSelectionInvalid(DomainError): code = "REWARD_SELECTION_INVALID"

@dataclass(frozen=True, slots=True)
class QuoteResult:
    quote: OrderQuote
    points_balance: int

class IdentificationService:
    async def generate(self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID) -> IdentificationSession:
        now = datetime.now(timezone.utc)
        customer = await session.scalar(select(Customer).where(Customer.id == customer_id, Customer.organization_id == organization_id))
        if customer is None or customer.is_blocked: raise InvalidIdentificationCode("Customer is unavailable")
        active = (await session.scalars(select(IdentificationSession).where(IdentificationSession.organization_id == organization_id, IdentificationSession.customer_id == customer_id, IdentificationSession.status == "active"))).all()
        for item in active: item.status = "expired"
        for _ in range(20):
            code = f"{secrets.randbelow(100000):05d}"
            collision = await session.scalar(select(IdentificationSession.id).where(IdentificationSession.organization_id == organization_id, IdentificationSession.code == code, IdentificationSession.status == "active"))
            if collision is None:
                item = IdentificationSession(organization_id=organization_id, customer_id=customer_id, code=code, status="active", expires_at=now + timedelta(seconds=IDENTIFICATION_TTL_SECONDS)); session.add(item); await session.flush(); return item
        raise DomainError("Could not allocate identification code")

    async def attach_to_draft(self, session: AsyncSession, *, organization_id: UUID, draft_id: UUID, code: str) -> OrderDraft:
        now = datetime.now(timezone.utc)
        ident = await session.scalar(select(IdentificationSession).where(IdentificationSession.organization_id == organization_id, IdentificationSession.code == code, IdentificationSession.status == "active").with_for_update())
        if ident is None: raise InvalidIdentificationCode("Identification code is invalid")
        if ident.expires_at <= now: ident.status = "expired"; raise IdentificationExpired("Identification code has expired")
        customer = await session.get(Customer, ident.customer_id)
        if customer is None or customer.is_blocked: raise InvalidIdentificationCode("Customer is unavailable")
        draft = await session.scalar(select(OrderDraft).where(OrderDraft.id == draft_id, OrderDraft.organization_id == organization_id).with_for_update())
        if draft is None or draft.status != "draft": raise DraftNotReady("Order draft is unavailable")
        draft.customer_id = customer.id; draft.identification_session_id = ident.id; draft.version += 1; await session.flush(); return draft

class OrderService:
    def __init__(self) -> None:
        self.tiers = TierService(); self.points = PointsService(); self.effects = RewardCampaignEngine(); self.policies = CustomerPolicyService(); self.milestones = MilestoneService(); self.notifications = NotificationService()

    async def create_draft(self, session: AsyncSession, *, organization_id: UUID, location_id: UUID, gross_amount_minor: int, requested_points: int = 0, currency_code: str = "RUB", selected_reward_ids: list[UUID] | None = None, category_counts: dict[str, int] | None = None) -> OrderDraft:
        if gross_amount_minor <= 0 or requested_points < 0: raise DraftNotReady("Invalid order values")
        categories = {str(k): int(v) for k,v in (category_counts or {}).items() if int(v)>0}
        if categories:
            known=set((await session.scalars(select(SaleCategory.code).where(SaleCategory.organization_id==organization_id, SaleCategory.is_active.is_(True), SaleCategory.code.in_(categories.keys())))).all())
            if known != set(categories): raise DraftNotReady("Unknown or inactive sale category")
        draft=OrderDraft(organization_id=organization_id, location_id=location_id, gross_amount_minor=gross_amount_minor, requested_points=requested_points, currency_code=currency_code, selected_reward_ids=[str(x) for x in (selected_reward_ids or [])], category_counts=categories); session.add(draft); await session.flush(); return draft

    async def _calculation(self, session, *, organization_id, draft, account, now):
        policy=await self.policies.resolve(session, organization_id=organization_id, customer_id=draft.customer_id, now=now); selected_ids=[UUID(x) for x in draft.selected_reward_ids]
        try: effects=await self.effects.resolve(session, organization_id=organization_id, customer_id=draft.customer_id, gross_amount_minor=draft.gross_amount_minor, selected_reward_ids=selected_ids, category_counts=draft.category_counts, now=now)
        except ValueError as exc: raise RewardSelectionInvalid(str(exc)) from exc
        after=max(draft.gross_amount_minor-effects.total_discount_minor,0); maximum=min((after*policy.redemption_percent)//(100*POINT_MINOR_VALUE), account.balance, after//POINT_MINOR_VALUE)
        if draft.requested_points>maximum: raise RedemptionLimitExceeded("Requested points exceed current redemption limit")
        redeemed=draft.requested_points; paid=after-redeemed*POINT_MINOR_VALUE; base=0 if redeemed else (paid*policy.effective_tier.cashback_basis_points)//1_000_000; earned=base*effects.cashback_multiplier
        snapshot={"reward_effects":[{"customer_reward_id":str(x.customer_reward_id),"discount_minor":x.discount_minor} for x in effects.reward_effects],"campaign_effects":[{"campaign_id":str(x.campaign_id),"discount_minor":x.discount_minor,"cashback_multiplier":x.cashback_multiplier} for x in effects.campaign_effects],"total_discount_minor":effects.total_discount_minor,"cashback_multiplier":effects.cashback_multiplier,"effective_tier_id":str(policy.effective_tier.id),"automatic_tier_id":str(policy.automatic_tier.id),"tier_override_id":str(policy.tier_override_id) if policy.tier_override_id else None,"redemption_percent":policy.redemption_percent,"redemption_override_id":str(policy.redemption_override_id) if policy.redemption_override_id else None,"inactivity_steps":policy.inactivity_steps}
        return policy,effects,after,maximum,redeemed,paid,earned,snapshot,selected_ids

    async def quote(self, session, *, organization_id, draft_id):
        draft=await session.scalar(select(OrderDraft).where(OrderDraft.id==draft_id,OrderDraft.organization_id==organization_id,OrderDraft.status=="draft"))
        if draft is None or draft.customer_id is None: raise DraftNotReady("Draft must have an identified customer")
        customer=await session.get(Customer,draft.customer_id); state=await session.scalar(select(CustomerLoyaltyState).where(CustomerLoyaltyState.customer_id==draft.customer_id)); account=await session.scalar(select(PointsAccount).where(PointsAccount.customer_id==draft.customer_id))
        if customer is None or customer.is_blocked or state is None or account is None: raise DraftNotReady("Customer loyalty state is unavailable")
        now=datetime.now(timezone.utc); policy,_,after,maximum,redeemed,paid,earned,snapshot,_=await self._calculation(session,organization_id=organization_id,draft=draft,account=account,now=now); qualification=after; potential=await self.tiers.tier_for_spend(session,organization_id,state.qualification_spend_minor+qualification)
        quote=OrderQuote(organization_id=organization_id,draft_id=draft.id,draft_version=draft.version,tier_id=policy.effective_tier.id,gross_amount_minor=draft.gross_amount_minor,amount_after_rewards_minor=after,max_redeemable_points=maximum,redeemed_points=redeemed,paid_amount_minor=paid,points_to_earn=earned,qualification_amount_minor=qualification,potential_tier_id=potential.id,loyalty_effects_snapshot=snapshot,category_counts_snapshot=dict(draft.category_counts),expires_at=now+timedelta(seconds=QUOTE_TTL_SECONDS)); session.add(quote); await session.flush(); return QuoteResult(quote,account.balance)

    async def confirm(self, session, *, organization_id, draft_id, quote_id, idempotency_key, actor_staff_id=None):
        existing=await session.scalar(select(Order).where(Order.organization_id==organization_id,Order.idempotency_key==idempotency_key))
        if existing: return existing
        draft=await session.scalar(select(OrderDraft).where(OrderDraft.id==draft_id,OrderDraft.organization_id==organization_id).with_for_update())
        if draft is None or draft.status!="draft" or draft.customer_id is None: raise DraftNotReady("Draft cannot be confirmed")
        quote=await session.scalar(select(OrderQuote).where(OrderQuote.id==quote_id,OrderQuote.draft_id==draft.id)); now=datetime.now(timezone.utc)
        if quote is None or quote.expires_at<=now: raise QuoteExpired("Quote has expired")
        if quote.draft_version!=draft.version or quote.category_counts_snapshot!=draft.category_counts: raise QuoteStale("Draft changed after quote")
        ident=await session.scalar(select(IdentificationSession).where(IdentificationSession.id==draft.identification_session_id).with_for_update())
        if ident is None or ident.status!="active" or ident.expires_at<=now: raise IdentificationExpired("Identification session is no longer valid")
        customer=await session.scalar(select(Customer).where(Customer.id==draft.customer_id,Customer.organization_id==organization_id).with_for_update()); state=await session.scalar(select(CustomerLoyaltyState).where(CustomerLoyaltyState.customer_id==draft.customer_id).with_for_update())
        if customer is None or customer.is_blocked or state is None: raise DraftNotReady("Customer is unavailable")
        account=await self.points._locked_account(session,organization_id,draft.customer_id); policy,_,after,maximum,redeemed,paid,earned,snapshot,selected_ids=await self._calculation(session,organization_id=organization_id,draft=draft,account=account,now=now)
        if snapshot!=quote.loyalty_effects_snapshot or paid!=quote.paid_amount_minor or earned!=quote.points_to_earn or maximum!=quote.max_redeemable_points: raise QuoteStale("Loyalty conditions changed after quote")
        qualification=after; new_qualification=state.qualification_spend_minor+qualification; tier_after=await self.tiers.tier_for_spend(session,organization_id,new_qualification)
        order=Order(organization_id=organization_id,location_id=draft.location_id,customer_id=draft.customer_id,draft_id=draft.id,quote_id=quote.id,gross_amount_minor=draft.gross_amount_minor,redeemed_points=redeemed,paid_amount_minor=paid,points_earned=earned,qualification_amount_minor=qualification,tier_before_id=policy.effective_tier.id,tier_after_id=tier_after.id,loyalty_effects_snapshot=snapshot,category_counts_snapshot=dict(draft.category_counts),idempotency_key=idempotency_key,actor_staff_id=actor_staff_id); session.add(order); await session.flush()
        if redeemed: await self.points.apply(session,organization_id=organization_id,customer_id=draft.customer_id,delta=-redeemed,entry_type=LedgerEntryType.REDEEM,reference_type="order",reference_id=order.id,idempotency_key=f"{idempotency_key}:redeem")
        if earned: await self.points.apply(session,organization_id=organization_id,customer_id=draft.customer_id,delta=earned,entry_type=LedgerEntryType.EARN,reference_type="order",reference_id=order.id,idempotency_key=f"{idempotency_key}:earn")
        if selected_ids:
            rewards=(await session.scalars(select(CustomerReward).where(CustomerReward.id.in_(selected_ids),CustomerReward.customer_id==draft.customer_id).order_by(CustomerReward.id.asc()).with_for_update())).all()
            if len(rewards)!=len(selected_ids): raise RewardSelectionInvalid("Selected reward changed before confirmation")
            for reward in rewards:
                if reward.quantity_remaining<=0 or reward.status!="active": raise RewardSelectionInvalid("Selected reward is unavailable")
                reward.quantity_remaining-=1
                if reward.quantity_remaining==0: reward.status="consumed"; reward.consumed_at=now
        await self.milestones.apply_sale(session,organization_id=organization_id,customer_id=draft.customer_id,order_id=order.id,category_counts=dict(draft.category_counts))
        previous_auto_id=state.automatic_tier_id; state.qualification_spend_minor=new_qualification; state.automatic_tier_id=tier_after.id; state.last_purchase_at=now; state.inactivity_steps=0; draft.status="confirmed"; ident.status="consumed"; ident.consumed_at=now
        if previous_auto_id != tier_after.id:
            body=await self.notifications.render(session,organization_id=organization_id,code="tier_changed",values={"tier":tier_after.name},fallback=f"Ваш уровень программы лояльности теперь: {tier_after.name}.")
            await self.notifications.enqueue(session,organization_id=organization_id,customer_id=draft.customer_id,body=body,kind="service",template_code="tier_changed",idempotency_key=f"tier:{order.id}:{tier_after.id}")
        await session.flush(); return order
