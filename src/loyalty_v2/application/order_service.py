from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loyalty_v2.application.services import DomainError, PointsService, TierService
from loyalty_v2.db.models import Customer, CustomerLoyaltyState, LedgerEntryType, PointsAccount
from loyalty_v2.db.order_models import IdentificationSession, Order, OrderDraft, OrderQuote


POINT_MINOR_VALUE = 100  # 1 point = 1 RUB = 100 kopecks
DEFAULT_REDEMPTION_PERCENT = 30
IDENTIFICATION_TTL_SECONDS = 90
QUOTE_TTL_SECONDS = 120


class InvalidIdentificationCode(DomainError):
    code = "INVALID_IDENTIFICATION_CODE"


class IdentificationExpired(DomainError):
    code = "IDENTIFICATION_EXPIRED"


class DraftNotReady(DomainError):
    code = "DRAFT_NOT_READY"


class QuoteExpired(DomainError):
    code = "QUOTE_EXPIRED"


class QuoteStale(DomainError):
    code = "QUOTE_STALE"


class RedemptionLimitExceeded(DomainError):
    code = "REDEMPTION_LIMIT_EXCEEDED"


@dataclass(frozen=True, slots=True)
class QuoteResult:
    quote: OrderQuote
    points_balance: int


class IdentificationService:
    async def generate(
        self, session: AsyncSession, *, organization_id: UUID, customer_id: UUID
    ) -> IdentificationSession:
        now = datetime.now(timezone.utc)
        active = (
            await session.scalars(
                select(IdentificationSession).where(
                    IdentificationSession.organization_id == organization_id,
                    IdentificationSession.customer_id == customer_id,
                    IdentificationSession.status == "active",
                )
            )
        ).all()
        for item in active:
            item.status = "expired"

        for _ in range(20):
            code = f"{secrets.randbelow(100000):05d}"
            collision = await session.scalar(
                select(IdentificationSession.id).where(
                    IdentificationSession.organization_id == organization_id,
                    IdentificationSession.code == code,
                    IdentificationSession.status == "active",
                )
            )
            if collision is None:
                identification = IdentificationSession(
                    organization_id=organization_id,
                    customer_id=customer_id,
                    code=code,
                    status="active",
                    expires_at=now + timedelta(seconds=IDENTIFICATION_TTL_SECONDS),
                )
                session.add(identification)
                await session.flush()
                return identification
        raise DomainError("Could not allocate identification code")

    async def attach_to_draft(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        draft_id: UUID,
        code: str,
    ) -> OrderDraft:
        now = datetime.now(timezone.utc)
        identification = await session.scalar(
            select(IdentificationSession)
            .where(
                IdentificationSession.organization_id == organization_id,
                IdentificationSession.code == code,
                IdentificationSession.status == "active",
            )
            .with_for_update()
        )
        if identification is None:
            raise InvalidIdentificationCode("Identification code is invalid")
        if identification.expires_at <= now:
            identification.status = "expired"
            raise IdentificationExpired("Identification code has expired")

        customer = await session.get(Customer, identification.customer_id)
        if customer is None or customer.is_blocked:
            raise InvalidIdentificationCode("Customer is unavailable")

        draft = await session.scalar(
            select(OrderDraft)
            .where(OrderDraft.id == draft_id, OrderDraft.organization_id == organization_id)
            .with_for_update()
        )
        if draft is None or draft.status != "draft":
            raise DraftNotReady("Order draft is unavailable")

        draft.customer_id = customer.id
        draft.identification_session_id = identification.id
        draft.version += 1
        await session.flush()
        return draft


class OrderService:
    def __init__(self) -> None:
        self.tiers = TierService()
        self.points = PointsService()

    async def create_draft(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID,
        gross_amount_minor: int,
        requested_points: int = 0,
        currency_code: str = "RUB",
    ) -> OrderDraft:
        if gross_amount_minor <= 0 or requested_points < 0:
            raise DraftNotReady("Invalid order values")
        draft = OrderDraft(
            organization_id=organization_id,
            location_id=location_id,
            gross_amount_minor=gross_amount_minor,
            requested_points=requested_points,
            currency_code=currency_code,
        )
        session.add(draft)
        await session.flush()
        return draft

    async def quote(self, session: AsyncSession, *, organization_id: UUID, draft_id: UUID) -> QuoteResult:
        draft = await session.scalar(
            select(OrderDraft).where(
                OrderDraft.id == draft_id,
                OrderDraft.organization_id == organization_id,
                OrderDraft.status == "draft",
            )
        )
        if draft is None or draft.customer_id is None:
            raise DraftNotReady("Draft must have an identified customer")

        customer = await session.get(Customer, draft.customer_id)
        if customer is None or customer.is_blocked:
            raise DraftNotReady("Customer is unavailable")

        state = await session.scalar(
            select(CustomerLoyaltyState).where(CustomerLoyaltyState.customer_id == customer.id)
        )
        account = await session.scalar(select(PointsAccount).where(PointsAccount.customer_id == customer.id))
        if state is None or account is None:
            raise DraftNotReady("Customer loyalty state is incomplete")

        tier = await self.tiers.tier_for_spend(session, organization_id, state.qualification_spend_minor)
        amount_after_rewards_minor = draft.gross_amount_minor  # reward/campaign engine plugs in here
        max_by_percent = (amount_after_rewards_minor * DEFAULT_REDEMPTION_PERCENT) // (100 * POINT_MINOR_VALUE)
        max_redeemable = min(max_by_percent, account.balance, amount_after_rewards_minor // POINT_MINOR_VALUE)
        if draft.requested_points > max_redeemable:
            raise RedemptionLimitExceeded("Requested points exceed current redemption limit")

        redeemed_points = draft.requested_points
        paid_amount_minor = amount_after_rewards_minor - redeemed_points * POINT_MINOR_VALUE
        points_to_earn = 0 if redeemed_points else (paid_amount_minor * tier.cashback_basis_points) // 1_000_000
        qualification_amount_minor = draft.gross_amount_minor
        potential_tier = await self.tiers.tier_for_spend(
            session, organization_id, state.qualification_spend_minor + qualification_amount_minor
        )
        now = datetime.now(timezone.utc)
        quote = OrderQuote(
            organization_id=organization_id,
            draft_id=draft.id,
            draft_version=draft.version,
            tier_id=tier.id,
            gross_amount_minor=draft.gross_amount_minor,
            amount_after_rewards_minor=amount_after_rewards_minor,
            max_redeemable_points=max_redeemable,
            redeemed_points=redeemed_points,
            paid_amount_minor=paid_amount_minor,
            points_to_earn=points_to_earn,
            qualification_amount_minor=qualification_amount_minor,
            potential_tier_id=potential_tier.id,
            expires_at=now + timedelta(seconds=QUOTE_TTL_SECONDS),
        )
        session.add(quote)
        await session.flush()
        return QuoteResult(quote=quote, points_balance=account.balance)

    async def confirm(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        draft_id: UUID,
        quote_id: UUID,
        idempotency_key: str,
    ) -> Order:
        existing = await session.scalar(
            select(Order).where(
                Order.organization_id == organization_id,
                Order.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing

        draft = await session.scalar(
            select(OrderDraft)
            .where(OrderDraft.id == draft_id, OrderDraft.organization_id == organization_id)
            .with_for_update()
        )
        if draft is None or draft.status != "draft" or draft.customer_id is None:
            raise DraftNotReady("Draft cannot be confirmed")

        quote = await session.scalar(
            select(OrderQuote).where(OrderQuote.id == quote_id, OrderQuote.draft_id == draft.id)
        )
        now = datetime.now(timezone.utc)
        if quote is None or quote.expires_at <= now:
            raise QuoteExpired("Quote has expired")
        if quote.draft_version != draft.version:
            raise QuoteStale("Draft changed after quote")

        identification = await session.scalar(
            select(IdentificationSession)
            .where(IdentificationSession.id == draft.identification_session_id)
            .with_for_update()
        )
        if identification is None or identification.status != "active" or identification.expires_at <= now:
            raise IdentificationExpired("Identification session is no longer valid")

        state = await session.scalar(
            select(CustomerLoyaltyState)
            .where(CustomerLoyaltyState.customer_id == draft.customer_id)
            .with_for_update()
        )
        if state is None:
            raise DraftNotReady("Loyalty state missing")

        # Recalculate against locked financial state instead of trusting UI values.
        account = await self.points._locked_account(session, organization_id, draft.customer_id)
        current_tier = await self.tiers.tier_for_spend(session, organization_id, state.qualification_spend_minor)
        max_by_percent = (draft.gross_amount_minor * DEFAULT_REDEMPTION_PERCENT) // (100 * POINT_MINOR_VALUE)
        max_redeemable = min(max_by_percent, account.balance, draft.gross_amount_minor // POINT_MINOR_VALUE)
        if draft.requested_points > max_redeemable:
            raise RedemptionLimitExceeded("Redemption availability changed")
        redeemed = draft.requested_points
        paid_minor = draft.gross_amount_minor - redeemed * POINT_MINOR_VALUE
        earned = 0 if redeemed else (paid_minor * current_tier.cashback_basis_points) // 1_000_000
        new_qualification = state.qualification_spend_minor + draft.gross_amount_minor
        tier_after = await self.tiers.tier_for_spend(session, organization_id, new_qualification)

        order = Order(
            organization_id=organization_id,
            location_id=draft.location_id,
            customer_id=draft.customer_id,
            draft_id=draft.id,
            quote_id=quote.id,
            gross_amount_minor=draft.gross_amount_minor,
            redeemed_points=redeemed,
            paid_amount_minor=paid_minor,
            points_earned=earned,
            qualification_amount_minor=draft.gross_amount_minor,
            tier_before_id=current_tier.id,
            tier_after_id=tier_after.id,
            idempotency_key=idempotency_key,
        )
        session.add(order)
        await session.flush()

        if redeemed:
            await self.points.apply(
                session,
                organization_id=organization_id,
                customer_id=draft.customer_id,
                delta=-redeemed,
                entry_type=LedgerEntryType.REDEEM,
                reference_type="order",
                reference_id=order.id,
                idempotency_key=f"{idempotency_key}:redeem",
            )
        if earned:
            await self.points.apply(
                session,
                organization_id=organization_id,
                customer_id=draft.customer_id,
                delta=earned,
                entry_type=LedgerEntryType.EARN,
                reference_type="order",
                reference_id=order.id,
                idempotency_key=f"{idempotency_key}:earn",
            )

        state.qualification_spend_minor = new_qualification
        state.automatic_tier_id = tier_after.id
        state.last_purchase_at = now
        state.inactivity_steps = 0
        draft.status = "confirmed"
        identification.status = "consumed"
        identification.consumed_at = now
        await session.flush()
        return order
